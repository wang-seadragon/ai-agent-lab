import asyncio
import json

import pytest

from app.knowledge.graph import KnowledgeGraph
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.mcp_inventory_client import (
    InventoryLookupError, verify_and_ingest_entity,
)


class FakeTool:
    name = "verify_inventory_entity_mcp"

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    async def ainvoke(self, args):
        if self.error:
            raise self.error
        return json.dumps(self.payload)


class FakeClient:
    def __init__(self, tool):
        self.tool = tool

    async def get_tools(self):
        return [self.tool]


@pytest.fixture
def graph(tmp_path):
    return KnowledgeGraph(KnowledgeRepository(tmp_path / "knowledge.db"))


def run(graph, tool, entity_id="service-a"):
    return asyncio.run(verify_and_ingest_entity(
        entity_id, graph, client=FakeClient(tool)))


def test_verified_entity_persists(graph):
    result = run(graph, FakeTool({
        "entity_id": "service-a", "kind": "service", "verified": True}))
    assert result == graph.get_entity("service-a")


@pytest.mark.parametrize("payload", [
    {"entity_id": "service-a", "verified": False},
    {"entity_id": "service-a", "kind": "service"},
    {"entity_id": "other", "kind": "service", "verified": True},
])
def test_unknown_or_unverified_entity_is_not_persisted(graph, payload):
    assert run(graph, FakeTool(payload)) is None
    assert graph.get_entity("service-a") is None


def test_unavailable_inventory_never_writes(graph):
    with pytest.raises(InventoryLookupError):
        run(graph, FakeTool(error=ConnectionError("down")))
    assert graph.get_entity("service-a") is None


def test_invalid_tool_result_never_writes(graph):
    with pytest.raises(InventoryLookupError):
        run(graph, FakeTool({"error": "source unavailable"}))
    assert graph.get_entity("service-a") is None


def test_inventory_tool_is_required(graph):
    class WrongTool(FakeTool):
        name = "get_incident_logs_mcp"
    with pytest.raises(InventoryLookupError):
        run(graph, WrongTool({}))
    assert graph.get_entity("service-a") is None
