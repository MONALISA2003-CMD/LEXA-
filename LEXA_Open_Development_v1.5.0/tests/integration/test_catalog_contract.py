from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_catalog_migration_exists():
    assert (ROOT / "migrations/004_catalog_and_rbac_hardening.sql").exists()


def test_catalog_route_exists():
    assert (ROOT / "apps/api/app/routes/catalog.py").exists()


def test_catalog_has_required_entities():
    migration = (ROOT / "migrations/004_catalog_and_rbac_hardening.sql").read_text()
    for table in [
        "categories", "brands", "units", "products", "product_variants",
        "barcodes", "product_attribute_definitions", "product_attribute_values",
        "price_lists", "product_prices", "outbox_events", "role_permissions",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration


def test_rbac_guard_uses_explicit_role_permission_binding():
    source = (ROOT / "apps/api/app/dependencies.py").read_text()
    assert "JOIN role_permissions rp ON rp.role_id = r.id" in source


def test_catalog_router_contains_core_routes():
    source = (ROOT / "apps/api/app/routes/catalog.py").read_text()
    for route_marker in [
        'prefix="/catalog"',
        'def categories',
        'def brands',
        'def units',
        'def products',
        'def create_variant',
        'def lookup_barcode',
        'def create_price',
    ]:
        assert route_marker in source
