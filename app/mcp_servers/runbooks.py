"""Runbooks MCP server. Start with: python -m app.mcp_servers.runbooks"""
import os
from mcp.server.fastmcp import FastMCP
from app.tools import get_incident_runbook

mcp = FastMCP("incident-runbooks", host="127.0.0.1", port=int(os.getenv("RUNBOOKS_MCP_PORT", "8103")), stateless_http=True, json_response=True)

@mcp.tool()
def get_incident_runbook_mcp(incident_id: str) -> dict:
    """Retrieve read-only incident response guidance and approval requirements."""
    return get_incident_runbook.invoke({"incident_id": incident_id})

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
