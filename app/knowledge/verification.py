"""Authoritative entity verification boundary for MCP-backed topology ingestion.

A connector must be explicitly trusted by the application. The LLM is never a
verification authority; a free-form tool result is not enough to create a node.
"""
from dataclasses import dataclass
from typing import Protocol

from app.knowledge.graph import KnowledgeGraph
from app.knowledge.models import VerifiedEntity


@dataclass(frozen=True)
class EntityVerification:
    entity: VerifiedEntity
    authoritative_source: str


class EntityVerifier(Protocol):
    def verify(self, entity_id: str) -> EntityVerification | None: ...


class VerifiedGraphIngestor:
    """Only this service should write connector-verified entities to the graph."""

    def __init__(self, graph: KnowledgeGraph, verifier: EntityVerifier):
        self.graph = graph
        self.verifier = verifier

    def verify_and_store(self, entity_id: str) -> VerifiedEntity | None:
        if not entity_id or not entity_id.strip():
            raise ValueError("Entity ID is required")
        result = self.verifier.verify(entity_id)
        if result is None:
            return None
        if (not isinstance(result, EntityVerification)
                or not isinstance(result.entity, VerifiedEntity)
                or result.entity.entity_id != entity_id
                or not result.entity.kind
                or not result.authoritative_source.strip()):
            raise ValueError("Invalid authoritative entity verification response")
        self.graph.add_entity(result.entity, verified=True)
        return result.entity
