"""Logs MCP server. Start with: python -m app.mcp_servers.logs"""
import os
from mcp.server.fastmcp import FastMCP
from app.tools import get_incident_logs

mcp = FastMCP("incident-logs", host="127.0.0.1", port=int(os.getenv("LOGS_MCP_PORT", "8102")), stateless_http=True, json_response=True)

@mcp.tool()
def get_incident_logs_mcp(incident_id: str) -> dict:
    """Retrieve recent operational log entries for an incident."""
    return get_incident_logs.invoke({"incident_id": incident_id})

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
