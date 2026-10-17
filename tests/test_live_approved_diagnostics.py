"""Live diagnostics remain gated by verified inventory identity."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api import main
from app.knowledge.models import VerifiedEntity


def _request(orchestrator=object()):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        agent=object(), knowledge_graph=object(),
        diagnostic_orchestrator=orchestrator, diagnostic_checks={})))


def test_verified_entity_triggers_diagnostics(monkeypatch):
    run = AsyncMock(return_value={"status": "complete"})
    diagnostic = AsyncMock(return_value="\nApproved diagnostic findings: inconclusive")
    monkeypatch.setattr(main, "investigate", run)
    monkeypatch.setattr(main, "verify_and_ingest_entity",
                        AsyncMock(return_value=VerifiedEntity("svc", "service")))
    monkeypatch.setattr(main, "approved_diagnostic_context", diagnostic)
    payload = main.InvestigationRequest(
        incident_id="INC-1", question="Investigate", entity_id="svc")
    asyncio.run(main.investigate_incident(payload, _request()))
    diagnostic.assert_awaited_once()
    assert "inconclusive" in run.await_args.args[2]


def test_unknown_entity_skips_diagnostics(monkeypatch):
    run = AsyncMock(return_value={"status": "complete"})
    diagnostic = AsyncMock()
    monkeypatch.setattr(main, "investigate", run)
    monkeypatch.setattr(main, "verify_and_ingest_entity", AsyncMock(return_value=None))
    monkeypatch.setattr(main, "approved_diagnostic_context", diagnostic)
    payload = main.InvestigationRequest(
        incident_id="INC-2", question="Investigate", entity_id="unknown")
    asyncio.run(main.investigate_incident(payload, _request()))
    diagnostic.assert_not_awaited()
    run.assert_awaited_once()


def test_diagnostic_failure_keeps_evidence_investigation(monkeypatch):
    run = AsyncMock(return_value={"status": "complete"})
    monkeypatch.setattr(main, "investigate", run)
    monkeypatch.setattr(main, "verify_and_ingest_entity",
                        AsyncMock(return_value=VerifiedEntity("svc", "service")))
    monkeypatch.setattr(main, "approved_diagnostic_context",
                        AsyncMock(side_effect=RuntimeError("unavailable")))
    payload = main.InvestigationRequest(
        incident_id="INC-3", question="Investigate", entity_id="svc")
    asyncio.run(main.investigate_incident(payload, _request()))
    assert "no check result is asserted" in run.await_args.args[2]
