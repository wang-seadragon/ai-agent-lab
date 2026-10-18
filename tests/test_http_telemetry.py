import io
import json
from urllib.error import HTTPError, URLError

from app.telemetry.http_metrics import fetch_telemetry_metrics


class Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return json.dumps(self.payload).encode()


def test_authenticated_evidence_and_incident_url_encoding():
    seen = {}
    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["timeout"] = timeout
        return Response({"incident_id": "INC/1", "pipeline": "orders",
                         "ingestion_lag_minutes": 24})
    result = fetch_telemetry_metrics(
        "INC/1", url="https://telemetry.example/incidents/{incident_id}/metrics",
        token="test-secret", opener=opener)
    assert result["ingestion_lag_minutes"] == 24
    assert "INC%2F1" in seen["url"]
    assert seen["authorization"] == "Bearer test-secret"


def test_missing_credentials_or_insecure_transport():
    assert fetch_telemetry_metrics(
        "INC", url="https://example.test/{incident_id}", token="")["error"] == "telemetry_not_configured"
    assert fetch_telemetry_metrics(
        "INC", url="http://example.test/{incident_id}", token="x")["error"] == "telemetry_requires_https"


def test_provider_mismatch_and_invalid_metrics():
    def opener(request, timeout):
        return Response({"incident_id": "OTHER", "pipeline": "orders",
                         "ingestion_lag_minutes": 24})
    result = fetch_telemetry_metrics(
        "INC", url="https://example.test/{incident_id}", token="x", opener=opener)
    assert result["error"] == "telemetry_identity_mismatch"
    def invalid(request, timeout):
        return Response({"incident_id": "INC", "pipeline": "orders",
                         "ingestion_lag_minutes": "24"})
    result = fetch_telemetry_metrics(
        "INC", url="https://example.test/{incident_id}", token="x", opener=invalid)
    assert result["error"] == "invalid_telemetry"


def test_provider_outage_fails_closed():
    def offline(request, timeout):
        raise URLError("offline")
    result = fetch_telemetry_metrics(
        "INC", url="https://example.test/{incident_id}", token="x", opener=offline)
    assert result["error"] == "telemetry_unavailable"
