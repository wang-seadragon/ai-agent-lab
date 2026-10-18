"""Lab metrics only become diagnostic findings after approval and identity verification."""
from app.diagnostics.engine import DiagnosticEngine
from app.diagnostics.playbooks import DiagnosticPlaybookRegistry
from app.diagnostics.mcp_metrics_check import parse_metrics, lag_check_from_evidence
from app.knowledge.repository import KnowledgeRepository
from app.reviews.service import KnowledgeReviewService


def test_lab_metric_requires_approval(tmp_path):
    store = KnowledgeRepository(tmp_path / "knowledge.db")
    registry = DiagnosticPlaybookRegistry(store)
    engine = DiagnosticEngine(registry)
    registry.propose("lab-high-ingestion-lag", "pipeline", "mcp_ingestion_lag")
    evidence = {"incident_id": "LAB-INC-1", "pipeline": "lab-orders",
                "ingestion_lag_minutes": 25.0, "environment": "lab"}
    outcome = parse_metrics(evidence, "LAB-INC-1", "lab-orders", 20)
    checks = {"mcp_ingestion_lag": lag_check_from_evidence("lab-orders", "lab-orders", outcome)}
    assert engine.evaluate("lab-orders", "pipeline", checks)[0] == "needs_engineer_review"
    KnowledgeReviewService(store).approve("lab-high-ingestion-lag", "test-engineer",
                                          {"mcp_ingestion_lag"})
    status, findings, playbook = engine.evaluate("lab-orders", "pipeline", checks)
    assert status == "pattern_matched"
    assert playbook == "lab-high-ingestion-lag"
    assert findings == ("mcp_ingestion_lag: conditions matched",)
    assert engine.evaluate("other", "pipeline", checks)[0] == "needs_engineer_review"


def test_wrong_incident_or_pipeline_is_inconclusive():
    evidence = {"incident_id": "LAB-INC-1", "pipeline": "lab-orders",
                "ingestion_lag_minutes": 100.0, "environment": "lab"}
    assert parse_metrics(evidence, "OTHER", "lab-orders", 20) is None
    assert parse_metrics(evidence, "LAB-INC-1", "other", 20) is None
