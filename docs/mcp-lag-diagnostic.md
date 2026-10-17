# MCP-backed ingestion lag diagnostic (development only)

**Important:** `app/tools.py` currently supplies hard-coded simulated
incident data. The MCP transport is real, but the data source is **not**
production telemetry. Do not enable this check for production decisions.

To use this integration in a development environment, configure the existing
inventory/Neo4j/approved-diagnostics settings, plus:

```sh
export ENABLE_MCP_LAG_CHECK=true
export DIAGNOSTIC_METRICS_MCP_URL=http://127.0.0.1:8101/mcp
export MCP_LAG_THRESHOLD_MINUTES=20
```

The value 20 above is an **illustrative operator-selected threshold**, not a
measured baseline. The caller's verified `entity_id` must match the MCP
payload's `pipeline` field exactly; the incident ID must also match. A
missing, mismatched, malformed, or unavailable response is inconclusive.

The only registered check name is `mcp_ingestion_lag`. An engineer must
separately propose and approve a playbook for the verified entity kind using
the existing review service. No automatic approval occurs. A lag threshold
match is a pattern, **not** proof of root cause.

The dedicated backend MCP client never exposes graph writes or playbook
approval to the LLM. Replace the simulated `app/tools.py` metrics backend
with authenticated telemetry before considering production deployment;
enforce tenant scope, provenance, and authorization.

Run `pytest -q tests/test_mcp_metrics_check.py` and `pytest -q`.
