# Golden Evaluation Baseline

## Purpose

The first evaluation layer checks **deterministic workflow behavior** of the incident
investigation LangGraph agent. It is deliberately independent of live Ollama,
networked MCP servers, and stochastic model responses.

## Run

From the repository root, with the development dependencies installed:

```bash
python -m pytest tests/test_golden_workflow.py -q
python -m pytest tests -q
```

The baseline contains **12 parametrized golden scenarios** in
`tests/test_golden_workflow.py`. They verify:

- The exact selected MCP tools are reflected in tool metrics.
- A successful selected-tool workflow finishes with `status=complete`.
- Iterative selection can collect additional evidence across LLM rounds.
- No evidence, unknown tools, wrong-incident requests, MCP transport errors,
  and MCP application errors cannot silently produce `status=complete`.
- A partial tool failure retains available evidence but reports
  `status=incomplete`, `missing_evidence`, and structured `tool_errors`.

These tests are a **contract regression suite**, not a claim that the agent
selects the best tools or diagnoses incidents correctly. The model's choices
are scripted; the synthetic tool observations do not contain real root causes.

## Next evaluation layer (not yet implemented)

Build a versioned incident dataset with metrics, logs, runbook fixtures,
known root causes, alternative hypotheses, and expected supporting evidence.
Run the real model against the fixtures, capture tool-call traces and answers,
then grade:

1. Tool selection precision and recall.
2. Evidence grounding and citation to observations.
3. Root-cause accuracy, distinguishing fact from hypothesis.
4. Missing-evidence disclosure and safe abstention.
5. Repeated-run consistency and latency/token budget.

Keep the deterministic workflow suite as a required fast gate; run
model-dependent evaluations separately with explicit model/version and
repeat counts. Never treat a scripted-model passing result as proof of
real-model accuracy.
