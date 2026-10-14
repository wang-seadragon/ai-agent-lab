# Architecture

## Milestone 1 — baseline

FastAPI -> LangGraph ReAct agent -> Ollama -> three deterministic LangChain tools.

The tools currently simulate metrics, logs and runbooks. They are **not MCP servers yet**. We will establish local execution and test fixtures first, then introduce three independent MCP servers and MCP client adapters.

## Next milestones

1. MCP metrics, logs and runbook servers.
2. Supervisor-worker LangGraph with separate reasoning contexts.
3. Parallel investigations, typed result contracts and evidence merging.
4. Durable checkpointing, deadlines, retries and authorization.
5. Tracing and comparisons of quality, latency and model cost.

Keep evidence distinct from hypotheses. Remediation requires human approval.
