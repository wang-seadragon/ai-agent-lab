"""Endpoint tests use fake inventory and graph; no LLM or Neo4j required."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api import main
from app.knowledge.models import VerifiedEntity


def test_verified_entity_is_passed_as_identity_only(monkeypatch):
    agent = object()
    fake_investigate = AsyncMock(return_value={"status": "complete"})
    verify = AsyncMock(return_value=VerifiedEntity("svc-1", "service"))
    monkeypatch.setattr(main, "investigate", fake_investigate)
    monkeypatch.setattr(main, "verify_and_ingest_entity", verify)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        agent=agent, knowledge_graph=object())))
    payload = main.InvestigationRequest(
        incident_id="INC-1", question="What happened?", entity_id="svc-1")
    asyncio.run(main.investigate_incident(payload, request))
    verify.assert_awaited_once()
    question = fake_investigate.await_args.args[2]
    assert "verified entity ID: svc-1" in question
    assert "not dependencies" in question


def test_unknown_entity_still_runs_evidence_investigation(monkeypatch):
    fake_investigate = AsyncMock(return_value={"status": "complete"})
    monkeypatch.setattr(main, "investigate", fake_investigate)
    monkeypatch.setattr(main, "verify_and_ingest_entity",
                        AsyncMock(return_value=None))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        agent=object(), knowledge_graph=object())))
    payload = main.InvestigationRequest(
        incident_id="INC-2", question="Investigate", entity_id="unknown")
    asyncio.run(main.investigate_incident(payload, request))
    assert "not verified" in fake_investigate.await_args.args[2]


def test_inventory_failure_still_runs_evidence_investigation(monkeypatch):
    fake_investigate = AsyncMock(return_value={"status": "complete"})
    monkeypatch.setattr(main, "investigate", fake_investigate)
    monkeypatch.setattr(main, "verify_and_ingest_entity",
                        AsyncMock(side_effect=main.InventoryLookupError("down")))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        agent=object(), knowledge_graph=object())))
    payload = main.InvestigationRequest(
        incident_id="INC-3", question="Investigate", entity_id="svc-1")
    asyncio.run(main.investigate_incident(payload, request))
    assert "not verified" in fake_investigate.await_args.args[2]


def test_disabled_inventory_never_attempts_lookup(monkeypatch):
    fake_investigate = AsyncMock(return_value={"status": "complete"})
    verify = AsyncMock()
    monkeypatch.setattr(main, "investigate", fake_investigate)
    monkeypatch.setattr(main, "verify_and_ingest_entity", verify)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        agent=object(), knowledge_graph=None)))
    payload = main.InvestigationRequest(
        incident_id="INC-4", question="Investigate", entity_id="svc-1")
    asyncio.run(main.investigate_incident(payload, request))
    verify.assert_not_awaited()
    assert "unverified" in fake_investigate.await_args.args[2]
