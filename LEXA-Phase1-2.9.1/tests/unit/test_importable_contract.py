from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_catalog_is_registered_in_main_source():
    source = (ROOT / "apps/api/app/main.py").read_text()
    assert "catalog" in source
    assert 'app.include_router(catalog.router, prefix="/api/v1")' in source


def test_catalog_module_is_present():
    assert (ROOT / "apps/api/app/catalog.py").exists()
    assert (ROOT / "apps/api/app/catalog_rules.py").exists()
