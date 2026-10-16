"""Regression tests for conservative structured diagnosis extraction."""
from app.agents.evidence_assessment import extract_diagnosis


SAMPLE = """**Root cause confirmed:** No
**Observed evidence:**
- Worker CPU usage at 96%.
**Likely cause:**
Resource pressure (CPU/memory) on workers is causing task retries.
**Confidence:** Medium
**Remaining uncertainty:**
- No data on recent deployments or input volume spikes.
- Alternative explanations are not ruled out.
**Next steps:**
1. Check deployment history.
"""


def test_structured_diagnosis_from_incident_answer():
    result = extract_diagnosis(SAMPLE, "complete")
    assert result["root_cause_confirmed"] is False
    assert result["suspected_root_cause"].startswith("Resource pressure")
    assert result["confidence"] == "medium"
    assert len(result["diagnostic_missing_evidence"]) == 2
    assert "Check deployment history" not in str(result["diagnostic_missing_evidence"])


def test_unverified_yes_is_not_promoted_to_confirmed():
    answer = """**Root cause confirmed:** Yes
**Likely cause:** Database outage
**Confidence:** High
"""
    result = extract_diagnosis(answer, "complete")
    assert result["root_cause_confirmed"] is False
    assert result["suspected_root_cause"] == "Database outage"
    assert result["confidence"] == "high"


def test_incomplete_does_not_assert_diagnosis():
    result = extract_diagnosis(SAMPLE, "incomplete")
    assert result["root_cause_confirmed"] is False
    assert result["suspected_root_cause"] is None
    assert result["confidence"] is None


def test_unstructured_answer_does_not_invent_diagnosis():
    result = extract_diagnosis("The investigation has no supporting evidence.", "complete")
    assert result == {
        "root_cause_confirmed": False,
        "suspected_root_cause": None,
        "confidence": None,
        "diagnostic_missing_evidence": [],
    }
