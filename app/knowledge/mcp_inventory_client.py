"""Dedicated trusted MCP inventory client; never expose it as an LLM tool."""
import asyncio
import json
import os

from langchain_mcp_adapters.client import MultiServerMCPClient

from app.knowledge.mcp_verifier import MCPInventoryVerifier
from app.knowledge.verification import VerifiedGraphIngestor


class InventoryLookupError(RuntimeError):
    pass


def _decode_tool_payload(result):
    """Decode only a single structured inventory response, not free-form prose."""
    if isinstance(result, dict):
        return result
    if hasattr(result, "content"):
        result = result.content
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (TypeError, ValueError) as exc:
            raise InventoryLookupError("Inventory returned invalid JSON") from exc
    if isinstance(result, list) and len(result) == 1:
        block = result[0]
        if isinstance(block, dict) and block.get("type") == "text":
            return _decode_tool_payload(block.get("text"))
    raise InventoryLookupError("Inventory returned an unsupported payload")


async def verify_and_ingest_entity(entity_id: str, graph, *,
                                   client=None, timeout_seconds: float = 5.0):
    """Verify an exact ID via dedicated MCP and persist only on positive verification.

    A client can be injected for tests. Production requires explicit INVENTORY_MCP_URL
    configuration and must authenticate the server through deployment controls.
    """
    if not entity_id or not entity_id.strip():
        raise ValueError("Entity ID required")
    if timeout_seconds <= 0:
        raise ValueError("Timeout must be positive")
    if client is None:
        url = os.getenv("INVENTORY_MCP_URL")
        if not url:
            raise InventoryLookupError("INVENTORY_MCP_URL is not configured")
        client = MultiServerMCPClient({
            "inventory": {"transport": "streamable_http", "url": url}
        })
    try:
        tools = await asyncio.wait_for(client.get_tools(), timeout=timeout_seconds)
        matches = [t for t in tools if t.name == "verify_inventory_entity_mcp"]
        if len(matches) != 1:
            raise InventoryLookupError("Expected exactly one inventory verification tool")
        result = await asyncio.wait_for(
            matches[0].ainvoke({"entity_id": entity_id}), timeout=timeout_seconds)
        payload = _decode_tool_payload(result)
        if not isinstance(payload, dict) or payload.get("error"):
            raise InventoryLookupError("Inventory verification failed")
        verifier = MCPInventoryVerifier(lambda _: payload, "configured-inventory-mcp")
        return VerifiedGraphIngestor(graph, verifier).verify_and_store(entity_id)
    except (asyncio.TimeoutError, ConnectionError, OSError) as exc:
        raise InventoryLookupError("Inventory service unavailable") from exc
