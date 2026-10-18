"""Optional approved diagnostic evaluation for a verified inventory entity.

Check implementations must be explicitly registered by trusted application code.
This module does not create checks or grant playbook approval.
"""
import asyncio

from app.diagnostics.engine import DiagnosticEngine
from app.diagnostics.playbooks import DiagnosticPlaybookRegistry
from app.investigations.orchestrator import InvestigationOrchestrator
from app.knowledge.repository import KnowledgeRepository


def make_diagnostic_orchestrator(graph, sqlite_path):
    store = KnowledgeRepository(sqlite_path)
    return InvestigationOrchestrator(
        graph, DiagnosticEngine(DiagnosticPlaybookRegistry(store)), store
    )


async def approved_diagnostic_context(orchestrator, incident_id, entity, checks):
    """Evaluate approved checks without treating a match as a root cause."""
    if entity is None or orchestrator is None:
        return ""
    result = await asyncio.to_thread(
        orchestrator.investigate, incident_id, entity.entity_id, checks
    )
    return (
        "\nApproved diagnostic findings (not proof of causation): "
        f"status={result.status}; findings={list(result.findings)}; "
        f"matched_playbook={result.playbook_id!r}. "
        "A matching pattern does not confirm root cause."
    )
