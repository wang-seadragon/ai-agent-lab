"""Verified entity topology; no incident investigation logic."""
from app.knowledge.models import Relationship, VerifiedEntity
from app.knowledge.repository import KnowledgeRepository


class KnowledgeGraph:
    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    def add_entity(self, entity: VerifiedEntity, *, verified: bool = False):
        # Future connector boundary must authenticate and enforce verification.
        if not verified:
            raise ValueError("Authoritative verification is required")
        if not entity.entity_id or not entity.kind:
            raise ValueError("Entity ID and kind are required")
        with self.repository.connect() as db:
            db.execute("INSERT INTO entities VALUES (?,?) ON CONFLICT(entity_id) "
                       "DO UPDATE SET kind=excluded.kind", (entity.entity_id, entity.kind))

    def get_entity(self, entity_id: str) -> VerifiedEntity | None:
        with self.repository.connect() as db:
            row = db.execute("SELECT * FROM entities WHERE entity_id=?", (entity_id,)).fetchone()
        return VerifiedEntity(row["entity_id"], row["kind"]) if row else None

    def add_relationship(self, relationship: Relationship):
        with self.repository.connect() as db:
            db.execute("INSERT INTO dependencies VALUES (?,?)",
                       (relationship.source_id, relationship.target_id))

    def get_dependencies(self, entity_id: str) -> list[VerifiedEntity]:
        with self.repository.connect() as db:
            rows = db.execute(
                "SELECT e.entity_id,e.kind FROM dependencies d JOIN entities e "
                "ON e.entity_id=d.target_id WHERE d.source_id=? ORDER BY e.entity_id",
                (entity_id,),
            ).fetchall()
        return [VerifiedEntity(row["entity_id"], row["kind"]) for row in rows]
