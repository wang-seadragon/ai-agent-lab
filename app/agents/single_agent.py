"""Explicit LangGraph workflow with evidence-based completion gating."""
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


def successful_evidence(messages):
    """Only count completed, non-error MCP tool responses."""
    return {
        message.name
        for message in messages
        if isinstance(message, ToolMessage)
        and message.name in REQUIRED_TOOLS
        and message.status != "error"
        and bool(message.content)
        and not (isinstance(message.content, str) and message.content.startswith("Error:"))
    }


def missing_evidence(state):
    return REQUIRED_TOOLS - successful_evidence(state["messages"])


def route_after_llm(state):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "validate"


def route_after_validation(state):
    return "agent" if state.get("needs_retry", False) else END


def build_agent(tools, model=None):
    """Compile a state graph once at application startup."""
    names = {tool.name for tool in tools}
    missing = REQUIRED_TOOLS - names
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
            rounds,
            [call["name"] for call in response.tool_calls],
        )
        return {"messages": [response], "llm_rounds": rounds}

    def validate(state):
        missing = missing_evidence(state)
        if not missing:
            logger.info("Investigation complete: all required evidence collected")
            return {"needs_retry": False}

        rounds = state.get("llm_rounds", 0)
        if rounds >= MAX_LLM_ROUNDS:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "Investigation incomplete: required MCP evidence was not "
                            f"collected after {rounds} LLM rounds. "
                            f"Missing: {', '.join(sorted(missing))}. "
                            "No root cause is asserted."
                        )
                    )
                ],
                "needs_retry": False,
            }

        logger.warning("Missing evidence, requesting tools: %s", sorted(missing))
        return {
            "messages": [
                HumanMessage(
                    content=(
                        "Before finalizing, call these missing MCP tools: "
                        + ", ".join(sorted(missing))
                        + ". Do not provide a final diagnosis without their results."
                    )
                )
            ],
            "needs_retry": True,
        }

    # Keep routing state explicit; validation decides whether to retry or finish.
    class GraphState(InvestigationState):
        needs_retry: bool

    graph = StateGraph(GraphState)
    graph.add_node("agent", call_llm)
    graph.add_node("tools", ToolNode(tools))
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
            "messages": [
                HumanMessage(content=f"Incident ID: {incident_id}. {question}")
            ],
            "llm_rounds": 0,
            "needs_retry": False,
        },
        config={"recursion_limit": 30},
    )
    return str(result["messages"][-1].content)
