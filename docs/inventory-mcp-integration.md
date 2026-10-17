# Dedicated inventory verification → KnowledgeGraph

`verify_and_ingest_entity(entity_id, graph)` connects a dedicated MCP inventory
tool to the existing `MCPInventoryVerifier` and `VerifiedGraphIngestor`.
It is **not** registered in the LLM's MCP tool list.

Configuration:
- Run the inventory server with `INVENTORY_FILE` pointing to a real operator-controlled snapshot.
- Set `INVENTORY_MCP_URL=http://127.0.0.1:8104/mcp` for the trusted backend process.
- Construct `KnowledgeGraph(Neo4jRepository.connect(...))` and initialize Neo4j.
- Call `await verify_and_ingest_entity(candidate_id, graph)` from trusted backend code.

Unknown/mismatched/unverified IDs return `None` and are not persisted.
Unavailable or invalid inventory responses raise `InventoryLookupError`;
no graph write occurs. There is no LLM fallback.

**Security limitation:** URL configuration and a structured response are not
sufficient authentication of an authoritative source. Deploy only with a
trusted localhost/private transport and access controls until authenticated
MCP transport, source provenance and audit logging are implemented.
The production FastAPI investigation route is intentionally unchanged; do
not enable untrusted clients to invoke graph writes. Graph relationships
must also be independently verified before insertion.

Run `pytest -q tests/test_mcp_inventory_client.py` and
`pytest -q tests/test_inventory_neo4j_integration.py` (with Neo4j configured).
