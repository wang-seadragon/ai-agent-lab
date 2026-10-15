"""Unit tests for selected-call evidence validation and routing."""
import json

from langchain_core.messages import AIMessage, ToolMessage

from app.agents.single_agent import route_after_llm, selected_tool_failures


def evidence(name, incident_id="INC-1001", *, status="success", payload=None):
    call = AIMessage(content="", tool_calls=[{
        "name": name, "args": {"incident_id": incident_id},
        "id": "call-1", "type": "tool_call",
    }])
    result = ToolMessage(
        name=name, tool_call_id="call-1", status=status,
        content=json.dumps(payload if payload is not None else {
            "incident_id": incident_id, "value": 1,
        }),
    )
    return [call, result]


def test_selected_tool_valid():
    state = {"messages": evidence("get_incident_metrics_mcp"),
             "incident_id": "INC-1001"}
    assert selected_tool_failures(state) == []


def test_failed_tool_rejected():
    state = {"messages": evidence("get_incident_logs_mcp", status="error"),
             "incident_id": "INC-1001"}
    assert selected_tool_failures(state) == ["get_incident_logs_mcp"]


def test_error_payload_rejected():
    state = {"messages": evidence("get_incident_logs_mcp", payload={
        "incident_id": "INC-1001", "error": "Not found",
    }), "incident_id": "INC-1001"}
    assert selected_tool_failures(state) == ["get_incident_logs_mcp"]


def test_wrong_incident_rejected():
    state = {"messages": evidence("get_incident_logs_mcp", payload={
        "incident_id": "INC-OTHER",
    }), "incident_id": "INC-1001"}
    assert selected_tool_failures(state) == ["get_incident_logs_mcp"]


def test_content_blocks_are_decoded():
    messages = evidence("get_incident_logs_mcp")
    messages[1].content = [
        {"type": "text", "text": '{"incident_id":"INC-1001"}'}
    ]
    assert selected_tool_failures({
        "messages": messages, "incident_id": "INC-1001",
    }) == []


def test_missing_tool_result_rejected():
    state = {"messages": evidence("get_incident_logs_mcp")[:1],
             "incident_id": "INC-1001"}
    assert selected_tool_failures(state) == ["get_incident_logs_mcp"]


def test_llm_tool_calls_route_to_tools():
    assert route_after_llm({
        "messages": evidence("get_incident_metrics_mcp")[:1],
    }) == "tools"


def test_llm_answer_routes_to_validation():
    assert route_after_llm({
        "messages": [AIMessage(content="Answer")],
    }) == "validate"
