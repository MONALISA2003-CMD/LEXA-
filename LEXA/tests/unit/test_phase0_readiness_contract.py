from pathlib import Path

ROOT = Path(__file__).parents[2]
HEALTH = ROOT / "apps/api/app/health.py"
CONFIG = ROOT / "apps/api/app/config.py"
RENDER = ROOT / "render.yaml"
ENV = ROOT / ".env.example"


def test_canonical_lexa_identity_is_explicitly_locked():
    health = HEALTH.read_text()
    config = CONFIG.read_text()
    render = RENDER.read_text()
    env = ENV.read_text()

    for text in (config, render, env):
        assert "wispy-mud-75323042" in text
        assert "br-soft-star-b1dj2m2w" in text
    assert 'EXPECTED_DATABASE = "neondb"' in health
    assert "current_setting('neon.project_id'" in health
    assert "current_setting('neon.branch_id'" in health


def test_readiness_normalizes_managed_identity_values():
    health = HEALTH.read_text()
    assert 'return str(value or "").strip()' in health
    assert "settings.lexa_neon_branch_id" in health
    assert "settings.lexa_neon_project_id" in health
    assert 'settings.app_env.strip().lower() != "production"' in health


def test_render_carries_canonical_neon_identity():
    render = RENDER.read_text()
    assert "LEXA_NEON_PROJECT_ID" in render
    assert "LEXA_NEON_BRANCH_ID" in render
    assert "value: wispy-mud-75323042" in render
    assert "value: br-soft-star-b1dj2m2w" in render


def test_frontend_catalog_exit_condition_is_visible():
    page = (ROOT / "apps/web/app/products/page.tsx").read_text()
    api = (ROOT / "apps/web/lib/api.ts").read_text()
    assert "Products" in page
    assert "Pack sizes & options" in page
    assert "product code" in page.lower()
    assert "Pricing" in page
    assert "Barcodes" in page
    assert "getProducts" in page
    assert "getBarcodes" in api
    assert "createPrice" in api


def test_readiness_requires_phase2_universal_business_engine_schema():
    health = HEALTH.read_text()
    for table in (
        "business_capabilities",
        "business_configurations",
        "party_relationships",
        "transaction_types",
        "transaction_lines",
        "transaction_status_history",
        "workflow_definitions",
        "workflow_steps",
        "workflow_instances",
        "workflow_step_runs",
    ):
        assert f'"{table}"' in health


def test_readiness_requires_auth_refresh_migration_and_safe_function():
    health = HEALTH.read_text()
    assert 'REQUIRED_AUTH_MIGRATION = "028_phase0_auth_rls_runtime_hardening"' in health
    assert 'REQUIRED_AUTH_FUNCTION = "public.lexa_find_session_by_refresh_hash(text)"' in health
    assert "to_regprocedure(:required_function) IS NOT NULL" in health
    assert "app_role_can_execute" in health
    assert "function_owner_bypasses_rls" in health
    assert '"LEXA_AUTH_SCHEMA_NOT_READY"' in health


def test_readiness_requires_cache_and_database_before_claiming_ready():
    main = (ROOT / "apps/api/app/main.py").read_text()
    health = (ROOT / "apps/api/app/health.py").read_text()
    assert "cache_ok, cache_error = check_redis()" in main
    assert "ready = database_ok and cache_ok" in main
    assert '"cache": "ok" if cache_ok else "error"' in main
    assert "socket_connect_timeout=2" in health
    assert "socket_timeout=2" in health
    assert '"failure_code"] = "LEXA_DEPENDENCY_NOT_READY"' in main
