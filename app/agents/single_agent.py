from langgraph.prebuilt import create_react_agent

from app.llm.provider import get_chat_model
from app.tools import get_incident_logs, get_incident_metrics, get_incident_runbook

SYSTEM_PROMPT = (
    "You are a read-only incident investigation assistant. "
    "Use metrics, logs and runbooks to gather evidence before diagnosing an incident. "
    "Distinguish observed facts from hypotheses. Never fabricate evidence. "
    "Do not perform remediation."
)


def build_agent():
    return create_react_agent(
        get_chat_model(),
        tools=[get_incident_metrics, get_incident_logs, get_incident_runbook],
        prompt=SYSTEM_PROMPT,
    )


def investigate(incident_id: str, question: str) -> str:
    agent = build_agent()
    result = agent.invoke({
        "messages": [
            {"role": "user", "content": f"Incident ID: {incident_id}. {question}"}
        ]
    })
    return str(result["messages"][-1].content)
