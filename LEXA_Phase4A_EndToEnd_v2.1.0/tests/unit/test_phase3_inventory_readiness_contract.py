from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_phase3_migration_exists_and_is_additive():
    sql = (ROOT / "migrations" / "014_phase3_inventory_foundation.sql").read_text()
    required = [
        "inventory_balances", "inventory_transactions", "inventory_adjustments",
        "stock_counts", "inventory_transfers", "inventory_transfer_lines",
        "idempotency_keys",
    ]
    for table in required:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "DROP TABLE" not in sql.upper()
    assert "TRUNCATE" not in sql.upper()
    assert "DELETE FROM" not in sql.upper()
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid" in sql


def test_readiness_requires_phase3_inventory_tables():
    source = (ROOT / "apps" / "api" / "app" / "health.py").read_text()
    for table in [
        "idempotency_keys", "inventory_balances", "inventory_transactions",
        "inventory_adjustments", "inventory_adjustment_lines", "stock_counts",
        "stock_count_lines", "inventory_transfers", "inventory_transfer_lines",
    ]:
        assert f'"{table}"' in source
