# Authoritative entity verification

The LLM may suggest entity IDs, but it cannot certify that they exist.
Only a configured trusted inventory connector may return verified entities.

The new `MCPInventoryVerifier` wraps a synchronous inventory lookup returning
`{"entity_id": "...", "kind": "...", "verified": true}`.
The lookup must be a dedicated authoritative MCP inventory operation, not
an LLM, generic metrics, logs, or runbook search result. The adapter validates
the exact requested ID, kind, and verification flag; missing or malformed
records are rejected.

`VerifiedGraphIngestor` is the only recommended write path into the
`KnowledgeGraph`. The existing `verified=True` argument is still present
for compatibility and tests; it is **not** an authenticated authorization
mechanism and must not be exposed to user-controlled API inputs.

No authoritative inventory MCP tool is configured in the current application,
so automatic production ingestion is intentionally not enabled. Next step:
define the inventory MCP schema and configure the connector with a trusted
identity, authorization, timeout, and audit logging. A positive verification
result should eventually carry provenance and freshness metadata.
