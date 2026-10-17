"""Verified infrastructure topology, independent of storage backend."""
from app.knowledge.graph_repository import GraphRepository
from app.knowledge.models import Relationship, VerifiedEntity


class KnowledgeGraph:
    def __init__(self, repository: GraphRepository):
        self.repository = repository

    def add_entity(self, entity: VerifiedEntity, *, verified: bool = False):
        # Placeholder until authenticated MCP entity verification is integrated.
        if not verified:
            raise ValueError("Authoritative verification is required")
        if not entity.entity_id or not entity.kind:
            raise ValueError("Entity ID and kind are required")
        self.repository.upsert_entity(entity)

    def get_entity(self, entity_id: str) -> VerifiedEntity | None:
        return self.repository.get_entity(entity_id)

    def add_relationship(self, relationship: Relationship):
        if not self.get_entity(relationship.source_id) or not self.get_entity(relationship.target_id):
            raise ValueError("Both relationship endpoints must be verified")
        self.repository.add_relationship(relationship)

    def get_dependencies(self, entity_id: str, *,
                         relationship_type: str | None = None) -> list[VerifiedEntity]:
        return self.repository.get_related(entity_id, direction="outgoing",
                                           relationship_type=relationship_type)

    def get_dependents(self, entity_id: str, *,
                       relationship_type: str | None = None) -> list[VerifiedEntity]:
        return self.repository.get_related(entity_id, direction="incoming",
                                           relationship_type=relationship_type)
