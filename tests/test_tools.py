from app.tools import get_incident_logs, get_incident_metrics, get_incident_runbook


def test_metrics_fixture():
    result = get_incident_metrics.invoke({"incident_id": "INC-1001"})
    assert result["ingestion_lag_minutes"] == 24


def test_logs_fixture():
    result = get_incident_logs.invoke({"incident_id": "INC-1001"})
    assert len(result["entries"]) == 3


def test_unknown_incident():
    result = get_incident_runbook.invoke({"incident_id": "INC-UNKNOWN"})
    assert result["error"] == "Incident not found"
