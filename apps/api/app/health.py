import logging

from sqlalchemy import text

from .db import engine
from .config import settings

EXPECTED_DATABASE = "neondb"
REQUIRED_AUTH_MIGRATION = "028_phase0_auth_rls_runtime_hardening"
REQUIRED_AUTH_FUNCTION = "public.lexa_find_session_by_refresh_hash(text)"
logger = logging.getLogger("lexa.health")
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
    # Phase 2 universal transaction/workflow kernel remains technical infrastructure; it is not a user-facing module.
    "business_capabilities",
    "business_configurations",
    "party_relationships",
    "transaction_types",
    "transaction_lines",
    "transaction_status_history",
    "workflow_definitions",
    "workflow_steps",
    "workflow_instances",
    "workflow_step_runs",
    # Phase 3 Inventory Foundation must be present before the API reports ready.
    "idempotency_keys",
    "inventory_balances",
    "inventory_transactions",
    "inventory_adjustments",
    "inventory_adjustment_lines",
    "stock_counts",
    "stock_count_lines",
    "inventory_transfers",
    "inventory_transfer_lines",
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

            # A reachable database and all expected tables are not sufficient:
            # the API cannot restore a cookie-backed session unless the auth
            # lookup migration is installed, executable by lexa_app, and owned
            # by a SECURITY DEFINER role that bypasses RLS.
            auth_contract = connection.execute(
                text("""
                    SELECT
                        EXISTS (
                            SELECT 1 FROM public.schema_migrations
                            WHERE version = :required_migration
                        ) AS migration_present,
                        to_regprocedure(:required_function) IS NOT NULL AS function_present,
                        COALESCE(
                            has_function_privilege(
                                'lexa_app', to_regprocedure(:required_function), 'EXECUTE'
                            ), false
                        ) AS app_role_can_execute,
                        EXISTS (
                            SELECT 1
                            FROM pg_proc p
                            JOIN pg_roles owner_role ON owner_role.oid = p.proowner
                            WHERE p.oid = to_regprocedure(:required_function)
                              AND p.prosecdef
                              AND owner_role.rolbypassrls
                        ) AS function_owner_bypasses_rls
                """),
                {
                    "required_migration": REQUIRED_AUTH_MIGRATION,
                    "required_function": REQUIRED_AUTH_FUNCTION,
                },
            ).mappings().one()
            if not all(bool(auth_contract[key]) for key in (
                "migration_present", "function_present", "app_role_can_execute", "function_owner_bypasses_rls"
            )):
                if settings.app_env.strip().lower() != "production":
                    return False, {
                        "code": "LEXA_AUTH_SCHEMA_NOT_READY",
                        **{key: bool(auth_contract[key]) for key in auth_contract},
                    }
                return False, "LEXA_AUTH_SCHEMA_NOT_READY"

        return True, None
    except Exception as exc:
        # Keep production responses sanitized, but preserve the full DB exception in Render logs.
        logger.exception(
            "database_readiness_failed",
            extra={
                "database": EXPECTED_DATABASE,
                "project_id": canonical_identity()["project_id"],
                "branch_id": canonical_identity()["branch_id"],
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc)[:500],
                "exception_cause": repr(exc.__cause__)[:500] if exc.__cause__ else "",
            },
        )
        return False, exc.__class__.__name__
