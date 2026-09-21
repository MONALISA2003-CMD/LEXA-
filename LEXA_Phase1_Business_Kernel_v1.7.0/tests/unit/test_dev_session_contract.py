from pathlib import Path

ROOT = Path(__file__).parents[2]
AUTH = ROOT / "apps/api/app/routes/auth.py"
CONFIG = ROOT / "apps/api/app/config.py"
RENDER = ROOT / "render.yaml"
API = ROOT / "apps/web/lib/api.ts"


def test_dev_session_is_guarded_and_uses_real_session_tokens():
    source = AUTH.read_text()
    assert '@router.post("/dev-session")' in source
    assert 'settings.app_env.strip().lower() == "production"' in source
    assert 'not settings.lexa_open_dev_mode' in source
    assert 'create_access_token' in source


def test_dev_mode_configuration_exists_for_development_service():
    config = CONFIG.read_text()
    render = RENDER.read_text()
    assert "lexa_open_dev_mode" in config
    assert "LEXA_OPEN_DEV_MODE" in render
    assert 'value: "true"' in render
    assert 'value: development' in render


def test_web_client_can_boot_open_development_session():
    source = API.read_text()
    assert '"/api/v1/auth/dev-session"' in source


def test_dev_session_seed_imports_decimal_for_price_bootstrap():
    source = AUTH.read_text()
    assert "from decimal import Decimal" in source
    assert 'unit_price=Decimal("15000")' in source


def test_frontend_boot_rechecks_readiness_after_session_establishment():
    page = (ROOT / "apps/web/app/page.tsx").read_text()
    assert "await establishWorkspaceSession();" in page
    assert "await refreshSystem();" in page
    assert 'r.status !== "ready"' in page
    assert "setTimeout(boot, 1500)" in page
    assert "setTimeout(boot, 2000)" in page
