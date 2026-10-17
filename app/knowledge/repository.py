"""SQLite persistence for playbooks, reviews, investigations, and local graph tests."""
import sqlite3
from pathlib import Path
from app.knowledge.models import Relationship, VerifiedEntity


class KnowledgeRepository:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY, kind TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dependencies (
                    source_id TEXT NOT NULL REFERENCES entities(entity_id),
                    target_id TEXT NOT NULL REFERENCES entities(entity_id),
                    PRIMARY KEY(source_id,target_id));
                CREATE TABLE IF NOT EXISTS graph_relationships (
                    source_id TEXT NOT NULL REFERENCES entities(entity_id),
                    target_id TEXT NOT NULL REFERENCES entities(entity_id),
                    relationship_type TEXT NOT NULL,
                    PRIMARY KEY(source_id,target_id,relationship_type));
                CREATE TABLE IF NOT EXISTS playbooks (
                    playbook_id TEXT PRIMARY KEY,
                    entity_kind TEXT NOT NULL, check_name TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('proposed','approved')),
                    version INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS approvals (
                    playbook_id TEXT NOT NULL REFERENCES playbooks(playbook_id),
                    reviewer TEXT NOT NULL,
                    approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS investigations (
                    incident_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL,
                    status TEXT NOT NULL, findings TEXT NOT NULL,
                    playbook_id TEXT);
            """)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    # SQLite graph adapter for lightweight unit tests and backwards compatibility.
    # Production graph storage uses Neo4jRepository.
    def upsert_entity(self, entity: VerifiedEntity) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO entities(entity_id,kind) VALUES (?,?) "
                       "ON CONFLICT(entity_id) DO UPDATE SET kind=excluded.kind",
                       (entity.entity_id, entity.kind))

    def get_entity(self, entity_id: str) -> VerifiedEntity | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM entities WHERE entity_id=?",
                             (entity_id,)).fetchone()
        return VerifiedEntity(row["entity_id"], row["kind"]) if row else None

    def add_relationship(self, relationship: Relationship) -> None:
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO graph_relationships VALUES (?,?,?)",
                       (relationship.source_id, relationship.target_id,
                        relationship.relationship_type))

    def get_related(self, entity_id: str, *, direction: str = "outgoing",
                    relationship_type: str | None = None) -> list[VerifiedEntity]:
        if direction not in {"outgoing", "incoming"}:
            raise ValueError("Invalid direction")
        source, target = ("source_id", "target_id") if direction == "outgoing" else ("target_id", "source_id")
        with self.connect() as db:
            rows = db.execute(
                f"SELECT DISTINCT e.entity_id,e.kind FROM graph_relationships r "
                f"JOIN entities e ON e.entity_id=r.{target} "
                f"WHERE r.{source}=? AND (? IS NULL OR r.relationship_type=?) "
                f"ORDER BY e.entity_id",
                (entity_id, relationship_type, relationship_type),
            ).fetchall()
        return [VerifiedEntity(row["entity_id"], row["kind"]) for row in rows]
