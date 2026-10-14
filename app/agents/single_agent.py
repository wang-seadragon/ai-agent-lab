"""Incident investigation StateGraph with bounded evidence collection and tool retries."""
import asyncio
import json
import logging
import os
import time
from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from app.llm.provider import get_chat_model

logger = logging.getLogger(__name__)

REQUIRED_TOOLS = frozenset({
    "get_incident_metrics_mcp", "get_incident_logs_mcp", "get_incident_runbook_mcp",
})
MAX_LLM_ROUNDS = 4
TOOL_ATTEMPTS = max(1, int(os.getenv("MCP_TOOL_ATTEMPTS", "3")))
TOOL_TIMEOUT_SECONDS = float(os.getenv("MCP_TOOL_TIMEOUT_SECONDS", "5"))
TOOL_BACKOFF_SECONDS = float(os.getenv("MCP_TOOL_BACKOFF_SECONDS", "0.25"))

SYSTEM_PROMPT = (
    "You are a read-only incident investigation assistant. "
    "Gather metrics, logs and runbook evidence before diagnosing an incident. "
    "Distinguish observed facts from hypotheses. Never fabricate evidence. "
    "Do not perform remediation. If evidence is missing, request the missing tools."
)


class InvestigationState(MessagesState):
    incident_id: str
    llm_rounds: int
    needs_retry: bool
    status: str
    tool_metrics: dict


class InvestigationResult(TypedDict):
    incident_id: str
    status: str
    missing_evidence: list[str]
    llm_rounds: int
    tool_metrics: dict
    duration_ms: float
    answer: str


def _payload(content):
    """Decode MCP JSON text or text blocks."""
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
    calls = {}
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                calls[call["id"]] = (call["name"], call.get("args", {}))
    valid = set()
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name not in REQUIRED_TOOLS:
            continue
        if message.status == "error":
            continue
        call = calls.get(message.tool_call_id)
        if not call or call[0] != message.name:
            continue
        expected = incident_id or call[1].get("incident_id")
        if not expected or call[1].get("incident_id") != expected:
            continue
        data = _payload(message.content)
        if isinstance(data, dict) and not data.get("error") and data.get("incident_id") == expected:
            valid.add(message.name)
    return valid


def missing_evidence(state):
    return REQUIRED_TOOLS - successful_evidence(state["messages"], state.get("incident_id"))


def route_after_llm(state):
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None) and state.get("llm_rounds", 0) < MAX_LLM_ROUNDS:
        return "tools"
    return "validate"


def route_after_validation(state):
    return "agent" if state.get("needs_retry", False) else END


def _content(value):
    if isinstance(value, ToolMessage):
        return value.content
    if isinstance(value, (str, list)):
        return value
    return json.dumps(value, default=str)


