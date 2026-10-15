"""End-to-end graph tests without running Ollama or MCP servers."""
import asyncio
import json

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from app.agents.single_agent import REQUIRED_TOOLS, build_agent, build_evidence_first_agent, build_llm_selected_agent, investigate


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


class SynthesisOnlyModel:
    def __init__(self):
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        return AIMessage(content="Evidence-first diagnosis.")


def test_evidence_first_success_uses_one_llm_round():
    async def scenario():
        model = SynthesisOnlyModel()
        graph = build_evidence_first_agent(fake_tools(), model=model)
        return await investigate(graph, "INC-1001", "Investigate"), model.calls
    result, calls = asyncio.run(scenario())
    assert result["status"] == "complete"
    assert result["missing_evidence"] == []
    assert result["llm_rounds"] == 1
    assert calls == 1
    assert result["answer"] == "Evidence-first diagnosis."


def test_evidence_first_outage_skips_llm(monkeypatch):
    monkeypatch.setattr("app.agents.single_agent.TOOL_ATTEMPTS", 2)
    monkeypatch.setattr("app.agents.single_agent.TOOL_BACKOFF_SECONDS", 0)
    async def scenario():
        model = SynthesisOnlyModel()
        graph = build_evidence_first_agent(fake_tools(fail_runbook=True), model=model)
        return await investigate(graph, "INC-1001", "Investigate"), model.calls
    result, calls = asyncio.run(scenario())
    assert result["status"] == "incomplete"
    assert result["missing_evidence"] == ["get_incident_runbook_mcp"]
    assert result["llm_rounds"] == 0
    assert calls == 0
    assert result["tool_metrics"]["get_incident_runbook_mcp"]["attempts"] == 2
    assert "No root cause is asserted" in result["answer"]


def test_llm_selected_success_calls_only_selected_tools():
    async def scenario():
        model = ScriptedModel()
        selected = fake_tools()[:1]
        name = selected[0].name

        class SelectOne(ScriptedModel):
            async def ainvoke(self, messages):
                self.calls += 1
                if self.calls == 1:
                    return AIMessage(content="", tool_calls=[
                        {"name": name, "args": {"incident_id": "INC-1001"},
                         "id": "selected-1", "type": "tool_call"}
                    ])
                return AIMessage(content="Selected evidence diagnosis.")

        model = SelectOne()
        graph = build_llm_selected_agent(fake_tools(), model=model)
        result = await investigate(graph, "INC-1001", "Investigate")
        return result, model.calls, name

    result, calls, name = asyncio.run(scenario())
    assert result["status"] == "complete"
    assert result["missing_evidence"] == []
    assert result["llm_rounds"] == 2
    assert calls == 2
    assert set(result["tool_metrics"]) == {name}


def test_llm_selected_outage_skips_synthesis(monkeypatch):
    monkeypatch.setattr("app.agents.single_agent.TOOL_ATTEMPTS", 2)
    monkeypatch.setattr("app.agents.single_agent.TOOL_BACKOFF_SECONDS", 0)

    async def scenario():
        model = ScriptedModel()
        graph = build_llm_selected_agent(fake_tools(fail_runbook=True), model=model)
        result = await investigate(graph, "INC-1001", "Investigate")
        return result, model.calls

    result, calls = asyncio.run(scenario())
    assert result["status"] == "incomplete"
    assert result["missing_evidence"] == ["get_incident_runbook_mcp"]
    assert result["llm_rounds"] == 1
    assert calls == 1
    assert result["tool_metrics"]["get_incident_runbook_mcp"]["attempts"] == 2


def test_llm_selected_no_tools_is_incomplete():
    class NoTools:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            return AIMessage(content="I think it is CPU.")

    async def scenario():
        graph = build_llm_selected_agent(fake_tools(), model=NoTools())
        return await investigate(graph, "INC-1001", "Investigate")

    result = asyncio.run(scenario())
    assert result["status"] == "incomplete"
    assert result["llm_rounds"] == 1
    assert result["missing_evidence"] == ["no_tools_selected"]
