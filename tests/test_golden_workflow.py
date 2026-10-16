"""Golden workflow evaluations: deterministic, no live LLM or MCP dependency.

These scenarios measure orchestration contracts, NOT diagnostic correctness.
"""
import asyncio
import json

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.agents.single_agent import build_agent, investigate

METRICS = "get_incident_metrics_mcp"
LOGS = "get_incident_logs_mcp"
RUNBOOK = "get_incident_runbook_mcp"
INCIDENT = "INC-1001"


class ScriptedModel:
    """Explicit tool decisions make regression runs repeatable."""

    def __init__(self, selections):
        self.selections = selections
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        index = self.calls
        self.calls += 1
        if index >= len(self.selections):
            return AIMessage(content="Scripted answer based on collected evidence.")
        return AIMessage(content="", tool_calls=[
            {"name": call["name"], "args": {"incident_id": call.get("incident_id", INCIDENT)},
             "id": f"golden-{index}-{i}", "type": "tool_call"}
            for i, call in enumerate(self.selections[index])
        ])


def selection(*names):
    return [{"name": name} for name in names]


def make_tools(*, failing=(), application_errors=()):
    tools = []
    for name in (METRICS, LOGS, RUNBOOK):
        async def implementation(incident_id: str, _name=name):
            if _name in failing:
                raise ConnectionError("MCP unavailable")
            if _name in application_errors:
                return json.dumps({"incident_id": incident_id, "error": "Access denied"})
            return json.dumps({"incident_id": incident_id, "source": _name,
                               "observation": "Synthetic fixture"})
        tools.append(StructuredTool.from_function(
            coroutine=implementation, name=name, description=f"Fetch {name}"
        ))
    return tools


# Every case asserts the externally visible investigation contract.
# "incomplete" is expected when any selected tool fails.
CASES = [
    ("metrics_only", [selection(METRICS)], "complete", [METRICS], [], 2),
    ("logs_only", [selection(LOGS)], "complete", [LOGS], [], 2),
    ("runbook_only", [selection(RUNBOOK)], "complete", [RUNBOOK], [], 2),
    ("metrics_and_logs", [selection(METRICS, LOGS)], "complete", [METRICS, LOGS], [], 2),
    ("all_three", [selection(METRICS, LOGS, RUNBOOK)], "complete",
     [METRICS, LOGS, RUNBOOK], [], 2),
    ("iterative", [selection(METRICS), selection(LOGS)], "complete",
     [METRICS, LOGS], [], 3),
    ("no_evidence", [], "incomplete", [], ["no_tools_selected"], 1),
    ("one_failed_source", [selection(METRICS, RUNBOOK)], "incomplete",
     [METRICS, RUNBOOK], [RUNBOOK], 2),
    ("all_sources_fail", [selection(RUNBOOK)], "incomplete",
     [RUNBOOK], [RUNBOOK], 1),
    ("wrong_incident", [[{"name": METRICS, "incident_id": "INC-OTHER"}]],
     "incomplete", [METRICS], [METRICS], 1),
    ("unknown_tool", [selection("unknown_mcp_tool")], "incomplete",
     ["unknown_mcp_tool"], ["unknown_mcp_tool"], 1),
    ("application_error", [selection(LOGS)], "incomplete", [LOGS], [LOGS], 1),
]


@pytest.mark.parametrize(
    "case_id,selections,status,selected,missing,rounds",
    CASES, ids=[case[0] for case in CASES],
)
def test_golden_workflow(case_id, selections, status, selected, missing, rounds, monkeypatch):
    monkeypatch.setattr("app.agents.single_agent.TOOL_ATTEMPTS", 1)
    monkeypatch.setattr("app.agents.single_agent.TOOL_BACKOFF_SECONDS", 0)
    failing = (RUNBOOK,) if case_id in ("one_failed_source", "all_sources_fail") else ()
    application_errors = (LOGS,) if case_id == "application_error" else ()
    model = ScriptedModel(selections)
    agent = build_agent(make_tools(failing=failing, application_errors=application_errors),
                        model=model)
    result = asyncio.run(investigate(agent, INCIDENT, "Investigate the incident"))

    assert result["incident_id"] == INCIDENT
    assert result["status"] == status
    assert set(result["tool_metrics"]) == set(selected)
    assert set(result["missing_evidence"]) == set(missing)
    assert result["llm_rounds"] == rounds
    assert result["answer"]
    assert result["duration_ms"] >= 0
    assert {error["tool"] for error in result["tool_errors"]} == set(missing) - {
        "no_tools_selected"
    }
    for metric in result["tool_metrics"].values():
        assert metric["attempts"] >= 0
        assert metric["duration_ms"] >= 0
