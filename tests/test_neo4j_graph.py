"""Run with NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD and neo4j installed."""
import os
import uuid
import pytest
from app.knowledge.graph import KnowledgeGraph
from app.knowledge.models import Relationship, VerifiedEntity
from app.knowledge.neo4j_repository import Neo4jRepository


@pytest.fixture
def graph():
    pytest.importorskip("neo4j")
    if not os.getenv("NEO4J_URI"):
        pytest.skip("Set NEO4J_URI to run Neo4j integration tests")
    repository = Neo4jRepository.connect(
        os.environ["NEO4J_URI"], os.getenv("NEO4J_USER", "neo4j"),
        os.environ["NEO4J_PASSWORD"],
    )
    repository.initialize()
    try:
        yield KnowledgeGraph(repository)
    finally:
        repository.close()


def test_typed_relationship_and_reverse_traversal(graph):
    suffix = uuid.uuid4().hex
    spark, db = f"spark-{suffix}", f"db-{suffix}"
    graph.add_entity(VerifiedEntity(spark, "pipeline"), verified=True)
    graph.add_entity(VerifiedEntity(db, "database"), verified=True)
    graph.add_relationship(Relationship(spark, db, "WRITES_TO"))
    assert graph.get_dependencies(spark, relationship_type="WRITES_TO") == [
        VerifiedEntity(db, "database")]
    assert graph.get_dependents(db, relationship_type="WRITES_TO") == [
        VerifiedEntity(spark, "pipeline")]


def test_unknown_endpoint_fails_closed(graph):
    suffix = uuid.uuid4().hex
    source = f"source-{suffix}"
    graph.add_entity(VerifiedEntity(source, "service"), verified=True)
    with pytest.raises(ValueError):
        graph.add_relationship(Relationship(source, f"missing-{suffix}", "DEPENDS_ON"))
