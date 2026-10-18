"""Read-only, opt-in MCP metrics check. No synthetic fallback or inferred mapping."""
import asyncio
import json

from langchain_mcp_adapters.client import MultiServerMCPClient


class MetricsEvidenceError(RuntimeError):
    pass


def parse_metrics(result, incident_id, entity_id, threshold):
    """Return True/False only for exact matching evidence, otherwise None."""
    if isinstance(result, dict):
        data = result
    else:
        if hasattr(result, "content"):
            result = result.content
        if isinstance(result, list) and len(result) == 1:
            block = result[0]
            result = block.get("text") if isinstance(block, dict) and block.get("type") == "text" else None
        try:
            data = json.loads(result) if isinstance(result, str) else None
        except (TypeError, ValueError):
            data = None
    if not isinstance(data, dict) or data.get("error"):
        return None
    if data.get("incident_id") != incident_id or data.get("pipeline") != entity_id:
        return None
    lag = data.get("ingestion_lag_minutes")
    if type(lag) not in (int, float) or not 0 <= lag < float("inf"):
        return None
    return lag >= threshold


async def fetch_lag_evidence(incident_id, entity_id, threshold, url, *,
                             client=None, timeout_seconds=5.0):
    """Query dedicated metrics MCP endpoint, never LLM-selected tool output."""
    if not url or not incident_id or not entity_id:
        raise MetricsEvidenceError("Metrics endpoint and exact identifiers required")
    if type(threshold) not in (int, float) or not 0 < threshold < float("inf"):
        raise MetricsEvidenceError("Positive finite lag threshold required")
    if client is None:
        client = MultiServerMCPClient({
            "diagnostic_metrics": {"transport": "streamable_http", "url": url}
        })
    try:
        tools = await asyncio.wait_for(client.get_tools(), timeout_seconds)
        matches = [tool for tool in tools if tool.name == "get_incident_metrics_mcp"]
        if len(matches) != 1:
            return None
        result = await asyncio.wait_for(
            matches[0].ainvoke({"incident_id": incident_id}), timeout_seconds
        )
        return parse_metrics(result, incident_id, entity_id, threshold)
    except Exception:
        return None


def lag_check_from_evidence(entity_id, observed_entity_id, outcome):
    """Bind a deterministic synchronous check to a single verified entity."""
    def check(candidate_id):
        if candidate_id != entity_id or observed_entity_id != entity_id:
            return None
        return outcome
    return check
