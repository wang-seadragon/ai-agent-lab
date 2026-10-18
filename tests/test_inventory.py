import json
import pytest
from app.knowledge.inventory import FileInventory, InventoryConfigurationError


def test_only_explicit_inventory_entries_are_verified(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"entities": [
        {"entity_id": "service-a", "kind": "service"}]}))
    inventory = FileInventory(str(path))
    assert inventory.lookup("service-a") == {
        "entity_id": "service-a", "kind": "service", "verified": True}
    assert inventory.lookup("imaginary-service") is None


def test_missing_inventory_fails_closed(tmp_path):
    with pytest.raises(InventoryConfigurationError):
        FileInventory(str(tmp_path / "missing.json")).lookup("anything")


def test_duplicate_entries_fail_closed(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"entities": [
        {"entity_id": "a", "kind": "service"},
        {"entity_id": "a", "kind": "database"}]}))
    with pytest.raises(InventoryConfigurationError):
        FileInventory(str(path)).lookup("a")


def test_malformed_inventory_fails_closed(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text('{"entities": "not a list"}')
    with pytest.raises(InventoryConfigurationError):
        FileInventory(str(path)).lookup("a")
