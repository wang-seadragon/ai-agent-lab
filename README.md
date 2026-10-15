# AI Agent Lab

Local-first incident investigation agent built with FastAPI, LangGraph, Ollama, and three independent MCP services (metrics, logs, runbooks).

## Current architecture

FastAPI discovers MCP tools and compiles **one** iterative LangGraph agent at startup. Each `/investigate` request runs that compiled graph with independent state.

1. The LLM receives the available MCP tool schemas and selects relevant tools.
2. Selected MCP calls execute concurrently, with bounded retries and timeouts.
3. The graph validates every selected call against its call ID, incident ID, and response payload.
4. If a selected call fails, the investigation returns `incomplete` without another LLM call.
5. Otherwise, the LLM reviews the results and may select additional tools or produce an answer.
6. A maximum LLM-round limit bounds execution. A diagnosis without tool evidence is rejected.

No fixed set of three evidence sources is required: the LLM chooses which available tools are relevant.

## Setup (Python 3.11+)

Install project dependencies and run tests:

```bash
python -m pip install -e '.[dev]'
python -m compileall -q app
pytest -q
```

Start Ollama with `qwen3:14b` available and configure `OLLAMA_MODEL` / `OLLAMA_BASE_URL` as needed. Run the three MCP services in separate terminals:

```bash
python -m app.mcp_servers.metrics
python -m app.mcp_servers.logs
python -m app.mcp_servers.runbooks
```

Then start the API:

```bash
uvicorn app.api.main:app --reload
```

Test it:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/investigate \
  -H 'Content-Type: application/json' \
  -d '{"incident_id":"INC-1001","question":"Why is the pipeline delayed? Investigate using relevant evidence."}'
```

See [architecture](docs/architecture.md). Next milestone: multi-agent supervisor and specialist agents.
