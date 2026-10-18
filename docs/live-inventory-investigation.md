# Opt-in inventory verification in /investigate

The FastAPI endpoint accepts optional `entity_id`. If `ENABLE_INVENTORY_GRAPH=true`,
the backend initializes Neo4j at startup and performs a **dedicated trusted**
inventory MCP lookup before starting the existing LangGraph investigation.

Configure `INVENTORY_MCP_URL`, `NEO4J_URI`, `NEO4J_USER`, and
`NEO4J_PASSWORD` in the backend environment. Start the operator-managed
inventory MCP server separately using `INVENTORY_FILE`.

Example request:
```json
{"incident_id":"INC-1001","question":"Investigate observed latency","entity_id":"<actual-inventory-id>"}
```

Verified identity is included in the investigation context with an explicit
warning that it proves **neither topology nor causation**. Unknown entities
and unavailable inventory are marked unverified; metrics/logs/runbook
investigation continues. With the feature disabled, existing API behavior
is preserved. No LLM tool receives graph-write privileges.

**Limitations:** This is an initial opt-in integration, not a production
authorization system. The supplied entity ID is caller-controlled; inventory
connector authentication, tenant isolation, provenance, auditing, safe output
handling, and independent relationship verification still need hardening.
No automatic candidate extraction or diagnostic playbook execution has been
connected to the LangGraph path yet.

Run `pytest -q tests/test_live_inventory_investigation.py` and `pytest -q`.
