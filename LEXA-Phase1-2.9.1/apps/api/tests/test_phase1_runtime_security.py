"""Regression coverage for Phase 1 runtime-role hardening."""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-for-phase1-security")

ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.config import validate_production_settings  # noqa: E402


def load_role_helper(role: str):
    """Load the small helper without requiring the optional DB driver locally."""
    source_path = API_ROOT / "app" / "db.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "apply_application_role")
    isolated = ast.Module(body=[function], type_ignores=[])
    namespace = {"settings": SimpleNamespace(database_app_role=role), "re": re}
    exec(compile(ast.fix_missing_locations(isolated), str(source_path), "exec"), namespace)
    return namespace["apply_application_role"]


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def exec_driver_sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_application_role_switch_is_transaction_local_and_validated():
    connection = RecordingConnection()
    apply_application_role = load_role_helper("lexa_app")

    apply_application_role(connection)

    assert connection.statements == ["SET LOCAL ROLE lexa_app"]


def test_application_role_switch_rejects_sql_fragments():
    connection = RecordingConnection()
    apply_application_role = load_role_helper("lexa_app; DROP TABLE users")

    try:
        apply_application_role(connection)
    except ValueError as exc:
        assert "simple PostgreSQL role identifier" in str(exc)
    else:
        raise AssertionError("Unsafe role identifier was accepted")
    assert connection.statements == []


def test_production_database_requires_runtime_login_pooler_and_tls():
    common = dict(
        app_env="production",
        database_app_role="lexa_app",
        jwt_secret="x" * 40,
        cors_origins=["https://lexa-green.vercel.app"],
    )
    good = "postgresql://lexa_runtime:example@ep-test-pooler.c-5.neon.tech/neondb?sslmode=require"
    assert validate_production_settings(**common, database_url=good)

    safe_login_url = "postgresql://lexa_runtime_safe:example@ep-test-pooler.c-5.neon.tech/neondb?sslmode=require"
    assert validate_production_settings(**common, database_url=safe_login_url, database_login_role="lexa_runtime_safe")

    for bad_url in (
        "postgresql://neondb_owner:example@ep-test-pooler.c-5.neon.tech/neondb?sslmode=require",
        "postgresql://lexa_runtime:example@ep-test.c-5.neon.tech/neondb?sslmode=require",
        "postgresql://lexa_runtime:example@ep-test-pooler.c-5.neon.tech/neondb",
    ):
        try:
            validate_production_settings(**common, database_url=bad_url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Unsafe production database URL was accepted: {bad_url.split('@')[-1]}")


def test_readiness_applies_least_privilege_role_before_catalog_reads():
    source = (ROOT / "apps" / "api" / "app" / "health.py").read_text(encoding="utf-8")
    role_switch = source.index("apply_application_role(connection)")
    first_query = source.index('connection.execute(text("SELECT 1"))')
    assert role_switch < first_query


def test_runtime_role_migration_removes_elevation_and_preserves_app_role():
    migration = ROOT / "migrations" / "029_phase1_runtime_role_least_privilege.sql"
    sql = migration.read_text(encoding="utf-8").lower()
    assert "create role lexa_runtime_safe login noinherit nocreatedb nocreaterole noreplication nobypassrls" in sql
    assert "grant lexa_app to lexa_runtime_safe with inherit false, set true" in sql
    assert "revoke all privileges on all tables in schema public from lexa_runtime_safe" in sql
    assert "pg_has_role('lexa_runtime_safe', 'neon_superuser', 'member')" in sql
    assert "lexa_app" in sql and "cannot set role lexa_app" in sql
    assert "raise exception" in sql
    assert "029_phase1_runtime_role_least_privilege" in sql
