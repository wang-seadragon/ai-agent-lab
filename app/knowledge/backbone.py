"""Persistent, fail-closed diagnostic knowledge backbone.

The graph starts empty. An engineer must approve a playbook before it can
be executed. This module does not treat a matching symptom as causal proof.
"""
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Investigation:
    incident_id: str
    entity_id: str
    status: str
    findings: tuple[str, ...]
    playbook_id: str | None = None


class KnowledgeBackbone:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dependencies (
                    source_id TEXT NOT NULL REFERENCES entities(entity_id),
                    target_id TEXT NOT NULL REFERENCES entities(entity_id),
                    PRIMARY KEY (source_id, target_id)
                );
                CREATE TABLE IF NOT EXISTS playbooks (
                    playbook_id TEXT PRIMARY KEY,
                    entity_kind TEXT NOT NULL,
                    check_name TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('proposed','approved')),
                    version INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS investigations (
                    incident_id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    findings TEXT NOT NULL,
                    playbook_id TEXT
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    playbook_id TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER NOT NULL
                );
            """)

    def register_verified_entity(self, entity_id: str, kind: str, *, verified: bool = False):
        """Only an authoritative connector should supply verified=True."""
        if not verified:
            raise ValueError("Entity registration requires authoritative verification")
        if not entity_id or not kind:
            raise ValueError("Entity ID and kind are required")
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO entities VALUES (?, ?)", (entity_id, kind))

    def add_dependency(self, source_id: str, target_id: str):
        with self._connect() as db:
            db.execute("INSERT INTO dependencies VALUES (?, ?)", (source_id, target_id))

    def propose_playbook(self, playbook_id: str, entity_kind: str, check_name: str):
        if not all((playbook_id, entity_kind, check_name)):
            raise ValueError("Playbook fields are required")
        with self._connect() as db:
            db.execute(
                "INSERT INTO playbooks(playbook_id,entity_kind,check_name,state) VALUES (?,?,?,'proposed')",
                (playbook_id, entity_kind, check_name),
            )

    def approve_playbook(self, playbook_id: str, reviewer: str, available_checks: set[str]):
        if not reviewer:
            raise ValueError("Reviewer identity required")
        with self._connect() as db:
            row = db.execute("SELECT * FROM playbooks WHERE playbook_id=?", (playbook_id,)).fetchone()
            if row is None or row["state"] != "proposed":
                raise ValueError("Playbook must exist and be proposed")
            if row["check_name"] not in available_checks:
                raise ValueError("Unregistered diagnostic check")
            db.execute("UPDATE playbooks SET state='approved' WHERE playbook_id=?", (playbook_id,))
            db.execute("INSERT INTO approvals(playbook_id,reviewer,version) VALUES (?,?,?)",
                       (playbook_id, reviewer, row["version"]))

    def investigate(self, incident_id: str, entity_id: str,
                    checks: dict[str, Callable[[str], bool | None]]) -> Investigation:
        """Run approved checks only; None means inconclusive, never confirmed."""
        with self._connect() as db:
            entity = db.execute("SELECT kind FROM entities WHERE entity_id=?", (entity_id,)).fetchone()
            if entity is None:
                result = Investigation(incident_id, entity_id, "entity_unverified",
                                       ("Entity not verified by an authoritative source",))
            else:
                playbooks = db.execute(
                    "SELECT playbook_id,check_name FROM playbooks "
                    "WHERE entity_kind=? AND state='approved' ORDER BY playbook_id",
                    (entity["kind"],),
                ).fetchall()
                if not playbooks:
                    result = Investigation(incident_id, entity_id, "needs_engineer_review",
                                           ("No approved diagnostic playbook applies",))
                else:
                    findings = []
                    matches = []
                    for playbook in playbooks:
                        name = playbook["check_name"]
                        if name not in checks:
                            findings.append(f"{name}: unavailable")
                            continue
                        try:
                            outcome = checks[name](entity_id)
                        except Exception as exc:
                            findings.append(f"{name}: check failed ({type(exc).__name__})")
                            continue
                        if outcome is True:
                            matches.append(playbook["playbook_id"])
                            findings.append(f"{name}: conditions matched")
                        elif outcome is False:
                            findings.append(f"{name}: conditions not matched")
                        else:
                            findings.append(f"{name}: inconclusive")
                    # Matching a rule is not confirmation of the ultimate root cause.
                    status = "pattern_matched" if matches else "needs_engineer_review"
                    result = Investigation(incident_id, entity_id, status, tuple(findings),
                                           matches[0] if matches else None)
            db.execute(
                "INSERT INTO investigations VALUES (?,?,?,?,?) "
                "ON CONFLICT(incident_id) DO UPDATE SET entity_id=excluded.entity_id,"
                "status=excluded.status,findings=excluded.findings,playbook_id=excluded.playbook_id",
                (result.incident_id, result.entity_id, result.status,
                 json.dumps(result.findings), result.playbook_id),
            )
            return result
