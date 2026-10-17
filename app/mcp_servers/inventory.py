"""Opt-in authoritative inventory MCP service.

Only deploy with an operator-controlled INVENTORY_FILE. This service is not
registered as an LLM-selected evidence tool: its result is used solely by
the trusted verification pipeline.
"""
import os
from mcp.server.fastmcp import FastMCP
from app.knowledge.inventory import FileInventory

mcp = FastMCP(
    "authoritative-inventory",
    host="127.0.0.1",
    port=int(os.getenv("INVENTORY_MCP_PORT", "8104")),
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def verify_inventory_entity_mcp(entity_id: str) -> dict:
    """Look up an exact infrastructure entity in configured authoritative inventory."""
    record = FileInventory(os.getenv("INVENTORY_FILE", "")).lookup(entity_id)
    return record if record is not None else {
        "entity_id": entity_id, "verified": False,
    }


if __name__ == "__main__":
    if not os.getenv("INVENTORY_FILE"):
        raise SystemExit("INVENTORY_FILE is required; refusing to start")
    mcp.run(transport="streamable-http")
