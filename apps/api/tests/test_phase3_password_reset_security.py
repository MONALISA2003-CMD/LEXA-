"""Source-level release contract checks for Phase 3 account recovery/security.

These checks run without a live database. The 044 migration must still be tested on a
fresh disposable PostgreSQL database before a production migration is approved.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_password_reset_is_one_time_hashed_and_revokes_all_sessions():
    sql = read("migrations/044_phase3_password_reset_security.sql")
    assert "token_type = 'PASSWORD_RESET'" in sql
    assert "p_token_hash !~ '^[0-9a-f]{64}$'" in sql
    assert "SET password_hash = p_password_hash" in sql
    assert "UPDATE public.sessions" in sql and "WHERE user_id = v_user_id AND revoked_at IS NULL" in sql
    assert "used_at = now()" in sql
    for fn in ("lexa_issue_password_reset", "lexa_consume_password_reset", "lexa_revoke_password_reset"):
        assert f"FUNCTION public.{fn}" in sql
        assert f"REVOKE ALL ON FUNCTION public.{fn}" in sql
        assert f"GRANT EXECUTE ON FUNCTION public.{fn}" in sql
    assert sql.count("SECURITY DEFINER") == 3
    assert sql.count("SET search_path = pg_catalog, public") == 3


def test_reset_http_contract_has_generic_response_rate_limits_and_no_raw_token_storage():
    auth = read("apps/api/app/routes/auth.py")
    assert '@router.post("/forgot-password", status_code=202)' in auth
    assert '@router.post("/reset-password")' in auth
    assert "_enforce_password_reset_request_limit(request, email)" in auth
    assert "_enforce_password_reset_completion_limit(request)" in auth
    assert "token_hash = hash_refresh_token(raw_token)" in auth
    assert "lexa_issue_password_reset(:email, :token_hash, :expires_at)" in auth
    assert "If an active account matches that email" in auth
    assert "lexa_consume_password_reset(:token_hash, :password_hash)" in auth
    assert 'logger.error("password_reset_delivery_failed"' in auth
    assert "reset_url" in auth and "#token={raw_token}" in auth
    assert "parsed.scheme.lower() not in schemes" in auth
    assert 'parsed.path not in {"", "/"}' in auth
    assert "background_tasks.add_task(_deliver_password_reset_and_revoke_on_failure" in auth
    assert "settings.lexa_proxy_shared_secret.strip()) < 32" in auth
    assert "def _trusted_client_ip(request: Request)" in auth
    assert "from fastapi import APIRouter, BackgroundTasks" in auth


def test_password_reset_migration_is_a_readiness_gate_and_in_clean_replay_chain():
    health = read("apps/api/app/health.py")
    replay_script = read("scripts/run_clean_migration_replay.py")
    manifest = json.loads(read("migrations/reconstructed/clean_replay_order.json"))
    paths = [item["path"] for item in manifest["steps"]]
    for version in (
        "041_commerce_integrity_scaling",
        "042_team_chat_foundation",
        "043_phase5_journal_currency_guard",
        "044_phase3_password_reset_security",
    ):
        assert f'"{version}"' in health, f"Readiness gate is missing {version}"
    assert "lexa_consume_password_reset" in health
    assert "definer_owner_bypasses_rls" in health
    # Older migrations stay in order but must not be pinned to the end of the
    # chain: newer forward-only migrations follow 044.
    path_044 = "migrations/044_phase3_password_reset_security.sql"
    assert path_044 in paths
    assert paths.index("migrations/043_phase5_journal_currency_guard.sql") < paths.index(path_044)
    assert paths.index(path_044) < paths.index("migrations/045_intelligence_foundation.sql")
    assert paths.index("migrations/045_intelligence_foundation.sql") < paths.index("migrations/046_intelligence_documents.sql")
    assert "password_reset_contract_count != 8" in replay_script
    assert "044_phase3_password_reset_security" in replay_script


def test_security_sessions_are_scoped_to_signed_in_user_and_workspace():
    auth = read("apps/api/app/routes/auth.py")
    session_list = auth.split('def list_my_sessions(', 1)[1].split('@router.post("/sessions/{session_id}/revoke")', 1)[0]
    revoke = auth.split('def revoke_my_session(', 1)[1].split('@router.post("/register")', 1)[0]
    assert "WHERE s.tenant_id=:tenant_id AND s.user_id=:user_id" in session_list
    assert "s.revoked_at IS NULL AND s.expires_at>now()" in session_list
    assert "WHERE id=:session_id AND tenant_id=:tenant_id AND user_id=:user_id" in revoke
    assert "if session_id == current_session_id" in revoke
    assert "db.commit()" in revoke


def test_production_reset_url_is_https_and_credentials_cannot_be_embedded():
    config = read("apps/api/app/config.py")
    assert "public_app_url: str | None = None" in config
    assert 'expected_schemes = {"https"}' in config
    assert "public_url.username is not None or public_url.password is not None" in config
    assert 'public_url.path not in {"", "/"}' in config
    assert "public_app_url=settings.public_app_url" in config
    assert "lexa_proxy_shared_secret=settings.lexa_proxy_shared_secret" in config
    assert "LEXA_PROXY_SHARED_SECRET must be set" in config
