# MCP milestone: three independent Streamable HTTP servers

Install dependencies with `python -m pip install -e '.[dev]'`.

Open three WSL terminals with the `ai-agent-lab` Conda environment active:

```bash
python -m app.mcp_servers.metrics    # 127.0.0.1:8101/mcp
python -m app.mcp_servers.logs       # 127.0.0.1:8102/mcp
python -m app.mcp_servers.runbooks   # 127.0.0.1:8103/mcp
```

Keep Windows Ollama running. In a fourth WSL terminal:

```bash
export OLLAMA_BASE_URL=http://192.168.48.1:11434
export OLLAMA_MODEL=qwen3:14b
uvicorn app.api.main:app --reload
```

FastAPI lifespan discovers the remote tools and compiles one agent per process.
Each tool call uses an MCP client-managed session. The MCP servers bind only to WSL
loopback by default. `/health` does not guarantee Ollama readiness.

Test:

```bash
curl -X POST http://localhost:8000/investigate -H 'Content-Type: application/json' -d '{"incident_id":"INC-1001","question":"Investigate using metrics, logs, and runbooks."}'
```

The three MCP servers currently delegate to the deterministic legacy fixture tools,
so this milestone tests transport and orchestration rather than live observability data.
Next steps: service integration tests, failure/timeout policies, and replacing fixture
backends with actual observability systems.
