from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.agents.single_agent import investigate

app = FastAPI(title="AI Agent Lab", version="0.1.0")


class InvestigationRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/investigate")
def investigate_incident(request: InvestigationRequest):
    return {
        "incident_id": request.incident_id,
        "answer": investigate(request.incident_id, request.question),
    }
