"""Unit tests for bounded investigation and incident-scoped evidence."""
import json

from langchain_core.messages import AIMessage, ToolMessage

from app.agents.single_agent import (
    MAX_LLM_ROUNDS, REQUIRED_TOOLS, missing_evidence,
    route_after_llm, route_after_validation, successful_evidence,
)


def evidence(name, incident_id="INC-1001", *, status="success", payload=None):
    call_id = f"call-{name}"
    call = AIMessage(content="", tool_calls=[{
        "name": name, "args": {"incident_id": incident_id},
        "id": call_id, "type": "tool_call",
    }])
    result = ToolMessage(
        name=name, tool_call_id=call_id, status=status,
        content=json.dumps(payload if payload is not None else {"incident_id": incident_id, "value": 1}),
    )
    return [call, result]


def test_all_required_evidence_is_complete():
    messages = sum((evidence(name) for name in REQUIRED_TOOLS), [])
    assert missing_evidence({"messages": messages, "incident_id": "INC-1001"}) == set()


def test_missing_evidence_requires_more_work():
    messages = evidence("get_incident_metrics_mcp")
    assert missing_evidence({"messages": messages, "incident_id": "INC-1001"}) == (
        REQUIRED_TOOLS - {"get_incident_metrics_mcp"}
    )


def test_failed_tool_result_is_not_valid_evidence():
    messages = evidence("get_incident_logs_mcp", status="error")
    assert not successful_evidence(messages, "INC-1001")


def test_error_payload_is_not_evidence():
    messages = evidence("get_incident_logs_mcp", payload={
        "incident_id": "INC-1001", "error": "Incident not found",
    })
    assert not successful_evidence(messages, "INC-1001")


def test_wrong_incident_is_not_evidence():
    messages = evidence("get_incident_logs_mcp", payload={
        "incident_id": "INC-OTHER", "entries": [],
    })
    assert not successful_evidence(messages, "INC-1001")


def test_mcp_content_blocks_are_decoded():
    messages = evidence("get_incident_logs_mcp")
    messages[1].content = [{"type": "text", "text": '{"incident_id":"INC-1001","entries":[]}'}]
    assert successful_evidence(messages, "INC-1001") == {"get_incident_logs_mcp"}


def test_llm_tool_calls_route_to_tools():
    message = evidence("get_incident_metrics_mcp")[0]
    assert route_after_llm({"messages": [message], "llm_rounds": 1}) == "tools"


def test_llm_tool_calls_stop_at_limit():
    message = evidence("get_incident_metrics_mcp")[0]
    assert route_after_llm({"messages": [message], "llm_rounds": MAX_LLM_ROUNDS}) == "validate"


def test_llm_without_tool_calls_routes_to_validation():
    assert route_after_llm({"messages": [AIMessage(content="Answer")], "llm_rounds": 1}) == "validate"


def test_validation_controls_termination():
    assert route_after_validation({"needs_retry": True}) == "agent"
    assert route_after_validation({"needs_retry": False}) == "__end__"
