from pathlib import Path

ROOT = Path(__file__).parents[2]
AUTH = ROOT / "apps/api/app/routes/auth.py"
MAIN = ROOT / "apps/api/app/main.py"
API = ROOT / "apps/web/lib/api.ts"
MIGRATION = ROOT / "migrations/008_workspace_registration_hardening.sql"


def test_registration_bootstraps_business_profile_and_is_idempotent():
    source = AUTH.read_text()
    assert "RegistrationRequest" in source
    assert "BusinessProfile(" in source
    assert 'country_code="UG"' in source
    assert 'currency_code="UGX"' in source
    assert "with_for_update()" in source
    assert "Idempotency-Key" in source
    assert 'event_type="workspace.created"' in source
    assert 'action="workspace.create"' in source


def test_registration_never_stores_plaintext_password_in_idempotency_record():
    source = AUTH.read_text()
    assert "request_hash({" in source
    assert "registration.response_body = response" in source
    assert "password_hash" in source
    # The idempotency table receives only the request digest, never the raw password field.
    assert "RegistrationRequest).values(" in source
    assert '"password": body.password' in source
    assert 'password_hash=hash_password(body.password)' in source


def test_request_id_is_returned_by_api():
    source = MAIN.read_text()
    assert "request_id_middleware" in source
    assert 'response.headers["X-Request-ID"]' in source


def test_web_registration_sends_idempotency_key():
    source = API.read_text()
    assert '"Idempotency-Key":key()' in source


def test_registration_hardening_migration_is_additive():
    source = MIGRATION.read_text()
    assert "CREATE TABLE IF NOT EXISTS registration_requests" in source
    assert "ON CONFLICT (version) DO NOTHING" in source
    assert "DROP TABLE" not in source.upper()
    assert "DELETE FROM" not in source.upper()
    assert "TRUNCATE" not in source.upper()


def test_proxy_keeps_internal_diagnostics_out_of_browser_responses():
    proxy = ROOT / "apps/web/app/api/lexa/[...path]/route.ts"
    source = proxy.read_text()
    assert 'response.headers.get("x-request-id")' not in source
    assert 'out.headers.set("x-request-id", responseRequestId)' not in source
    assert 'response.status >= 500' in source
    assert 'LEXA is temporarily unavailable. Please try again shortly.' in source


