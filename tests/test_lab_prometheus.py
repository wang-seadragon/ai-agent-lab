import json

from app.telemetry.lab_prometheus import fetch_lab_metrics


class Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return json.dumps(self.payload).encode()


def sample(value="25", pipeline="lab-orders"):
    return {"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": {"pipeline": pipeline, "incident_id": "LAB-INC-1"},
         "value": [1234567890, value]}]}}


def test_real_prometheus_shape():
    observed = {}
    def opener(url, timeout):
        observed["url"] = url
        return Response(sample())
    result = fetch_lab_metrics("LAB-INC-1", opener=opener)
    assert result["ingestion_lag_minutes"] == 25
    assert result["environment"] == "lab"
    assert "/api/v1/query?" in observed["url"]


def test_unknown_incident_does_not_query():
    def never(*args, **kwargs):
        raise AssertionError("must not query")
    assert fetch_lab_metrics("INC-OTHER", opener=never)["error"] == "lab_incident_not_found"


def test_missing_or_mismatched_evidence_is_not_a_measurement():
    for payload in (sample(pipeline="unknown"),
                    {"status": "success", "data": {"resultType": "vector", "result": []}},
                    sample(value="NaN")):
        assert fetch_lab_metrics(
            "LAB-INC-1", opener=lambda *args, p=payload, **kwargs: Response(p)
        )["error"] == "lab_metrics_unavailable"


def test_lab_adapter_rejects_remote_endpoint():
    result = fetch_lab_metrics("LAB-INC-1", endpoint="https://external.example")
    assert result["error"] == "invalid_lab_endpoint"
