# Architecture

## Current investigation workflow

FastAPI -> compiled LangGraph `build_agent()` -> Ollama (tool selection and reasoning) -> selected MCP services (metrics, logs, runbooks).

At application startup, MCP tools are discovered and the graph is compiled once. Concurrent API requests run independent graph executions.

```text
START -> agent (LLM chooses tools)
           | tool_calls
           v
         tools (parallel MCP execution + retries)
           | failed + some valid evidence -> partial LLM synthesis -> incomplete -> END
           | failed + no valid evidence -> incomplete -> END
           | validated
           +-----------------------> agent
                                      | additional tool_calls -> tools
                                      | answer -> validate -> complete -> END
```

Only LLM-selected calls are required. Every selected call is validated by tool-call ID, tool name, incident ID, execution status, and response payload. Tool failure returns `incomplete`; when other evidence succeeded, a separate LLM call summarizes the valid observations and explicitly identifies unknowns. The API includes structured `tool_errors` with tool name, error type, message and attempt count. The configured LLM-round limit also returns `incomplete`. A response without any evidence cannot be marked complete.

The agent does not perform remediation. Evidence and hypotheses must remain distinct.

## Next milestones

1. Multi-agent supervisor with specialist agents and independent reasoning contexts.
2. Typed specialist outputs and evidence merging.
3. Durable checkpointing, deadlines, authorization, and tracing.
4. Evaluation of quality, latency, and model cost.
