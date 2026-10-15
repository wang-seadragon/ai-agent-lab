"""Iterative tool-selection workflow tests without live Ollama or MCP."""
import asyncio
import json

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.agents.single_agent import build_agent, investigate


def fake_tools(fail_name=None):
    tools = []
    for name in ("get_incident_metrics_mcp", "get_incident_logs_mcp",
                 "get_incident_runbook_mcp"):
        async def implementation(incident_id: str, _name=name):
            if _name == fail_name:
                raise ConnectionError("MCP unavailable")
            return json.dumps({"incident_id": incident_id, "source": _name})
        tools.append(StructuredTool.from_function(
            coroutine=implementation, name=name,
            description=f"Retrieve {name} for an incident",
        ))
    return tools


class ScriptedModel:
    def __init__(self, selections):
        self.selections = selections
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        index = self.calls
        self.calls += 1
        if index < len(self.selections):
            return AIMessage(content="", tool_calls=[
                {"name": name, "args": {"incident_id": "INC-1001"},
                 "id": f"call-{index}-{name}", "type": "tool_call"}
                for name in self.selections[index]
            ])
        return AIMessage(content="Evidence-based diagnosis.")


def run(model, tools=None):
    async def scenario():
        graph = build_agent(tools or fake_tools(), model=model)
        return await investigate(graph, "INC-1001", "Investigate")
    return asyncio.run(scenario())


def test_only_selected_tool_is_required():
    model = ScriptedModel([["get_incident_metrics_mcp"]])
    result = run(model)
    assert result["status"] == "complete"
    assert result["missing_evidence"] == []
    assert result["llm_rounds"] == 2
    assert set(result["tool_metrics"]) == {"get_incident_metrics_mcp"}


def test_iterative_tool_selection_based_on_evidence():
    model = ScriptedModel([
        ["get_incident_metrics_mcp"],
        ["get_incident_logs_mcp"],
    ])
    result = run(model)
    assert result["status"] == "complete"
    assert result["llm_rounds"] == 3
    assert set(result["tool_metrics"]) == {
        "get_incident_metrics_mcp", "get_incident_logs_mcp",
    }


def test_tool_failure_stops_before_another_llm_round(monkeypatch):
    monkeypatch.setattr("app.agents.single_agent.TOOL_ATTEMPTS", 2)
    monkeypatch.setattr("app.agents.single_agent.TOOL_BACKOFF_SECONDS", 0)
    model = ScriptedModel([["get_incident_runbook_mcp"]])
    result = run(model, fake_tools(fail_name="get_incident_runbook_mcp"))
    assert result["status"] == "incomplete"
    assert result["missing_evidence"] == ["get_incident_runbook_mcp"]
    assert result["llm_rounds"] == 1
    assert model.calls == 1
    assert result["tool_metrics"]["get_incident_runbook_mcp"]["attempts"] == 2


def test_no_tools_selected_is_incomplete():
    model = ScriptedModel([])
    result = run(model)
    assert result["status"] == "incomplete"
    assert result["missing_evidence"] == ["no_tools_selected"]
    assert result["llm_rounds"] == 1


def test_round_limit_stops_tool_loop(monkeypatch):
    monkeypatch.setattr("app.agents.single_agent.MAX_LLM_ROUNDS", 2)
    model = ScriptedModel([
        ["get_incident_metrics_mcp"],
        ["get_incident_logs_mcp"],
    ])
    result = run(model)
    assert result["status"] == "incomplete"
    assert result["missing_evidence"] == ["llm_round_limit"]
    assert result["llm_rounds"] == 2
    assert model.calls == 2
