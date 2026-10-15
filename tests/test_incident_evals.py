"""Unit tests for the model-in-the-loop evaluation harness (no Ollama required)."""
import asyncio
import json
from pathlib import Path

from evals.run import TOOL_NAMES, grade, make_fixture_tools, summarize


def load_cases():
    return json.loads((Path(__file__).resolve().parents[1] / "evals" / "incidents.json").read_text())


def test_all_fixtures_have_required_sources_and_ground_truth():
    cases = load_cases()
    assert len(cases) == 5
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["question"]
        assert set(case["tools"]) == set(TOOL_NAMES)
        assert set(case["required_tools"]).issubset(set(TOOL_NAMES.values()))
        assert case["root_cause"] is None or case["expected_terms"]


def test_fixture_tools_return_incident_scoped_data():
    case = load_cases()[0]
    tools = make_fixture_tools(case)
    assert {tool.name for tool in tools} == set(TOOL_NAMES.values())

    async def check():
        for tool in tools:
            response = json.loads(await tool.ainvoke({"incident_id": case["id"]}))
            assert response["incident_id"] == case["id"]
            assert "error" not in response
            other = json.loads(await tool.ainvoke({"incident_id": "INC-OTHER"}))
            assert other["error"] == "Incident not found"
    asyncio.run(check())


def test_grade_flags_missing_required_tools_and_unsupported_diagnosis():
    case = load_cases()[0]
    result = {
        "answer": "No confirmed root cause.",
        "tool_metrics": {TOOL_NAMES["metrics"]: {}},
        "status": "incomplete",
        "missing_evidence": [],
    }
    graded = grade(case, result)
    assert graded["tool_recall"] == 0.5
    assert graded["root_cause_keyword_match"] is False
    assert graded["missing_required_tools"] == [TOOL_NAMES["logs"]]


def test_unknown_root_cause_requires_uncertainty():
    case = load_cases()[-1]
    result = {
        "answer": "There is insufficient evidence to confirm a root cause.",
        "tool_metrics": {},
        "status": "incomplete",
        "missing_evidence": [],
    }
    assert grade(case, result)["root_cause_keyword_match"] is True
    result["answer"] = "The root cause is definitely a database outage."
    assert grade(case, result)["root_cause_keyword_match"] is False


def test_summary_counts_errors_without_treating_them_as_success():
    records = [
        {"grades": {"tool_recall": 1, "root_cause_keyword_match": True,
                    "evidence_keyword_match": False, "status": "complete"}},
        {"error": {"type": "ConnectionError", "message": "offline"}},
    ]
    summary = summarize(records)
    assert summary["total_runs"] == 2
    assert summary["completed_runs"] == 1
    assert summary["execution_errors"] == 1
    assert summary["mean_required_tool_recall"] == 1
