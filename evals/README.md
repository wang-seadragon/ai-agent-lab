# Model-in-the-loop incident quality evaluation

This suite uses the **real LangGraph investigation agent and configured Ollama model**,
with **fixture-backed LangChain tools** exposing the same tool names as the three MCP
servers. It does **not** exercise MCP transport or require the MCP servers to run.
The existing pytest suite remains the deterministic workflow regression gate.

## Run

Install dev dependencies and ensure Ollama has the configured model (default
`qwen3:14b`) running:

```bash
python -m pip install -e '.[dev]'
python -m pytest tests -q
python -m evals.run --runs 3 --output evals/report.json
```

The evaluation reads `evals/incidents.json` and runs five scenarios three
times each. Each repetition constructs a fresh model and agent graph.

The JSON report records the complete investigation response, selected tool
metrics, missing evidence, execution errors, and these **heuristic** scores:

- **Required-tool recall**: proportion of designated evidence tools selected.
  Tool selection precision is not yet measured; extra calls may be reasonable.
- **Root-cause keyword match**: whether all expected strings appear in the
  answer. For the inconclusive case, checks for uncertainty language.
- **Evidence keyword match**: whether expected evidence terms appear.
- **Complete status rate**: workflow completion, **not** diagnosis accuracy.

These indicators are **not semantic grading**. A model can match keywords and
still hallucinate causal claims; it can be correct using different wording and
fail the keyword check. The inconclusive fixture tests language of uncertainty,
not a complete absence of unsupported claims.

## Next iteration

Add structured answer claims with evidence IDs, human-reviewed ground-truth
rubrics, tool-selection precision, and a separate LLM judge (with calibrated
human review). Record prompt/model versions and latency distributions before
using scores as a release gate.

Never commit generated reports containing operational or sensitive data.
