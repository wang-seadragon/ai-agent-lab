# Authenticated telemetry backend

The metrics MCP server supports two explicit backends:

- `METRICS_BACKEND=simulated` (default): existing demonstration fixture
- `METRICS_BACKEND=http`: authenticated, read-only HTTPS provider

Example configuration for a compatible customer telemetry API:

```sh
export METRICS_BACKEND=http
export TELEMETRY_METRICS_URL='https://telemetry.example/api/incidents/{incident_id}/metrics'
export TELEMETRY_API_TOKEN='<read-only service token>'
```

The provider endpoint must return JSON with exact `incident_id`,
`pipeline`, and numeric nonnegative `ingestion_lag_minutes`.
The URL template must contain exactly one `{incident_id}` placeholder.
The adapter percent-encodes that identifier, sets an Authorization bearer
header, uses a five-second timeout, and rejects responses over 64 KiB.

The existing diagnostic check also requires
`ENABLE_MCP_LAG_CHECK=true`, `DIAGNOSTIC_METRICS_MCP_URL`,
`MCP_LAG_THRESHOLD_MINUTES`, and an engineer-approved
`mcp_ingestion_lag` playbook. The live API will only register this check
when `METRICS_BACKEND=http`.

**Security scope:** the adapter checks response identity and uses a
configured read-only token, but the provider must enforce authorization,
tenant isolation, and incident/entity ownership. There is no production
telemetry provider configured or tested yet. The metrics MCP endpoint itself
also needs deployment-level access controls.

Run:

```sh
pytest -q tests/test_http_telemetry.py
pytest -q
```
