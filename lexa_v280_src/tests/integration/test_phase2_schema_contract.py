from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_phase2_hardening_migration_exists():
    path = ROOT / "migrations/007_phase2_catalog_hardening.sql"
    assert path.exists()
    source = path.read_text()
    for token in [
        "btree_gist",
        "product_prices_no_overlap",
        "lexa_validate_category_parent",
        "lexa_validate_variant_unit",
        "FORCE ROW LEVEL SECURITY",
        "uq_variants_tenant_sku_active",
        "uq_barcodes_tenant_value_active",
    ]:
        assert token in source


def test_phase2_does_not_replace_phase1_outbox_contract():
    source = (ROOT / "migrations/007_phase2_catalog_hardening.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS outbox_events" not in source
    assert "actor_user_id" not in source


def test_phase2_schema_has_database_level_price_overlap_protection():
    source = (ROOT / "migrations/007_phase2_catalog_hardening.sql").read_text()
    assert "EXCLUDE USING gist" in source
    assert "minimum_quantity WITH =" in source
    assert "tstzrange(effective_from, effective_to, '[)') WITH &&" in source
