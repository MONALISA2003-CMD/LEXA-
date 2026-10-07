from pathlib import Path

ROOT = Path(__file__).parents[2]
AUTH = ROOT / "apps/api/app/routes/auth.py"
CONFIG = ROOT / "apps/api/app/config.py"
RENDER = ROOT / "render.yaml"
API = ROOT / "apps/web/lib/api.ts"
PAGE = ROOT / "apps/web/app/page.tsx"


def test_development_session_route_is_removed_from_production_surface():
    auth = AUTH.read_text()
    api = API.read_text()
    page = PAGE.read_text()
    assert '@router.post("/dev-session")' not in auth
    assert '"/api/v1/auth/dev-session"' not in api
    assert "openDevSession" not in page
    assert "NEXT_PUBLIC_LEXA_OPEN_MODE" not in page


def test_production_configuration_is_fail_closed():
    config = CONFIG.read_text()
    render = RENDER.read_text()
    assert "def validate_production_settings" in config
    assert 'database_app_role != "lexa_app"' in config
    assert 'value: production' in render
    assert "LEXA_OPEN_DEV_MODE" not in render
    assert "LEXA_OPEN_DEV_EMAIL" not in render
    assert "LEXA_OPEN_DEV_WORKSPACE_NAME" not in render


def test_browser_session_restoration_uses_refresh_cookie_not_persistent_access_token():
    api = API.read_text()
    assert "restoreSession" in api
    assert 'credentials: "same-origin"' in api
    assert 'sessionStorage.getItem("lexa_access_token")' not in api
    assert 'sessionStorage.setItem("lexa_access_token"' not in api


def test_authentication_surface_has_safe_refresh_and_rate_limits():
    auth = AUTH.read_text()
    assert "_enforce_login_rate_limit" in auth
    assert "_enforce_registration_rate_limit" in auth
    assert "_clear_login_rate_limit" in auth
    assert 'httponly=True' in auth
    assert 'samesite="lax"' in auth
    assert 'return {\n        "access_token"' in auth
    assert '"refresh_token": refresh' not in auth
