from sqlalchemy import text

from .db import engine
from .config import settings

EXPECTED_DATABASE = "neondb"
REQUIRED_TABLES = (
    "schema_migrations",
    "tenants",
    "users",
    "tenant_memberships",
    "roles",
    "permissions",
    "membership_roles",
    "business_profiles",
    "registration_requests",
)


def _clean(value: object | None) -> str:
    """Normalize managed-environment identity values before comparison."""
    return str(value or "").strip()


def canonical_identity() -> dict[str, str]:
    """Return the identity LEXA expects from its canonical Neon database."""
    return {
        "database": EXPECTED_DATABASE,
        "project_id": _clean(settings.lexa_neon_project_id),
        "branch_id": _clean(settings.lexa_neon_branch_id),
    }


def _diagnostic(settings_key: str, expected: str, actual: str) -> dict[str, str]:
    return {"field": settings_key, "expected": expected, "actual": actual}


def check_database() -> tuple[bool, str | dict[str, object] | None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            identity = connection.execute(
                text("""
                    SELECT
                        current_database() AS database_name,
                        current_setting('neon.branch_id', true) AS branch_id,
                        current_setting('neon.project_id', true) AS project_id,
                        current_setting('neon.endpoint_id', true) AS endpoint_id
                """)
            ).mappings().one()

            actual = {
                "database": _clean(identity["database_name"]),
                "branch_id": _clean(identity["branch_id"]),
                "project_id": _clean(identity["project_id"]),
                "endpoint_id": _clean(identity["endpoint_id"]),
            }
            expected = canonical_identity()
            identity_ok = (
                actual["database"] == expected["database"]
                and actual["branch_id"] == expected["branch_id"]
                and actual["project_id"] == expected["project_id"]
            )
            if not identity_ok:
                if settings.app_env.strip().lower() != "production":
                    mismatch = None
                    for key in ("database", "project_id", "branch_id"):
                        if expected[key] != actual[key]:
                            mismatch = _diagnostic(key, expected[key], actual[key])
                            break
                    return False, {
                        "code": "LEXA_DATABASE_NOT_CANONICAL",
                        "expected": expected,
                        "actual": actual,
                        "mismatch": mismatch,
                    }
                return False, "LEXA_DATABASE_NOT_CANONICAL"

            result = connection.execute(
                text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = ANY(:required_tables)
                """),
                {"required_tables": list(REQUIRED_TABLES)},
            )
            present = {row[0] for row in result}
            missing = [table for table in REQUIRED_TABLES if table not in present]
            if missing:
                if settings.app_env.strip().lower() != "production":
                    return False, {
                        "code": "LEXA_SCHEMA_NOT_READY",
                        "missing_tables": missing,
                    }
                return False, "LEXA_SCHEMA_NOT_READY"

        return True, None
    except Exception as exc:
        return False, exc.__class__.__name__
