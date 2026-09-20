from pathlib import Path
import re

ROOT = Path(__file__).parents[2]
API = ROOT / "apps" / "api"


def test_inventory_migration_is_additive_and_tenant_safe():
    sql = (ROOT / "migrations" / "005_inventory_foundation.sql").read_text()
    for table in [
        "idempotency_keys", "inventory_balances", "inventory_transactions",
        "inventory_adjustments", "inventory_adjustment_lines", "stock_counts",
        "stock_count_lines", "inventory_transfers", "inventory_transfer_lines",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
        assert "ALTER TABLE %I ENABLE ROW LEVEL SECURITY" in sql
        assert "_tenant_isolation" in sql
    assert "DELETE FROM" not in sql.upper()
    assert "TRUNCATE" not in sql.upper()
    assert "DROP TABLE" not in sql.upper()


def test_inventory_api_matches_state_machine_contract():
    source = (API / "app" / "routes" / "inventory.py").read_text()
    required = [
        '"/balances"', '"/ledger"', '"/products/{variant_id}"',
        '"/adjustments"', '"/adjustments/{adjustment_id}/approve"', '"/adjustments/{adjustment_id}/post"',
        '"/stock-counts"', '"/stock-counts/{count_id}/submit"', '"/stock-counts/{count_id}/approve"', '"/stock-counts/{count_id}/post"',
        '"/transfers"', '"/transfers/{transfer_id}/approve"', '"/transfers/{transfer_id}/dispatch"',
        '"/transfers/{transfer_id}/receive"', '"/transfers/{transfer_id}/complete"',
    ]
    for endpoint in required:
        assert endpoint in source
    assert "Insufficient available stock" in source or "Insufficient available stock" in (API / "app" / "inventory.py").read_text()
    assert "TRANSFER_QUANTITY_EXCEEDED" in source


def test_inventory_domain_has_weighted_average_and_ledger_balance_logic():
    source = (API / "app" / "inventory.py").read_text()
    assert "average_cost" in source
    assert "stock_value" in source
    assert "old_quantity * old_average" in source
    assert "new_qty < 0" in source
    assert "balance_after" in source


def test_frontend_inventory_is_live_data_only():
    source = (ROOT / "apps" / "web" / "app" / "page.tsx").read_text()
    assert "getInventoryBalances" in source
    assert "getInventoryLedger" in source
    assert "getAdjustments" in source
    assert "getStockCounts" in source
    assert "getTransfers" in source
    assert "Your stock, movements and locations will appear here as soon as the workspace is connected." in source
    assert "LIVE SYSTEM" not in source
