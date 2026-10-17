"""Optional real-Neo4j test. Requires configured local Neo4j and explicit opt-in."""
import asyncio
import json
import os
import uuid

import pytest

from app.knowledge.graph import KnowledgeGraph
from app.knowledge.neo4j_repository import Neo4jRepository
from app.knowledge.mcp_inventory_client import verify_and_ingest_entity


@pytest.mark.skipif(not os.getenv("NEO4J_URI"),
                    reason="Set NEO4J_URI to run the real Neo4j integration")
def test_verified_inventory_entity_reaches_neo4j():
    class InventoryTool:
        name = "verify_inventory_entity_mcp"
        async def ainvoke(self, args):
            return json.dumps({"entity_id": args["entity_id"],
                               "kind": "service", "verified": True})

    class Client:
        async def get_tools(self):
            return [InventoryTool()]

    repo = Neo4jRepository.connect(
        os.environ["NEO4J_URI"], os.getenv("NEO4J_USER", "neo4j"),
        os.environ["NEO4J_PASSWORD"])
    try:
        repo.initialize()
        graph = KnowledgeGraph(repo)
        entity_id = "inventory-test-" + uuid.uuid4().hex
        result = asyncio.run(verify_and_ingest_entity(
            entity_id, graph, client=Client()))
        assert graph.get_entity(entity_id) == result
    finally:
        repo.close()
