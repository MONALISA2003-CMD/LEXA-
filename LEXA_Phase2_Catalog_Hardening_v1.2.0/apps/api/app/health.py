from sqlalchemy import text

from .db import engine

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


def check_database() -> tuple[bool, str | None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
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
