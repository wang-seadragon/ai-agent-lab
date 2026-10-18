"""Execute only registered, approved checks; do not infer causality."""
from collections.abc import Callable
from app.diagnostics.playbooks import DiagnosticPlaybookRegistry


class DiagnosticEngine:
    def __init__(self, registry: DiagnosticPlaybookRegistry):
        self.registry = registry

    def evaluate(self, entity_id: str, entity_kind: str,
                 checks: dict[str, Callable[[str], bool | None]]
                 ) -> tuple[str, tuple[str, ...], str | None]:
        playbooks = self.registry.approved_for_kind(entity_kind)
        if not playbooks:
            return "needs_engineer_review", ("No approved diagnostic playbook applies",), None
        findings = []
        matched = []
        for playbook_id, check_name in playbooks:
            check = checks.get(check_name)
            if check is None:
                findings.append(f"{check_name}: unavailable")
                continue
            try:
                outcome = check(entity_id)
            except Exception as exc:
                findings.append(f"{check_name}: check failed ({type(exc).__name__})")
                continue
            if outcome is True:
                matched.append(playbook_id)
                findings.append(f"{check_name}: conditions matched")
            elif outcome is False:
                findings.append(f"{check_name}: conditions not matched")
            else:
                findings.append(f"{check_name}: inconclusive")
        return ("pattern_matched" if matched else "needs_engineer_review",
                tuple(findings), matched[0] if matched else None)
