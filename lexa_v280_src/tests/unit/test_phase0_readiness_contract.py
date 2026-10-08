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
    assert "settings.app_env.strip().lower() == \"production\"" in health


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
    assert "Variants" in page
    assert "SKU" in page
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


def test_invite_page_uses_suspense_for_search_params():
    source = (ROOT / "apps/web/app/invite/page.tsx").read_text()
    assert "Suspense" in source
    assert "useSearchParams" in source


def test_invite_page_uses_suspense_for_search_params():
    source = (ROOT / "apps/web/app/invite/page.tsx").read_text()
    assert "Suspense" in source
    assert "useSearchParams" in source


def test_invite_page_uses_suspense_for_search_params():
    source = (ROOT / "apps/web/app/invite/page.tsx").read_text()
    assert "Suspense" in source
    assert "useSearchParams" in source


def test_invitation_api_contract_exists():
    api = (ROOT / "apps/web/lib/api.ts").read_text()
    backend = (ROOT / "apps/api/app/routes/auth.py").read_text()
    page = (ROOT / "apps/web/app/invite/page.tsx").read_text()
    assert "export function acceptInvitation" in api
    assert '@router.post("/accept-invitation")' in backend
    assert "lexa_get_invitation_by_token" in backend
    assert "Suspense" in page
