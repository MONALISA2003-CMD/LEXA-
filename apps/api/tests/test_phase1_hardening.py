import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT.parent / "web"


def test_production_config_has_fail_closed_validation():
    source = (ROOT / "app" / "config.py").read_text()
    assert "def validate_production_settings" in source
    assert 'database_app_role != "lexa_app"' in source
    assert "len(jwt_secret) < 32" in source
    assert "localhost" in source


def test_sqlalchemy_pool_is_bounded_and_pg_bouncer_safe():
    source = (ROOT / "app" / "db.py").read_text()
    assert "pool_size=5" in source
    assert "max_overflow=5" in source
    assert "pool_timeout=10" in source
    assert '"prepare_threshold": None' in source
    assert "statement_timeout" in source
    assert "idle_in_transaction_session_timeout" in source


def test_web_auth_never_persists_access_tokens_and_refreshes_with_cookie():
    page = (WEB_ROOT / "app" / "page.tsx").read_text()
    api = (WEB_ROOT / "lib" / "api.ts").read_text()
    proxy = (WEB_ROOT / "app" / "api" / "lexa" / "[...path]" / "route.ts").read_text()
    assert '"/login"' in page and '"/register"' in page
    assert "sessionStorage.setItem(\"lexa_access_token\"" not in page
    assert "sessionStorage.getItem(\"lexa_access_token\")" not in page
    assert "sessionStorage.getItem(\"lexa_access_token\")" not in api
    assert 'const cookie = request.headers.get("cookie")' in proxy
    assert "credentials: \"same-origin\"" in api


def test_auth_rate_limit_and_refresh_cookie_are_present():
    source = (ROOT / "app" / "routes" / "auth.py").read_text()
    assert "_enforce_login_rate_limit" in source
    assert "_enforce_registration_rate_limit" in source
    assert 'httponly=True' in source
    assert 'samesite="lax"' in source
    assert '"refresh_token": new_refresh' not in source


def test_source_contains_live_brain_migration():
    migration = ROOT.parent.parent / "migrations" / "022_phase6a_brain_foundation.sql"
    assert migration.exists()
    assert "brain_runs" in migration.read_text()
    assert "022_phase6a_brain_foundation" in migration.read_text()


def test_database_role_is_applied_per_transaction_for_pgbouncer():
    db = (ROOT / "app" / "db.py").read_text()
    assert '@event.listens_for(Session, "after_begin")' in db
    assert 'SET LOCAL ROLE' in db
    assert 'cursor.execute(f"SET ROLE {settings.database_app_role}")' not in db


def test_login_rate_limit_is_cleared_after_successful_authentication():
    source = (ROOT / "app" / "routes" / "auth.py").read_text()
    assert "_clear_login_rate_limit" in source
    values_block = source.split("RegistrationRequest).values(", 1)[1].split(").on_conflict_do_nothing", 1)[0]
    assert "password" not in values_block
    assert "_clear_login_rate_limit(request, email)" in source


def test_user_facing_business_engine_route_module_is_absent():
    assert not (ROOT / "app" / "routes" / "business_engine.py").exists()


def test_ci_and_manual_runtime_contract_are_present():
    repo = ROOT.parent.parent
    assert (repo / ".github" / "workflows" / "lexa-ci.yml").exists()
    backup = repo / "scripts" / "backup-neon.sh"
    assert backup.exists()
    assert "DATABASE_URL_UNPOOLED" in backup.read_text()


def test_registration_idempotency_hash_binds_password_without_persisting_it():
    source = (ROOT / "app" / "routes" / "auth.py").read_text()
    assert '"password": body.password' in source
    values_block = source.split('RegistrationRequest).values(', 1)[1].split(').on_conflict_do_nothing', 1)[0]
    assert 'password=' not in values_block
    assert 'password=body.password' not in values_block
