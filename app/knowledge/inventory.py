"""Read-only authoritative inventory loaded from a customer-managed JSON snapshot.

An inventory snapshot is trusted only when an operator explicitly configures
its path. No sample entities, LLM guesses, or tool evidence are promoted.
"""
import json
from pathlib import Path


class InventoryConfigurationError(RuntimeError):
    pass


class FileInventory:
    def __init__(self, path: str):
        if not path:
            raise InventoryConfigurationError("INVENTORY_FILE must be configured")
        self.path = Path(path)

    def lookup(self, entity_id: str) -> dict | None:
        if not entity_id or not entity_id.strip():
            raise ValueError("Entity ID required")
        try:
            with self.path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            raise InventoryConfigurationError("Authoritative inventory unavailable") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("entities"), list):
            raise InventoryConfigurationError("Inventory must contain an entities array")
        matches = [e for e in payload["entities"]
                   if isinstance(e, dict) and e.get("entity_id") == entity_id]
        if len(matches) > 1:
            raise InventoryConfigurationError("Duplicate inventory entity IDs")
        if not matches:
            return None
        entity = matches[0]
        if not isinstance(entity.get("kind"), str) or not entity["kind"].strip():
            raise InventoryConfigurationError("Inventory entity missing kind")
        # Explicit verified=True only after exact match in configured inventory.
        return {"entity_id": entity_id, "kind": entity["kind"], "verified": True}
