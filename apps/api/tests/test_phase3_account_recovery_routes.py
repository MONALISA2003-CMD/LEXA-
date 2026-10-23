"""Isolated HTTP-level tests for Phase 3 recovery routes; no Neon/Render is contacted."""
import hashlib
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-for-phase3-account-recovery")
API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import pytest

# Import-only stubs keep this HTTP-level contract executable in minimal offline
# development containers. Normal CI/Render builds use dependencies from pyproject.
try:
    import redis  # noqa: F401
except ModuleNotFoundError:
    import types
    redis_stub = types.ModuleType("redis")
    redis_stub.Redis = type("Redis", (), {"from_url": staticmethod(lambda *_args, **_kwargs: None)})
    sys.modules["redis"] = redis_stub

try:
    import pwdlib  # noqa: F401
except ModuleNotFoundError:
    import types
    pwdlib_stub = types.ModuleType("pwdlib")
    class _PasswordHash:
        @classmethod
        def recommended(cls): return cls()
        def hash(self, _value): return "test-only-placeholder-hash"
        def verify(self, _value, _hashed): return False
    pwdlib_stub.PasswordHash = _PasswordHash
    sys.modules["pwdlib"] = pwdlib_stub

import sqlalchemy
try:
    import psycopg  # noqa: F401
except ModuleNotFoundError:
    sqlalchemy.create_engine = lambda *_args, **_kwargs: None

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.requests import Request
    from app.routes import auth
except ModuleNotFoundError as exc:
    pytest.skip(f"API route test dependencies are not installed: {exc.name}", allow_module_level=True)


class FakeResult:
    def __init__(self, row=None, value=None, rows=None):
        self.row = row
        self.value = value
        self.rows = rows or ([] if row is None else [row])
    def mappings(self):
        return self
    def first(self):
        return self.row
    def all(self):
        return self.rows
    def scalar_one(self):
        return self.value


class FakeDb:
    def __init__(self, issued_row=None, consumed=True, revoke_row=True):
        self.issued_row = issued_row
        self.consumed = consumed
        self.revoke_row = revoke_row
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
    def execute(self, statement, params=None):
        sql = str(statement)
        values = dict(params or {})
        self.calls.append((sql, values))
        if "lexa_issue_password_reset" in sql:
            return FakeResult(row=self.issued_row)
        if "lexa_consume_password_reset" in sql:
            return FakeResult(value=self.consumed)
        if "lexa_revoke_password_reset" in sql:
            return FakeResult(value=self.revoke_row)
        if "UPDATE public.sessions" in sql:
            return FakeResult(row={"id": values.get("session_id")})
        return FakeResult()
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): self.closed = True


class FakeRedis:
    counts = {}
    @classmethod
    def from_url(cls, *_args, **_kwargs):
        return cls()
    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]
    def expire(self, *_args): return True
    def close(self): pass


def configure(monkeypatch):
    FakeRedis.counts = {}
    monkeypatch.setattr(auth.redis.Redis, "from_url", FakeRedis.from_url)
    monkeypatch.setattr(auth.settings, "resend_api_key", "test-provider-key")
    monkeypatch.setattr(auth.settings, "email_from", "LEXA Test <security@example.test>")
    monkeypatch.setattr(auth.settings, "lexa_proxy_shared_secret", "s" * 40)
    monkeypatch.setattr(auth.settings, "public_app_url", "https://lexa-green.vercel.app")
    monkeypatch.setattr(auth.settings, "app_env", "production")
    monkeypatch.setattr(auth.settings, "password_reset_minutes", 20)
    monkeypatch.setattr(auth.settings, "redis_url", "redis://test.invalid/0")


def test_forgot_password_config_missing_fails_closed_before_account_lookup(monkeypatch):
    monkeypatch.setattr(auth.settings, "resend_api_key", "")
    db = FakeDb(issued_row={"user_id": str(uuid4()), "email": "user@example.com"})
    app = FastAPI(); app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[auth.get_db] = lambda: db
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/forgot-password", json={"email": "member@example.com"})
    assert response.status_code == 503
    assert db.calls == []


