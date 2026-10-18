"""Coordinate verified graph entities and deterministic diagnostic checks."""
import json
from collections.abc import Callable
from app.diagnostics.engine import DiagnosticEngine
from app.knowledge.graph import KnowledgeGraph
from app.knowledge.models import Investigation
from app.knowledge.repository import KnowledgeRepository


class InvestigationOrchestrator:
    def __init__(self, graph: KnowledgeGraph, engine: DiagnosticEngine,
                 repository: KnowledgeRepository):
        self.graph, self.engine, self.repository = graph, engine, repository

    def investigate(self, incident_id: str, entity_id: str,
                    checks: dict[str, Callable[[str], bool | None]]) -> Investigation:
        entity = self.graph.get_entity(entity_id)
        if entity is None:
            result = Investigation(incident_id, entity_id, "entity_unverified",
                                   ("Entity not verified by an authoritative source",))
        else:
            status, findings, playbook_id = self.engine.evaluate(
                entity_id, entity.kind, checks)
            result = Investigation(incident_id, entity_id, status, findings, playbook_id)
        with self.repository.connect() as db:
            db.execute(
                "INSERT INTO investigations VALUES (?,?,?,?,?) "
                "ON CONFLICT(incident_id) DO UPDATE SET entity_id=excluded.entity_id,"
                "status=excluded.status,findings=excluded.findings,playbook_id=excluded.playbook_id",
                (result.incident_id, result.entity_id, result.status,
                 json.dumps(result.findings), result.playbook_id),
            )
        return result
