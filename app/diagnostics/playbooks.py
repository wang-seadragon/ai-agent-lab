"""Playbook registry: proposed rules cannot run until reviewed."""
from app.knowledge.repository import KnowledgeRepository


class DiagnosticPlaybookRegistry:
    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    def propose(self, playbook_id: str, entity_kind: str, check_name: str):
        if not all((playbook_id, entity_kind, check_name)):
            raise ValueError("All playbook fields are required")
        with self.repository.connect() as db:
            db.execute(
                "INSERT INTO playbooks(playbook_id,entity_kind,check_name,state) "
                "VALUES (?,?,?,'proposed')", (playbook_id, entity_kind, check_name),
            )

    def approved_for_kind(self, entity_kind: str) -> list[tuple[str, str]]:
        with self.repository.connect() as db:
            rows = db.execute(
                "SELECT playbook_id,check_name FROM playbooks "
                "WHERE entity_kind=? AND state='approved' ORDER BY playbook_id",
                (entity_kind,),
            ).fetchall()
        return [(row["playbook_id"], row["check_name"]) for row in rows]
