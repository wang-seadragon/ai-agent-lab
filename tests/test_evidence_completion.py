"""Evidence completion gate regression tests; no Ollama dependency."""
import asyncio

from app.agents.single_agent import build_agent, investigate
from tests.test_golden_workflow import (
    INCIDENT, LOGS, METRICS, RUNBOOK, ScriptedModel, make_tools, selection,
)


def test_confirmation_question_collects_missing_sources():
    model = ScriptedModel([selection(METRICS)])
    agent = build_agent(make_tools(), model=model)
    result = asyncio.run(investigate(
        agent, INCIDENT, "Investigate latency. Can you confirm the root cause?"
    ))
    assert result["status"] == "complete"
    assert set(result["tool_metrics"]) == {METRICS, LOGS, RUNBOOK}
    assert result["llm_rounds"] == 3
    assert result["root_cause_confirmed"] is False


def test_nonconfirmation_question_keeps_dynamic_tool_choice():
    model = ScriptedModel([selection(METRICS)])
    agent = build_agent(make_tools(), model=model)
    result = asyncio.run(investigate(agent, INCIDENT, "Summarize CPU metrics"))
    assert result["status"] == "complete"
    assert set(result["tool_metrics"]) == {METRICS}


def test_failed_required_source_remains_incomplete(monkeypatch):
    monkeypatch.setattr("app.agents.single_agent.TOOL_ATTEMPTS", 1)
    model = ScriptedModel([selection(METRICS)])
    agent = build_agent(make_tools(failing=(LOGS,)), model=model)
    result = asyncio.run(investigate(
        agent, INCIDENT, "Can you confirm the root cause?"
    ))
    assert result["status"] == "incomplete"
    assert LOGS in result["missing_evidence"]
    assert result["root_cause_confirmed"] is False
