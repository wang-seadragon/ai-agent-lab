"""Reusable incident investigation agent backed by MCP tools."""
from langgraph.prebuilt import create_react_agent
from app.llm.provider import get_chat_model

SYSTEM_PROMPT = (
    "You are a read-only incident investigation assistant. "
    "Use metrics, logs and runbooks to gather evidence before diagnosing an incident. "
    "Distinguish observed facts from hypotheses. Never fabricate evidence. "
    "Do not perform remediation."
)


def build_agent(tools):
    """Compile once during FastAPI startup, not once per request."""
    return create_react_agent(get_chat_model(), tools=tools, prompt=SYSTEM_PROMPT)


async def investigate(agent, incident_id: str, question: str) -> str:
    result = await agent.ainvoke({
        "messages": [
            {"role": "user", "content": f"Incident ID: {incident_id}. {question}"}
        ]
    })
    return str(result["messages"][-1].content)
