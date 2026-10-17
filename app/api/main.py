"""FastAPI application; discover MCP tools and compile graph at startup."""
from contextlib import asynccontextmanager
import logging
import asyncio
import os

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from app.agents.single_agent import build_agent, investigate
from app.mcp_client import create_mcp_client
from app.investigations.live_diagnostics import make_diagnostic_orchestrator, approved_diagnostic_context
from app.diagnostics.mcp_metrics_check import fetch_lag_evidence, lag_check_from_evidence
from app.knowledge.graph import KnowledgeGraph
from app.knowledge.neo4j_repository import Neo4jRepository
from app.knowledge.mcp_inventory_client import verify_and_ingest_entity, InventoryLookupError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = create_mcp_client()
    tools = await client.get_tools()
    app.state.agent = build_agent(tools)
    app.state.knowledge_graph = None
    app.state.graph_repository = None
    app.state.diagnostic_orchestrator = None
    app.state.diagnostic_checks = {}
    if os.getenv("ENABLE_INVENTORY_GRAPH", "false").lower() == "true":
        if not os.getenv("INVENTORY_MCP_URL"):
            raise RuntimeError("INVENTORY_MCP_URL required when inventory graph enabled")
        required = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")
        if any(not os.getenv(name) for name in required):
            raise RuntimeError("Neo4j connection variables are required")
        repo = Neo4jRepository.connect(
            os.environ["NEO4J_URI"], os.environ["NEO4J_USER"],
            os.environ["NEO4J_PASSWORD"])
        try:
            repo.initialize()
        except Exception:
            repo.close()
            raise
        app.state.graph_repository = repo
        app.state.knowledge_graph = KnowledgeGraph(repo)
        if os.getenv('ENABLE_APPROVED_DIAGNOSTICS') == 'true':
            path = os.getenv('KNOWLEDGE_SQLITE_PATH')
            if not path:
                repo.close()
                raise RuntimeError('KNOWLEDGE_SQLITE_PATH required')
            app.state.diagnostic_orchestrator = make_diagnostic_orchestrator(
                app.state.knowledge_graph, path)
    try:
        yield
    finally:
        if app.state.graph_repository is not None:
            app.state.graph_repository.close()
        del app.state.agent


app = FastAPI(title="AI Agent Lab", version="0.6.0", lifespan=lifespan)


class InvestigationRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    entity_id: str | None = Field(default=None, min_length=1)


class ToolMetric(BaseModel):
    status: str
    attempts: int
    duration_ms: float


class ToolError(BaseModel):
    tool: str
    error_type: str
    message: str
    attempts: int


class InvestigationResponse(BaseModel):
    incident_id: str
    status: str
    missing_evidence: list[str]
    llm_rounds: int
    tool_metrics: dict[str, ToolMetric]
    tool_errors: list[ToolError]
    duration_ms: float
    answer: str
    root_cause_confirmed: bool
    suspected_root_cause: str | None
    confidence: str | None
    diagnostic_missing_evidence: list[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/investigate", response_model=InvestigationResponse)
async def investigate_incident(payload: InvestigationRequest, request: Request):
    question = payload.question
    entity = None
    graph = getattr(request.app.state, "knowledge_graph", None)
    if payload.entity_id and graph is not None:
        try:
            entity = await verify_and_ingest_entity(payload.entity_id, graph)
        except (InventoryLookupError, ValueError):
            logging.getLogger(__name__).warning(
                "Inventory verification unavailable or invalid for incident=%s",
                payload.incident_id,
            )
            entity = None
        if entity is None:
            question += (
                "\\nInventory verification: the requested entity ID was not verified. "
                "Do not assume it exists or infer any topology from it."
            )
        else:
            question += (
                f"\\nAuthoritative inventory verified entity ID: {entity.entity_id}; "
                f"kind: {entity.kind}. This verifies identity only, not dependencies, "
                "health, causation, or root cause."
            )
    elif payload.entity_id:
        question += (
            "\\nInventory verification is disabled. Treat the supplied entity ID "
            "as unverified and do not infer topology from it."
        )
    if entity is not None:
        try:
            checks = dict(getattr(request.app.state, "diagnostic_checks", {}))
            if (getattr(request.app.state, "diagnostic_orchestrator", None) is not None
                    and os.getenv("ENABLE_MCP_LAG_CHECK") == "true"):
                # Existing MCP metrics server currently uses SIMULATED data.
                # Explicit opt-in must only be used for development until the
                # metrics backend is replaced by an authoritative provider.
                threshold = float(os.environ["MCP_LAG_THRESHOLD_MINUTES"])
                url = os.environ["DIAGNOSTIC_METRICS_MCP_URL"]
                outcome = await fetch_lag_evidence(
                    payload.incident_id, entity.entity_id, threshold, url)
                checks["mcp_ingestion_lag"] = lag_check_from_evidence(
                    entity.entity_id, entity.entity_id, outcome)
            question += await approved_diagnostic_context(
                getattr(request.app.state, "diagnostic_orchestrator", None),
                payload.incident_id, entity,
                checks,
            )
        except Exception:
            logging.getLogger(__name__).exception("Approved diagnostics unavailable")
            question += "\\nApproved diagnostics unavailable; no check result is asserted."
    return await investigate(request.app.state.agent, payload.incident_id, question)
