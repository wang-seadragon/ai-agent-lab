"""Metrics MCP server. Start with: python -m app.mcp_servers.metrics"""
import os
from mcp.server.fastmcp import FastMCP
from app.tools import get_incident_metrics

mcp = FastMCP("incident-metrics", host="127.0.0.1", port=int(os.getenv("METRICS_MCP_PORT", "8101")), stateless_http=True, json_response=True)

@mcp.tool()
def get_incident_metrics_mcp(incident_id: str) -> dict:
    """Retrieve ingestion lag and worker CPU metrics for an incident."""
    return get_incident_metrics.invoke({"incident_id": incident_id})

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
