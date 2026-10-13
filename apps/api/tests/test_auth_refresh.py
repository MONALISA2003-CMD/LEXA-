import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

# The API config requires these settings at import time. Keep test-only values
# local to the test environment; existing deployment settings are not changed.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-for-refresh-contract")

import pytest

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routes import auth
except ModuleNotFoundError as exc:
    pytest.skip(
        f"API test dependencies are not installed in this environment: {exc.name}",
        allow_module_level=True,
    )


class FakeDb:
    def __init__(self):
        self.user_id = uuid4()
        self.tenant_id = uuid4()
        self.auth_session = SimpleNamespace(
            id=uuid4(),
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            revoked_at=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            refresh_token_hash="old-hash",
            last_used_at=None,
        )
        self.scalar_calls = 0
        self.commits = 0

    def scalar(self, _statement):
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            return self.auth_session
        return SimpleNamespace(status="ACTIVE")

    def get(self, model, _identity):
        if model is auth.User:
            return SimpleNamespace(id=self.user_id, is_active=True)
        if model is auth.Tenant:
            return SimpleNamespace(id=self.tenant_id, name="Test workspace")
        return None

    def commit(self):
        self.commits += 1


def test_cookie_refresh_accepts_request_without_json_body():
    db = FakeDb()
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[auth.get_db] = lambda: db

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/refresh",
            cookies={"lexa_refresh_token": "cookie-backed-refresh-token"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["tenant_name"] == "Test workspace"
    assert "lexa_refresh_token" in response.cookies
    assert db.commits == 1
