"""Run repeatable, model-in-the-loop incident evaluations against fixture-backed tools.

Usage:
  python -m evals.run --runs 3 --output evals/report.json

Requires Ollama and the configured model. No live MCP servers are required.
"""
import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import StructuredTool

from app.agents.single_agent import build_agent, investigate
from app.llm.provider import get_chat_model

DEFAULT_CASES = Path(__file__).with_name("incidents.json")
TOOL_NAMES = {
    "metrics": "get_incident_metrics_mcp",
    "logs": "get_incident_logs_mcp",
    "runbook": "get_incident_runbook_mcp",
}
UNCERTAINTY = re.compile(
    r"insufficient|cannot (?:confirm|determine)|can't (?:confirm|determine)|"
    r"not enough|uncertain|not (?:confirmed|established)|inconclusive|"
    r"unable to (?:confirm|determine)|no (?:clear|confirmed) root cause",
    re.IGNORECASE,
)


def make_fixture_tools(case):
    """Expose the same MCP tool names, but serve versioned local fixture data."""
    tools = []
    for source, name in TOOL_NAMES.items():
        payload = {"incident_id": case["id"], **case["tools"][source]}

        def make_coroutine(data):
            async def lookup(incident_id: str) -> str:
                if incident_id != data["incident_id"]:
                    return json.dumps({"incident_id": incident_id, "error": "Incident not found"})
                return json.dumps(data)
            return lookup

        tools.append(StructuredTool.from_function(
            coroutine=make_coroutine(payload), name=name,
            description={
                "metrics": "Retrieve incident service performance and resource metrics.",
                "logs": "Retrieve incident logs, warnings, and error events.",
                "runbook": "Retrieve operational guidance and approval requirements.",
            }[source],
        ))
    return tools


def grade(case, result):
    """Transparent heuristics, not a semantic correctness or hallucination judge."""
    answer = result["answer"].lower()
    selected = set(result["tool_metrics"])
    required = set(case["required_tools"])
    root_terms = case["expected_terms"]
    root_match = (
        bool(UNCERTAINTY.search(result["answer"]))
        if case["root_cause"] is None
        else all(term.lower() in answer for term in root_terms)
    )
    return {
        "tool_recall": round(len(selected & required) / len(required), 3),
        "required_tools_selected": sorted(selected & required),
        "missing_required_tools": sorted(required - selected),
        "root_cause_keyword_match": root_match,
        "evidence_keyword_match": all(
            term.lower() in answer for term in case["evidence_terms"]
        ),
        "status": result["status"],
        "missing_evidence": result["missing_evidence"],
    }


async def evaluate(cases, runs):
    records = []
    for case in cases:
        for repetition in range(1, runs + 1):
            record = {"case_id": case["id"], "run": repetition}
            try:
                # Fresh model and graph per repetition prevent cross-run state.
                graph = build_agent(make_fixture_tools(case), model=get_chat_model())
                result = await investigate(graph, case["id"], case["question"])
                record["result"] = result
                record["grades"] = grade(case, result)
            except Exception as exc:
                record["error"] = {"type": type(exc).__name__, "message": str(exc)}
            records.append(record)
            outcome = record.get("grades", {})
            print(f'{case["id"]} run={repetition}: '
                  f'status={outcome.get("status", "error")} '
                  f'tool_recall={outcome.get("tool_recall", "n/a")} '
                  f'keyword_match={outcome.get("root_cause_keyword_match", "n/a")}',
                  flush=True)
    return records


def summarize(records):
    graded = [record["grades"] for record in records if "grades" in record]
    return {
        "total_runs": len(records),
        "completed_runs": len(graded),
        "execution_errors": len(records) - len(graded),
        "mean_required_tool_recall": round(
            sum(g["tool_recall"] for g in graded) / len(graded), 3
        ) if graded else None,
        "root_cause_keyword_match_rate": round(
            sum(g["root_cause_keyword_match"] for g in graded) / len(graded), 3
        ) if graded else None,
        "evidence_keyword_match_rate": round(
            sum(g["evidence_keyword_match"] for g in graded) / len(graded), 3
        ) if graded else None,
        "complete_status_rate": round(
            sum(g["status"] == "complete" for g in graded) / len(graded), 3
        ) if graded else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("evals/report.json"))
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be >= 1")
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not cases:
        parser.error("No cases found")
    records = asyncio.run(evaluate(cases, args.runs))
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": __import__("os").getenv("OLLAMA_MODEL", "qwen3:14b"),
        "fixture_path": str(args.cases),
        "grading_note": "Keyword and tool-recall proxies only; not validated diagnostic accuracy.",
        "summary": summarize(records),
        "runs": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n",
                           encoding="utf-8")
    print(f"Report: {args.output}")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
