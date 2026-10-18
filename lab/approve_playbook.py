"""Explicit local-lab engineer approval; never automatically run on startup."""
import argparse
from app.knowledge.repository import KnowledgeRepository
from app.diagnostics.playbooks import DiagnosticPlaybookRegistry
from app.reviews.service import KnowledgeReviewService

PLAYBOOK = "lab-high-ingestion-lag"
CHECK = "mcp_ingestion_lag"


def main():
    parser = argparse.ArgumentParser(description="Approve synthetic lab diagnostic")
    parser.add_argument("--db", required=True, help="Local SQLite path")
    parser.add_argument("--reviewer", required=True, help="Actual approving engineer identity")
    args = parser.parse_args()
    store = KnowledgeRepository(args.db)
    registry = DiagnosticPlaybookRegistry(store)
    with store.connect() as db:
        row = db.execute("SELECT state,entity_kind,check_name FROM playbooks WHERE playbook_id=?",
                         (PLAYBOOK,)).fetchone()
    if row is None:
        registry.propose(PLAYBOOK, "pipeline", CHECK)
    elif row["entity_kind"] != "pipeline" or row["check_name"] != CHECK:
        raise SystemExit("Existing playbook definition differs; refusing to modify")
    elif row["state"] == "approved":
        raise SystemExit("Playbook already approved; no change made")
    print(f"Proposed playbook {PLAYBOOK}: pipeline / {CHECK}")
    confirmation = input("Review the check and type APPROVE to authorize this lab playbook: ")
    if confirmation != "APPROVE":
        raise SystemExit("Approval cancelled; playbook remains proposed")
    KnowledgeReviewService(store).approve(PLAYBOOK, args.reviewer, {CHECK})
    print(f"Approved {PLAYBOOK} by {args.reviewer} in {args.db}")


if __name__ == "__main__":
    main()
