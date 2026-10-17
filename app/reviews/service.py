"""Engineer approval gate; requires known executable check."""
from app.knowledge.repository import KnowledgeRepository


class KnowledgeReviewService:
    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    def approve(self, playbook_id: str, reviewer: str, available_checks: set[str]):
        if not reviewer:
            raise ValueError("Reviewer identity required")
        with self.repository.connect() as db:
            row = db.execute("SELECT * FROM playbooks WHERE playbook_id=?",
                             (playbook_id,)).fetchone()
            if row is None or row["state"] != "proposed":
                raise ValueError("Playbook must exist and be proposed")
            if row["check_name"] not in available_checks:
                raise ValueError("Unregistered diagnostic check")
            db.execute("UPDATE playbooks SET state='approved' WHERE playbook_id=?",
                       (playbook_id,))
            db.execute("INSERT INTO approvals(playbook_id,reviewer,version) VALUES (?,?,?)",
                       (playbook_id, reviewer, row["version"]))
