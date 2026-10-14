"""Unit tests for the actual MCP server tool functions (no network needed)."""
from app.mcp_servers.metrics import get_incident_metrics_mcp
from app.mcp_servers.logs import get_incident_logs_mcp
from app.mcp_servers.runbooks import get_incident_runbook_mcp


def test_metrics_mcp_tool():
    assert get_incident_metrics_mcp("INC-1001")["worker_cpu_percent"] == 96


def test_logs_mcp_tool():
    assert len(get_incident_logs_mcp("INC-1001")["entries"]) == 3


def test_runbook_mcp_tool():
    assert "guidance" in get_incident_runbook_mcp("INC-1001")


def test_unknown_incident_mcp_tool():
    assert get_incident_metrics_mcp("INC-UNKNOWN")["error"] == "Incident not found"
