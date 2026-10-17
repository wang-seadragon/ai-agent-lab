"""SQLite persistence shared by graph, diagnostics, and review services."""
import sqlite3
from pathlib import Path


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
