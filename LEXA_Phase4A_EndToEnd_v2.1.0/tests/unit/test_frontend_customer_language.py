from pathlib import Path

ROOT = Path(__file__).parents[2]
WEB = ROOT / "apps/web"

# These are implementation/deployment terms that should never be presented as customer copy.
FORBIDDEN_VISIBLE_PHRASES = (
    "LEXA_SCHEMA_NOT_READY",
    "LEXA API",
    "Request ID",
    "request id",
    "transactional database",
    "database is not ready",
    "API proxy",
    "backend",
    "frontend",
    "migration",
    "deployment details",
    "HTTP 500",
    "workspace ID",
)


def test_customer_facing_frontend_has_no_developer_diagnostics():
    files = list((WEB / "app").rglob("*.tsx")) + list((WEB / "lib").rglob("*.ts"))
    haystack = "\n".join(path.read_text() for path in files)
    lowered = haystack.lower()
    for phrase in FORBIDDEN_VISIBLE_PHRASES:
        assert phrase.lower() not in lowered, f"Developer-facing phrase remains in frontend source: {phrase}"


def test_brand_assets_are_present():
    public = WEB / "public"
    for name in [
        "lexa-mark.png",
        "lexa-wordmark.png",
        "lexa-icon.png",
        "lexa-icon-180.png",
        "lexa-icon-32.png",
    ]:
        assert (public / name).exists(), f"Missing LEXA brand asset: {name}"


def test_open_workspace_surface_has_safe_network_states():
    page = (WEB / "app/page.tsx").read_text()
    api = (WEB / "lib/api.ts").read_text()
    assert "openDevSession" in page
    assert "Preview" in page
    assert "We couldn't connect to LEXA right now." in api
    assert "Failed to fetch" not in api


def test_open_development_mode_is_not_enabled_by_production_guard():
    config = (ROOT / "apps/api/app/config.py").read_text()
    auth = (ROOT / "apps/api/app/routes/auth.py").read_text()
    assert "lexa_open_dev_mode" in config
    assert 'settings.app_env.strip().lower() == "production"' in auth
    assert '"/dev-session"' in auth


def test_workspace_opens_directly_in_development():
    page = (WEB / "app/page.tsx").read_text()
    assert "NEXT_PUBLIC_LEXA_OPEN_MODE" in page
    assert "openDevSession" in page
    assert "Preview" in page