def test_forgot_password_has_generic_response_and_hashes_token_before_persisting(monkeypatch):
    configure(monkeypatch)
    sent = []
    monkeypatch.setattr(auth, "send_password_reset_email", lambda email, url: sent.append((email, url)))
    user_id = str(uuid4())
    active_db = FakeDb(issued_row={"user_id": user_id, "email": "member@example.com"})
    app = FastAPI(); app.include_router(auth.router, prefix="/api/v1")
    active_request_dbs = [active_db]
    app.dependency_overrides[auth.get_db] = lambda: active_request_dbs.pop(0)
    unknown_db = FakeDb(issued_row=None)
    active_request_dbs.append(unknown_db)
    with TestClient(app) as client:
        found = client.post("/api/v1/auth/forgot-password", json={"email": "member@example.com"})
        missing = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})

    assert found.status_code == missing.status_code == 202
    assert found.json() == missing.json()
    assert len(sent) == 1 and sent[0][0] == "member@example.com"
    issued = next((sql, values) for sql, values in active_db.calls if "lexa_issue_password_reset" in sql)
    persisted_hash = issued[1]["token_hash"]
    assert len(persisted_hash) == 64
    assert "raw_token" not in issued[1]
    token = parse_qs(urlsplit(sent[0][1]).fragment)["token"][0]
    assert persisted_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in str(active_db.calls)
    assert active_db.commits == 1
    assert unknown_db.commits == 1


def test_reset_password_consumes_one_time_token_and_clears_refresh_cookie(monkeypatch):
    configure(monkeypatch)
    db = FakeDb(consumed=True)
    monkeypatch.setattr(auth, "hash_password", lambda _password: "$argon2id$test-only-password-digest-which-is-long-enough-for-reset")
    app = FastAPI(); app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[auth.get_db] = lambda: db
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/reset-password", json={"token": "t" * 40, "new_password": "a very long test password"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "password_updated"
    assert "lexa_refresh_token" in response.headers.get("set-cookie", "")
    call = next((sql, params) for sql, params in db.calls if "lexa_consume_password_reset" in sql)
    assert call[1]["token_hash"] == hashlib.sha256(("t" * 40).encode()).hexdigest()
    assert call[1]["password_hash"].startswith("$argon2id$")
    assert db.commits == 1


def test_revoke_current_session_is_refused(monkeypatch):
    user_id, tenant_id, current_session = uuid4(), uuid4(), uuid4()
    db = FakeDb()
    app = FastAPI(); app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[auth.tenant_db] = lambda: (db, user_id, tenant_id, current_session)
    with TestClient(app) as client:
        response = client.post(f"/api/v1/auth/sessions/{current_session}/revoke")
    assert response.status_code == 409
    assert db.calls == []
    assert db.commits == 0


def test_rate_limit_client_ip_trusts_only_verified_proxy_headers(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(auth.settings, "lexa_proxy_shared_secret", "trusted-secret-value-longer-than-32-chars")
    direct = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("198.51.100.10", 1234), "server": ("test", 80), "scheme": "http", "query_string": b""})
    forged = Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"x-lexa-client-ip", b"203.0.113.9"), (b"x-lexa-proxy-secret", b"wrong-secret")], "client": ("198.51.100.10", 1234), "server": ("test", 80), "scheme": "http", "query_string": b""})
    trusted = Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"x-lexa-client-ip", b"203.0.113.9"), (b"x-lexa-proxy-secret", b"trusted-secret-value-longer-than-32-chars")], "client": ("198.51.100.10", 1234), "server": ("test", 80), "scheme": "http", "query_string": b""})
    assert auth._trusted_client_ip(direct) == "198.51.100.10"
    assert auth._trusted_client_ip(forged) == "198.51.100.10"
    assert auth._trusted_client_ip(trusted) == "203.0.113.9"


def test_delivery_failure_revokes_the_token_and_keeps_generic_http_response(monkeypatch):
    configure(monkeypatch)
    active_db = FakeDb(issued_row={"user_id": str(uuid4()), "email": "member@example.com"})
    cleanup_db = FakeDb()
    monkeypatch.setattr(auth, "send_password_reset_email", lambda *_args: (_ for _ in ()).throw(RuntimeError("provider fail")))
    monkeypatch.setattr(auth, "SessionLocal", lambda: cleanup_db)
    app = FastAPI(); app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[auth.get_db] = lambda: active_db
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/forgot-password", json={"email": "member@example.com"})
    assert response.status_code == 202
    assert "If an active account matches that email" in response.json()["message"]
    assert any("lexa_revoke_password_reset" in sql for sql, _ in cleanup_db.calls)
    assert cleanup_db.commits == 1 and cleanup_db.closed


def test_forgot_password_has_a_bounded_per_email_rate_limit(monkeypatch):
    configure(monkeypatch)
    db = FakeDb(issued_row=None)
    app = FastAPI(); app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[auth.get_db] = lambda: db
    with TestClient(app) as client:
        results = [client.post("/api/v1/auth/forgot-password", json={"email": "limited@example.com"}) for _ in range(5)]
    assert [response.status_code for response in results] == [202, 202, 202, 202, 429]
    assert all("limited@example.com" not in response.text for response in results)
