# Opt-in approved diagnostics in live investigation

After the inventory MCP confirms a caller-provided entity ID, the API can
invoke the existing deterministic InvestigationOrchestrator. The engine
only loads playbooks approved in the local knowledge SQLite database.

Enable only with all existing inventory and Neo4j configuration plus:

- `ENABLE_APPROVED_DIAGNOSTICS=true`
- `KNOWLEDGE_SQLITE_PATH=/path/to/operator-managed/knowledge.db`

**No diagnostic checks are registered by default.** The trusted application
must explicitly populate `app.state.diagnostic_checks` with deterministic
read-only callables keyed by approved check names. An approved playbook
without an executable check reports `unavailable`; it is never invented.
The existing engineer approval workflow is required to approve playbooks.

Unknown entities do not execute checks. Diagnostic failures are reported as
unavailable while metrics/logs/runbook investigation continues. Findings
are context for the investigation, not proof of a root cause.

This is an opt-in development integration, not a production-ready
authorization or tenant-isolation boundary. Tests:
`pytest -q tests/test_live_approved_diagnostics.py tests/test_approved_diagnostic_context.py`.
