"""End-to-end graph tests without running Ollama or MCP servers."""
import asyncio
import json

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from app.agents.single_agent import REQUIRED_TOOLS, build_agent, investigate


class ScriptedModel:
    def __init__(self):
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(content="", tool_calls=[
                {"name": name, "args": {"incident_id": "INC-1001"},
                 "id": f"call-{name}", "type": "tool_call"}
                for name in sorted(REQUIRED_TOOLS)
            ])
        return AIMessage(content="Evidence-based diagnosis.")


def fake_tools(fail_runbook=False):
    result = []
    for name in sorted(REQUIRED_TOOLS):
        async def implementation(incident_id: str, _name=name):
            if fail_runbook and _name == "get_incident_runbook_mcp":
                raise ConnectionError("Runbook MCP unavailable")
            return json.dumps({"incident_id": incident_id, "source": _name})
        # Use StructuredTool to keep the incident_id schema clean.
        from langchain_core.tools import StructuredTool
        result.append(StructuredTool.from_function(
            coroutine=implementation, name=name,
            description=f"Retrieve {name} for an incident",
        ))
    return result


def test_graph_complete_result():
    async def scenario():
        model = ScriptedModel()
        graph = build_agent(fake_tools(), model=model)
        return await investigate(graph, "INC-1001", "Investigate")
    result = asyncio.run(scenario())
    assert result["status"] == "complete"
    assert result["missing_evidence"] == []
    assert result["llm_rounds"] == 2
    assert result["answer"] == "Evidence-based diagnosis."
    assert all(v["status"] == "success" for v in result["tool_metrics"].values())


def test_graph_failure_returns_structured_incomplete(monkeypatch):
    monkeypatch.setattr("app.agents.single_agent.TOOL_ATTEMPTS", 2)
    monkeypatch.setattr("app.agents.single_agent.TOOL_BACKOFF_SECONDS", 0)
    async def scenario():
        model = ScriptedModel()
        graph = build_agent(fake_tools(fail_runbook=True), model=model)
        return await investigate(graph, "INC-1001", "Investigate")
    result = asyncio.run(scenario())
    assert result["status"] == "incomplete"
    assert result["missing_evidence"] == ["get_incident_runbook_mcp"]
    assert result["llm_rounds"] == 4
    assert result["tool_metrics"]["get_incident_runbook_mcp"]["status"] == "error"
    assert result["tool_metrics"]["get_incident_runbook_mcp"]["attempts"] == 2
    assert "No root cause is asserted" in result["answer"]
