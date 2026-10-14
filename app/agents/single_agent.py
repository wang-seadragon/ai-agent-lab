"""Explicit LangGraph workflow with bounded MCP failure handling."""
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode

from app.llm.provider import get_chat_model

logger = logging.getLogger(__name__)

REQUIRED_TOOLS = frozenset({
    "get_incident_metrics_mcp",
    "get_incident_logs_mcp",
    "get_incident_runbook_mcp",
})
MAX_LLM_ROUNDS = 4

SYSTEM_PROMPT = (
    "You are a read-only incident investigation assistant. "
    "Gather metrics, logs and runbook evidence before diagnosing an incident. "
    "Distinguish observed facts from hypotheses. Never fabricate evidence. "
    "Do not perform remediation. "
    "If you lack required evidence, request the missing tools."
)


class InvestigationState(MessagesState):
    llm_rounds: int
    needs_retry: bool
    incident_id: str


def _payload(content):
    """Decode either ordinary JSON text or MCP text content blocks."""
    try:
        if isinstance(content, str):
            return json.loads(content)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return json.loads(block["text"])
    except (ValueError, TypeError, KeyError):
        pass
    return None


def successful_evidence(messages, incident_id=None):
    """Require a matching tool call and a successful, incident-scoped JSON result."""
    requested = {}
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                requested[call["id"]] = (call["name"], call.get("args", {}))

    valid = set()
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name not in REQUIRED_TOOLS:
            continue
        if message.status == "error":
            continue
        call = requested.get(message.tool_call_id)
        if not call or call[0] != message.name:
            continue
        expected_id = incident_id or call[1].get("incident_id")
        if not expected_id or call[1].get("incident_id") != expected_id:
            continue
        data = _payload(message.content)
        if isinstance(data, dict) and not data.get("error") and data.get("incident_id") == expected_id:
            valid.add(message.name)
    return valid


def missing_evidence(state):
    return REQUIRED_TOOLS - successful_evidence(
        state["messages"], state.get("incident_id")
    )


def route_after_llm(state):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None) and state.get("llm_rounds", 0) < MAX_LLM_ROUNDS:
        return "tools"
    return "validate"


def route_after_validation(state):
    return "agent" if state.get("needs_retry", False) else END


def build_agent(tools, model=None):
    """Compile the investigation workflow once at startup."""
    missing = REQUIRED_TOOLS - {tool.name for tool in tools}
    if missing:
        raise ValueError(f"Missing required MCP tool definitions: {sorted(missing)}")

    llm = (model if model is not None else get_chat_model()).bind_tools(tools)

    async def call_llm(state):
        response = await llm.ainvoke(
            [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        )
        rounds = state.get("llm_rounds", 0) + 1
        logger.info(
            "LLM round=%d selected_tools=%s",
            rounds, [call["name"] for call in response.tool_calls],
        )
        return {"messages": [response], "llm_rounds": rounds}

    def validate(state):
        missing = missing_evidence(state)
        rounds = state.get("llm_rounds", 0)
        last = state["messages"][-1]

        # A final answer is accepted only after complete evidence collection.
        if not missing and not getattr(last, "tool_calls", None):
            logger.info("Investigation complete: all required evidence collected")
            return {"needs_retry": False}

        if rounds >= MAX_LLM_ROUNDS:
            logger.warning("Investigation incomplete after %d rounds; missing=%s", rounds, sorted(missing))
            return {
                "messages": [AIMessage(content=(
                    "Investigation incomplete: evidence collection or final synthesis "
                    f"did not finish within {MAX_LLM_ROUNDS} LLM rounds. "
                    f"Missing valid evidence: {', '.join(sorted(missing)) or 'none'}. "
                    "No root cause is asserted."
                ))],
                "needs_retry": False,
            }

        logger.warning("Investigation needs retry; missing=%s", sorted(missing))
        return {
            "messages": [HumanMessage(content=(
                "Continue the investigation. Missing valid MCP evidence: "
                + (", ".join(sorted(missing)) or "none; provide the final answer now")
                + ". Use incident ID " + state["incident_id"]
                + ". Do not diagnose without valid evidence."
            ))],
            "needs_retry": True,
        }

    graph = StateGraph(InvestigationState)
    graph.add_node("agent", call_llm)
    # Convert invocation failures (including MCP transport errors) to error ToolMessages.
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_node("validate", validate)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent", route_after_llm, {"tools": "tools", "validate": "validate"}
    )
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges(
        "validate", route_after_validation, {"agent": "agent", END: END}
    )
    return graph.compile()


async def investigate(agent, incident_id: str, question: str) -> str:
    result = await agent.ainvoke(
        {
            "messages": [HumanMessage(content=f"Incident ID: {incident_id}. {question}")],
            "incident_id": incident_id,
            "llm_rounds": 0,
            "needs_retry": False,
        },
        config={"recursion_limit": 30},
    )
    for message in result["messages"]:
        if isinstance(message, AIMessage):
            logger.info("LLM response: %s", message.content)
            for call in message.tool_calls:
                logger.info("LLM selected tool: %s | arguments: %s", call["name"], call["args"])
        elif isinstance(message, ToolMessage):
            logger.info("MCP tool result: %s | status=%s | %s", message.name, message.status, message.content)
    return str(result["messages"][-1].content)
