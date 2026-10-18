import asyncio
from app.investigations.live_diagnostics import approved_diagnostic_context


def test_missing_entity_does_not_run_checks():
    result = asyncio.run(approved_diagnostic_context(None, 'INC', None, {}))
    assert result == ''
