import asyncio
import json

from app.diagnostics.mcp_metrics_check import (
    fetch_lag_evidence, parse_metrics, lag_check_from_evidence,
)


class Tool:
    name = "get_incident_metrics_mcp"
    def __init__(self, data):
        self.data = data
    async def ainvoke(self, args):
        return json.dumps(self.data)


class Client:
    def __init__(self, data):
        self.data = data
    async def get_tools(self):
        return [Tool(self.data)]


def test_exact_incident_and_entity_required():
    data = {"incident_id": "INC-1", "pipeline": "orders",
            "ingestion_lag_minutes": 24}
    assert parse_metrics(data, "INC-1", "orders", 20) is True
    assert parse_metrics(data, "INC-2", "orders", 20) is None
    assert parse_metrics(data, "INC-1", "other", 20) is None
    assert parse_metrics(data, "INC-1", "orders", 25) is False


def test_missing_invalid_or_error_evidence_is_inconclusive():
    base = {"incident_id": "INC-1", "pipeline": "orders"}
    for lag in (None, True, "24", -1, float("inf")):
        assert parse_metrics(dict(base, ingestion_lag_minutes=lag),
                             "INC-1", "orders", 20) is None
    assert parse_metrics({"error": "not found"}, "INC-1", "orders", 20) is None
    assert parse_metrics("bad-json", "INC-1", "orders", 20) is None


def test_dedicated_mcp_tool_and_no_inferred_entity_mapping():
    data = {"incident_id": "INC-1", "pipeline": "orders",
            "ingestion_lag_minutes": 24}
    result = asyncio.run(fetch_lag_evidence(
        "INC-1", "orders", 20, "http://localhost:8101/mcp",
        client=Client(data)))
    assert result is True
    assert lag_check_from_evidence("orders", "orders", result)("other") is None
    assert lag_check_from_evidence("orders", "orders", result)("orders") is True


def test_mcp_error_fails_closed():
    class BadClient:
        async def get_tools(self):
            raise ConnectionError("down")
    assert asyncio.run(fetch_lag_evidence(
        "INC-1", "orders", 20, "http://localhost:8101/mcp",
        client=BadClient())) is None
