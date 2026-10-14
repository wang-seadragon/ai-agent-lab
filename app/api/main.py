"""FastAPI application; discover MCP tools and compile graph at startup."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from app.agents.single_agent import build_agent, investigate
from app.mcp_client import create_mcp_client
import logging

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


app = FastAPI(title="AI Agent Lab", version="0.2.0", lifespan=lifespan)


class InvestigationRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/investigate")
async def investigate_incident(payload: InvestigationRequest, request: Request):
    answer = await investigate(request.app.state.agent, payload.incident_id, payload.question)
    return {"incident_id": payload.incident_id, "answer": answer}
