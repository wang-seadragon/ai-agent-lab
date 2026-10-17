"""MCP verification adapter: accepts only a dedicated, trusted inventory lookup.

This adapter is deliberately NOT wired to generic logs/metrics/runbook tools.
The supplied lookup must query an authoritative inventory, not an LLM.
"""
from collections.abc import Callable
from typing import Any

from app.knowledge.models import VerifiedEntity
from app.knowledge.verification import EntityVerification


class MCPInventoryVerifier:
    def __init__(self, lookup: Callable[[str], dict[str, Any] | None],
                 source_name: str):
        if not source_name or not source_name.strip():
            raise ValueError("A trusted inventory source name is required")
        self.lookup = lookup
        self.source_name = source_name

    def verify(self, entity_id: str) -> EntityVerification | None:
        record = self.lookup(entity_id)
        if record is None:
            return None
        if not isinstance(record, dict):
            raise ValueError("Inventory lookup must return a structured record")
        # Never accept generic text, candidate names, or unverified responses.
        if (record.get("verified") is not True
                or record.get("entity_id") != entity_id
                or not isinstance(record.get("kind"), str)
                or not record["kind"].strip()):
            return None
        return EntityVerification(
            VerifiedEntity(record["entity_id"], record["kind"]),
            self.source_name,
        )
