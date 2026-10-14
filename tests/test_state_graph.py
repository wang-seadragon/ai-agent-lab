"""Unit tests for explicit investigation completion rules."""
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.single_agent import (
    REQUIRED_TOOLS,
    missing_evidence,
    route_after_llm,
    route_after_validation,
    successful_evidence,
)


def tool_result(name, status="success", content="ok"):
    return ToolMessage(
        content=content, name=name, tool_call_id=name, status=status
    )


def test_all_required_evidence_is_complete():
    state = {"messages": [tool_result(name) for name in REQUIRED_TOOLS]}
    assert missing_evidence(state) == set()


def test_missing_evidence_requires_more_work():
    state = {"messages": [tool_result("get_incident_metrics_mcp")]}
    assert missing_evidence(state) == REQUIRED_TOOLS - {"get_incident_metrics_mcp"}


def test_failed_tool_result_is_not_valid_evidence():
    messages = [tool_result("get_incident_logs_mcp", status="error", content="timeout")]
    assert "get_incident_logs_mcp" not in successful_evidence(messages)


def test_llm_tool_calls_route_to_tools():
    message = AIMessage(
        content="",
        tool_calls=[{
            "name": "get_incident_metrics_mcp",
            "args": {"incident_id": "INC-1001"},
            "id": "call-1",
            "type": "tool_call",
        }],
    )
    assert route_after_llm({"messages": [message]}) == "tools"


def test_llm_without_tool_calls_routes_to_validation():
    assert route_after_llm({"messages": [AIMessage(content="Answer")]}) == "validate"


def test_validation_controls_termination():
    assert route_after_validation({"needs_retry": True}) == "agent"
    assert route_after_validation({"needs_retry": False}) == "__end__"
