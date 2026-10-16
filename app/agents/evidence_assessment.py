"""Conservative, deterministic projection of narrative diagnosis into API fields.

This parser is not an independent causal verifier. It deliberately never upgrades
a narrative claim to a *confirmed* root cause without a separate evidence gate.
"""
import re

_HEADINGS = {
    "likely": ("likely cause", "likely root cause", "suspected root cause", "hypothesis for root cause"),
    "confidence": ("confidence",),
    "missing": ("remaining uncertainty", "missing evidence", "evidence gaps", "unknowns"),
}
_ALL_HEADINGS = tuple(label for labels in _HEADINGS.values() for label in labels) + (
    "root cause confirmed", "observed evidence", "observed facts", "supporting evidence",
    "alternative explanations", "next steps", "recommended next steps",
)
_HEADING_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:\*\*)?(" +
    "|".join(re.escape(s) for s in sorted(_ALL_HEADINGS, key=len, reverse=True)) +
    r")(?:\*\*)?\s*:\s*(.*)$", re.IGNORECASE,
)


def _sections(answer: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    active = None
    for line in answer.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            active = match.group(1).lower()
            sections.setdefault(active, [])
            if match.group(2).strip():
                sections[active].append(match.group(2).strip())
        elif active and line.strip():
            sections[active].append(line.strip())
    return sections


def _clean(line: str) -> str:
    return re.sub(r"^[-*•]\s*|^\d+[.)]\s*", "", line).strip().strip("* ").strip()


def extract_diagnosis(answer: str, status: str) -> dict:
    """Project explicit narrative statements, never infer confirmation from symptoms."""
    sections = _sections(answer)
    likely = next(
        (_clean(line) for heading in _HEADINGS["likely"]
         for line in sections.get(heading, []) if _clean(line)),
        None,
    )
    confidence = next(
        (level for heading in _HEADINGS["confidence"]
         for line in sections.get(heading, [])
         for level in ("high", "medium", "low")
         if re.search(r"\b" + level + r"\b", line, re.IGNORECASE)),
        None,
    )
    gaps = []
    for heading in _HEADINGS["missing"]:
        for line in sections.get(heading, []):
            item = _clean(line)
            if item and item not in gaps:
                gaps.append(item)
    # Even an explicit "Yes" in free-form LLM text is not independent proof.
    # A later evidence-verification stage may safely set this to True.
    return {
        "root_cause_confirmed": False,
        "suspected_root_cause": likely if status == "complete" else None,
        "confidence": confidence if status == "complete" else None,
        "diagnostic_missing_evidence": gaps,
    }
