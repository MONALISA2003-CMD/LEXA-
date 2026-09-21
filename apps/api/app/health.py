from sqlalchemy import text

from .db import engine
from .config import settings

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


def check_database() -> tuple[bool, str | dict | None]:
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
            database_name = (identity["database_name"] or "").strip()
            branch_id = (identity["branch_id"] or "").strip()
            project_id = (identity["project_id"] or "").strip()
            endpoint_id = (identity["endpoint_id"] or "").strip()
            configured_branch_id = (settings.lexa_neon_branch_id or "").strip()
            canonical = database_name == "neondb" and branch_id == configured_branch_id
            if not canonical:
                # Development-only diagnostics. Never expose infrastructure identity
                # through readiness in production. This lets free Render instances
                # diagnose DB/branch mismatches without an interactive shell.
                if settings.app_env.strip().lower() != "production":
                    return False, {
                        "code": "LEXA_DATABASE_NOT_CANONICAL",
                        "expected": {
                            "database": "neondb",
                            "branch_id": configured_branch_id,
                        },
                        "actual": {
                            "database": database_name,
                            "branch_id": branch_id,
                            "project_id": project_id,
                            "endpoint_id": endpoint_id,
                        },
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
                return False, "LEXA_SCHEMA_NOT_READY"
        return True, None
    except Exception as exc:
        return False, exc.__class__.__name__
