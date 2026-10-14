# AI Agent Lab

Local-first, production-oriented AI agent architecture learning project.

## Milestone 1: single-agent baseline

FastAPI -> LangGraph ReAct agent -> Ollama -> three deterministic simulated tools.

The current tools are **not yet MCP servers**. We'll add actual MCP services and client adapters in milestone 2.

### Prerequisites
- Python 3.11+
- Ollama running and a model downloaded (`ollama pull qwen3:14b`)

### Setup (Linux / WSL2)

```bash
cd ~/projects/ai-agent-lab
git pull origin main
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
uvicorn app.api.main:app --reload
```

### Test API (second terminal)

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/investigate \
  -H 'Content-Type: application/json' \
  -d '{"incident_id":"INC-1001","question":"Why is the pipeline delayed? Check metrics, logs and runbooks."}'
```

Set `OLLAMA_MODEL` and `OLLAMA_BASE_URL` via environment variables if defaults differ. If Ollama runs on Windows and Python in WSL, check connectivity to port 11434.

See [architecture](docs/architecture.md). Next: actual MCP servers, supervisor-worker architecture, checkpoints and evaluation.
