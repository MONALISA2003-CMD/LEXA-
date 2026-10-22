"""Regression tests for the sign-in workspace-context ordering bug."""
import os
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-for-login-context-contract")

import pytest

# The endpoint test replaces Redis rate limiting, password verification and the
# database session below. In minimal offline dev environments, provide import-only
# stand-ins for those three optional runtime packages so the route ordering itself
# can still be exercised. Normal CI uses the real packages installed from pyproject.
try:
    import redis  # noqa: F401
except ModuleNotFoundError:
    import sys
    import types
    redis_stub = types.ModuleType("redis")
    redis_stub.Redis = type("Redis", (), {"from_url": staticmethod(lambda *_args, **_kwargs: None)})
    sys.modules["redis"] = redis_stub

try:
    import pwdlib  # noqa: F401
except ModuleNotFoundError:
    import sys
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
    _original_create_engine = None
except ModuleNotFoundError:
    # app.db only builds an engine at import time; all requests in this test use
    # a fake DB. Avoid importing a real PostgreSQL driver or opening a connection.
    _original_create_engine = sqlalchemy.create_engine
    sqlalchemy.create_engine = lambda *_args, **_kwargs: None

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes import auth
except ModuleNotFoundError as exc:
    pytest.skip(
        f"API route test dependencies are not installed in this environment: {exc.name}",
        allow_module_level=True,
    )
finally:
    if _original_create_engine is not None:
        sqlalchemy.create_engine = _original_create_engine


class Rows:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, **kwargs):
        self.id = uuid4()
        self.__dict__.update(kwargs)


class FakeDb:
    def __init__(self, *, has_workspace=True):
        self.user = SimpleNamespace(id=uuid4(), email="member@example.com", is_active=True, password_hash="test-hash")
        self.tenant = SimpleNamespace(id=uuid4(), name="Test workspace", status="ACTIVE")
        self.membership = SimpleNamespace(id=uuid4(), tenant_id=self.tenant.id, user_id=self.user.id, status="ACTIVE")
        self.has_workspace = has_workspace
        self.user_context = None
        self.tenant_context = None
        self.pre_tenant_access = None
        self.pre_tenant_email = None
        self.workspace_lookup_context = None
        self.commits = 0
        self.added = []

    def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}
        if "set_config('app.pre_tenant_access'" in sql:
            self.pre_tenant_access = "login" if params.get("email") else ""
        if "set_config('app.pre_tenant_email'" in sql:
            self.pre_tenant_email = params.get("email", "")
        if "set_config('app.user_id'" in sql:
            self.user_context = params.get("user_id")
        if "set_config('app.tenant_id'" in sql:
            self.tenant_context = params.get("tenant_id")
        if "lexa_list_active_user_workspaces" in sql:
            self.workspace_lookup_context = self.user_context
            if self.has_workspace and self.user_context == params.get("user_id"):
                return Rows([{
                    "tenant_id": self.tenant.id,
                    "tenant_name": self.tenant.name,
                    "membership_id": self.membership.id,
                }])
            return Rows([])
        return Rows([])

    def scalar(self, statement):
        sql = str(statement).lower()
        if "from users" in sql:
            if self.pre_tenant_access == "login" and self.pre_tenant_email == self.user.email.lower():
                return self.user
            return None
        if "from tenant_memberships" in sql:
            return self.membership if self.tenant_context == str(self.tenant.id) else None
        if "from tenants" in sql:
            return self.tenant if self.tenant_context == str(self.tenant.id) else None
        return None

    def get(self, model, _identity):
        if model is auth.Tenant:
            return self.tenant
        return None

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


def make_client(db, monkeypatch):
    monkeypatch.setattr(auth, "_enforce_login_rate_limit", lambda *_args: None)
    monkeypatch.setattr(auth, "_clear_login_rate_limit", lambda *_args: None)
    monkeypatch.setattr(auth, "verify_password", lambda *_args: True)
    monkeypatch.setattr(auth, "AuthSession", FakeSession)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[auth.get_db] = lambda: db
    return TestClient(app)


def test_active_account_can_resolve_workspace_and_sign_in(monkeypatch):
    db = FakeDb(has_workspace=True)
    with make_client(db, monkeypatch) as client:
        response = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "valid-test-password"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == str(db.tenant.id)
    assert body["tenant_name"] == "Test workspace"
    assert body["access_token"]
    assert "lexa_refresh_token" in response.headers.get("set-cookie", "")
    assert db.pre_tenant_access == ""
    assert db.pre_tenant_email == ""
    assert db.workspace_lookup_context == str(db.user.id)
    assert db.user_context == str(db.user.id)
    assert db.tenant_context == str(db.tenant.id)
    assert db.commits == 1


def test_valid_password_without_active_workspace_gets_clear_account_guidance(monkeypatch):
    db = FakeDb(has_workspace=False)
    with make_client(db, monkeypatch) as client:
        response = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "valid-test-password"})

    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "NO_ACTIVE_WORKSPACE"
    assert "no active workspace" in response.json()["detail"]["message"].lower()
    assert db.workspace_lookup_context == str(db.user.id)
    assert db.commits == 0


def test_wrong_password_never_resolves_workspaces_or_creates_session(monkeypatch):
    db = FakeDb(has_workspace=True)
    client = make_client(db, monkeypatch)
    monkeypatch.setattr(auth, "verify_password", lambda *_args: False)
    with client:
        response = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "wrong-password"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
    assert db.workspace_lookup_context is None
    assert db.user_context is None
    assert db.commits == 0
    assert not db.added
