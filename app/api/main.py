"""FastAPI application; discover MCP tools and compile graph at startup."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from app.agents.single_agent import build_agent, investigate
from app.mcp_client import create_mcp_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = create_mcp_client()
    tools = await client.get_tools()
    if len(tools) != 3:
        raise RuntimeError(f"Expected 3 MCP tools, discovered {len(tools)}")
    app.state.agent = build_agent(tools)
    yield
    del app.state.agent


app = FastAPI(title="AI Agent Lab", version="0.3.0", lifespan=lifespan)


class InvestigationRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


class ToolMetric(BaseModel):
    status: str
    attempts: int
    duration_ms: float


class InvestigationResponse(BaseModel):
    incident_id: str
    status: str
    missing_evidence: list[str]
    llm_rounds: int
    tool_metrics: dict[str, ToolMetric]
    duration_ms: float
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/investigate", response_model=InvestigationResponse)
async def investigate_incident(payload: InvestigationRequest, request: Request):
    return await investigate(request.app.state.agent, payload.incident_id, payload.question)