def build_agent(tools, model=None):
    tools_by_name = {tool.name: tool for tool in tools}
    missing = REQUIRED_TOOLS - tools_by_name.keys()
    if missing:
        raise ValueError(f"Missing MCP tool definitions: {sorted(missing)}")
    llm = (model if model is not None else get_chat_model()).bind_tools(tools)

    async def call_llm(state):
        response = await llm.ainvoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])
        rounds = state.get("llm_rounds", 0) + 1
        logger.info("LLM round=%d selected_tools=%s", rounds,
                    [call["name"] for call in response.tool_calls])
        return {"messages": [response], "llm_rounds": rounds}

    async def execute_tools(state):
        """Run selected calls concurrently; retry each transient failure without the LLM."""
        calls = state["messages"][-1].tool_calls
        incident_id = state["incident_id"]

        async def run_one(call):
            name, call_id = call["name"], call["id"]
            args = call.get("args", {})
            started = time.perf_counter()
            error = None
            attempts = 0
            tool = tools_by_name.get(name)
            # Reject wrong-incident calls; never silently query another incident.
            if tool is None or args.get("incident_id") != incident_id:
                error = "Unknown tool or incident ID mismatch"
            else:
                for attempt in range(1, TOOL_ATTEMPTS + 1):
                    attempts = attempt
                    try:
                        result = await asyncio.wait_for(
                            tool.ainvoke(args), timeout=TOOL_TIMEOUT_SECONDS
                        )
                        if isinstance(result, ToolMessage) and result.status == "error":
                            raise RuntimeError(str(result.content))
                        payload = _payload(_content(result))
                        # A returned business error is not a transport failure: don't retry it.
                        if isinstance(payload, dict) and payload.get("error"):
                            error = str(payload["error"])
                            break
                        duration = round((time.perf_counter() - started) * 1000, 2)
                        logger.info("MCP tool=%s status=success attempts=%d duration_ms=%.2f",
                                    name, attempts, duration)
                        return (
                            ToolMessage(name=name, tool_call_id=call_id,
                                        content=_content(result), status="success"),
                            {"status": "success", "attempts": attempts, "duration_ms": duration},
                        )
                    except Exception as exc:
                        error = f"{type(exc).__name__}: {exc}"
                        logger.warning("MCP tool=%s attempt=%d/%d failed: %s",
                                       name, attempt, TOOL_ATTEMPTS, error)
                        if attempt < TOOL_ATTEMPTS:
                            await asyncio.sleep(TOOL_BACKOFF_SECONDS * 2 ** (attempt - 1))
            duration = round((time.perf_counter() - started) * 1000, 2)
            return (
                ToolMessage(name=name, tool_call_id=call_id,
                            content=f"Error: {error}", status="error"),
                {"status": "error", "attempts": attempts, "duration_ms": duration},
            )

        results = await asyncio.gather(*(run_one(call) for call in calls))
        metrics = dict(state.get("tool_metrics", {}))
        for call, (_, measurement) in zip(calls, results):
            metrics[call["name"]] = measurement
        return {"messages": [message for message, _ in results], "tool_metrics": metrics}

    def validate(state):
        missing = missing_evidence(state)
        rounds = state.get("llm_rounds", 0)
        last = state["messages"][-1]
        if not missing and not getattr(last, "tool_calls", None):
            logger.info("Investigation complete: all required evidence collected")
            return {"needs_retry": False, "status": "complete"}
        if rounds >= MAX_LLM_ROUNDS:
            logger.warning("Investigation incomplete after %d rounds; missing=%s",
                           rounds, sorted(missing))
            return {
                "messages": [AIMessage(content=(
                    "Investigation incomplete: evidence collection or final synthesis "
                    f"did not finish within {MAX_LLM_ROUNDS} LLM rounds. "
                    f"Missing valid evidence: {', '.join(sorted(missing)) or 'none'}. "
                    "No root cause is asserted."
                ))],
                "needs_retry": False,
                "status": "incomplete",
            }
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
    graph.add_node("tools", execute_tools)
    graph.add_node("validate", validate)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_llm,
                                {"tools": "tools", "validate": "validate"})
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges("validate", route_after_validation,
                                {"agent": "agent", END: END})
    return graph.compile()


async def investigate(agent, incident_id: str, question: str) -> InvestigationResult:
    started = time.perf_counter()
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=f"Incident ID: {incident_id}. {question}")],
         "incident_id": incident_id, "llm_rounds": 0, "needs_retry": False,
         "status": "incomplete", "tool_metrics": {}},
        config={"recursion_limit": 30},
    )
    for message in result["messages"]:
        if isinstance(message, AIMessage):
            logger.info("LLM response: %s", message.content)
            for call in message.tool_calls:
                logger.info("LLM selected tool: %s | arguments: %s",
                            call["name"], call["args"])
        elif isinstance(message, ToolMessage):
            logger.info("MCP tool result: %s | status=%s | %s",
                        message.name, message.status, message.content)
    return {
        "incident_id": incident_id,
        "status": result["status"],
        "missing_evidence": sorted(missing_evidence(result)),
        "llm_rounds": result["llm_rounds"],
        "tool_metrics": result["tool_metrics"],
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "answer": str(result["messages"][-1].content),
    }
