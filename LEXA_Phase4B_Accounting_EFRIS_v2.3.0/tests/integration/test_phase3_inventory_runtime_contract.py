from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_inventory_rebuild_and_immutability_contract():
    route = (ROOT / "apps" / "api" / "app" / "routes" / "inventory.py").read_text()
    assert '"/rebuild"' in route
    assert 'inventory.rebuild' in route
    source = (ROOT / "migrations" / "014_phase3_inventory_foundation.sql").read_text()
    assert "inventory.rebuild" in source
    assert "REVOKE UPDATE, DELETE ON inventory_transactions" in source
    assert "inventory_transactions is append-only" in source
