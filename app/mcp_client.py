"""MCP tool discovery via independent Streamable HTTP servers."""
import os
from langchain_mcp_adapters.client import MultiServerMCPClient


def create_mcp_client() -> MultiServerMCPClient:
    host = os.getenv("MCP_HOST", "127.0.0.1")
    return MultiServerMCPClient({
        "metrics": {"transport": "streamable_http", "url": f"http://{host}:{os.getenv('METRICS_MCP_PORT', '8101')}/mcp"},
        "logs": {"transport": "streamable_http", "url": f"http://{host}:{os.getenv('LOGS_MCP_PORT', '8102')}/mcp"},
        "runbooks": {"transport": "streamable_http", "url": f"http://{host}:{os.getenv('RUNBOOKS_MCP_PORT', '8103')}/mcp"},
    })
