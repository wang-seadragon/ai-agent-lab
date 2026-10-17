import pytest

from app.knowledge.graph import KnowledgeGraph
from app.knowledge.mcp_verifier import MCPInventoryVerifier
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.verification import VerifiedGraphIngestor


@pytest.fixture
def graph(tmp_path):
    return KnowledgeGraph(KnowledgeRepository(tmp_path / "knowledge.db"))


def test_authoritative_inventory_result_is_ingested(graph):
    verifier = MCPInventoryVerifier(
        lambda entity_id: {"entity_id": entity_id, "kind": "pipeline", "verified": True},
        "trusted-inventory",
    )
    result = VerifiedGraphIngestor(graph, verifier).verify_and_store("pipeline-1")
    assert result == graph.get_entity("pipeline-1")


@pytest.mark.parametrize("record", [
    None,
    {"entity_id": "pipeline-1", "kind": "pipeline"},
    {"entity_id": "pipeline-1", "kind": "pipeline", "verified": "true"},
    {"entity_id": "other", "kind": "pipeline", "verified": True},
    {"entity_id": "pipeline-1", "verified": True},
])
def test_unverified_inventory_results_cannot_create_entities(graph, record):
    verifier = MCPInventoryVerifier(lambda _: record, "trusted-inventory")
    assert VerifiedGraphIngestor(graph, verifier).verify_and_store("pipeline-1") is None
    assert graph.get_entity("pipeline-1") is None


def test_lookup_errors_fail_closed(graph):
    def broken_lookup(_):
        raise ConnectionError("Inventory unavailable")

    ingestor = VerifiedGraphIngestor(
        graph, MCPInventoryVerifier(broken_lookup, "trusted-inventory"))
    with pytest.raises(ConnectionError):
        ingestor.verify_and_store("pipeline-1")
    assert graph.get_entity("pipeline-1") is None
