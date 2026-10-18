# Local Observability Lab (synthetic test environment)

This lab runs a real Python simulator and Prometheus scraper. **All
incidents and measurements are synthetic lab data, never production evidence.**

## Start the lab

```sh
docker compose -f lab/compose.yaml up -d
curl http://127.0.0.1:8090/metrics
```

Prometheus is available at http://127.0.0.1:9090. Search for
`lab_ingestion_lag_minutes` and allow several seconds for scraping.

## Reproduce scenarios

```sh
curl -X POST http://127.0.0.1:8090/scenario \
  -H 'Authorization: Bearer local-lab-only' \
  -H 'Content-Type: application/json' -d '{"mode":"lag"}'
```

The lag gauge increases by one simulated minute per second while the
lag scenario runs. Change `mode` to `failure` to increment worker
error counts, or `normal` to reset lag and resume processing.
This time acceleration is intentional and is not real elapsed lag.

## Connect metrics MCP

Run the existing metrics MCP server on the host with:

```sh
export METRICS_BACKEND=lab_prometheus
export LAB_PROMETHEUS_URL=http://127.0.0.1:9090
python -m app.mcp_servers.metrics
```

The MCP tool `get_incident_metrics_mcp` accepts incident
`LAB-INC-1` and returns pipeline `lab-orders` with the current
Prometheus ingestion lag. Unknown incidents, missing series, and
mismatched labels produce errors, not fabricated values.

## Optional approved diagnostics through /investigate

The lab does not bypass inventory verification or engineer approval.
For a full API investigation, explicitly configure inventory MCP,
Neo4j, knowledge SQLite, and an approved `mcp_ingestion_lag`
playbook for entity kind `pipeline`. The operator-managed inventory
must contain `lab-orders` with kind `pipeline`.
Also set:

```sh
export ENABLE_INVENTORY_GRAPH=true
export ENABLE_APPROVED_DIAGNOSTICS=true
export ENABLE_MCP_LAG_CHECK=true
export METRICS_BACKEND=lab_prometheus
export DIAGNOSTIC_METRICS_MCP_URL=http://127.0.0.1:8101/mcp
export MCP_LAG_THRESHOLD_MINUTES=20
```

The API request must specify `incident_id=LAB-INC-1` and
`entity_id=lab-orders`. The read-only diagnostic is executed only
after current inventory verification. A matching lag threshold is a
pattern, not proof of causation.

**Important:** the lab alone does not start Neo4j, inventory MCP, logs
MCP, runbooks MCP, or the FastAPI application. These remain part of the
existing application setup. Lab endpoints bind to loopback only on the
Docker host. Change the example control token before shared use.

```sh
pytest -q tests/test_lab_prometheus.py
pytest -q
docker compose -f lab/compose.yaml down
```


## Engineer-approved diagnostic setup (local lab)

This is a **manual approval step**, not automatic approval by the API.
Review the check implementation in `app/diagnostics/mcp_metrics_check.py`
and run from the repository root:

```sh
export KNOWLEDGE_SQLITE_PATH="$PWD/lab/knowledge.db"
python -m lab.approve_playbook --db "$KNOWLEDGE_SQLITE_PATH" --reviewer "$USER"
```

The command proposes `lab-high-ingestion-lag`, requires typing
`APPROVE`, and records the reviewer in SQLite. It does not approve
other checks or automatically execute any check.

Run inventory MCP in its own terminal:

```sh
export INVENTORY_FILE="$PWD/lab/inventory.json"
python -m app.mcp_servers.inventory
```

The inventory is an explicitly configured **synthetic lab inventory**;
it is not evidence of real infrastructure. The API also requires a
running Neo4j server and its credentials, plus the existing logs and
runbooks MCP servers, metrics MCP server, and LLM configuration.
Configure those according to the existing project setup before
starting FastAPI. The opt-in API variables are:

```sh
export ENABLE_INVENTORY_GRAPH=true
export INVENTORY_MCP_URL=http://127.0.0.1:8104/mcp
export ENABLE_APPROVED_DIAGNOSTICS=true
export KNOWLEDGE_SQLITE_PATH="$PWD/lab/knowledge.db"
export ENABLE_MCP_LAG_CHECK=true
export METRICS_BACKEND=lab_prometheus
export DIAGNOSTIC_METRICS_MCP_URL=http://127.0.0.1:8101/mcp
export MCP_LAG_THRESHOLD_MINUTES=20
```

Once all services are running, request:

```sh
curl -s http://127.0.0.1:8000/investigate \
  -H 'Content-Type: application/json' \
  -d '{"incident_id":"LAB-INC-1","entity_id":"lab-orders","question":"Investigate the observed lag. Distinguish measurements from root-cause hypotheses."}'
```

A high reading can match the approved playbook, but it **cannot confirm
root cause**. Missing or mismatched evidence must be inconclusive.

```sh
pytest -q tests/test_lab_approved_diagnostics.py
```
