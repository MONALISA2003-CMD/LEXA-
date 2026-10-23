import logging

import redis
from sqlalchemy import text

from .db import apply_application_role, engine
from .config import settings

EXPECTED_DATABASE = "neondb"
REQUIRED_AUTH_MIGRATION = "028_phase0_auth_rls_runtime_hardening"
REQUIRED_AUTH_FUNCTION = "public.lexa_find_session_by_refresh_hash(text)"
# The API must not report full readiness while the transactional modules expect
# schema changes that have not been installed. Migration 032 is intentionally
# excluded: it is documented as QA-branch-only in migrations/SOURCE_RECOVERY.md.
REQUIRED_APP_MIGRATIONS = (
    "033_phase5_refund_settlement_consistency",
    "034_phase5_return_accounting_journals",
    "035_phase5_none_return_receivable_guard",
    "036_phase6_inventory_intelligence",
    "037_phase6_inventory_ageing_index",
    "038_phase6_movement_health_indexes",
    "039_phase7_supplier_ledger_landed_costs",
    "040_phase8_finance_workflows",
    "041_commerce_integrity_scaling",
    "042_team_chat_foundation",
    "043_phase5_journal_currency_guard",
    "044_phase3_password_reset_security",
    "045_phase8_reconciliation_closed_snapshot",
)
REQUIRED_SCHEMA_COLUMNS = (
    ("suppliers", "supplier_party_id"),
    ("expense_records", "reversal_journal_entry_id"),
    ("analytics_daily_business_metrics", "expense_reversals_total"),
)
logger = logging.getLogger("lexa.health")
REQUIRED_TABLES = (
    "schema_migrations",
    "tenants",
    "users",
    "sessions",
    "user_security_tokens",
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
    # Purchasing and finance records referenced by the current API release.
    "purchase_landed_costs",
    "purchase_landed_cost_allocations",
    "supplier_bills",
    "supplier_payments",
    "supplier_payment_allocations",
    "supplier_ledger_entries",
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


def check_redis() -> tuple[bool, str | None]:
    """Check the required Redis-compatible cache without leaking its URL."""
    client = None
    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        return True, None
    except Exception as exc:
        logger.warning(
            "cache_readiness_failed",
            extra={"dependency": "redis", "exception_type": exc.__class__.__name__},
        )
        return False, exc.__class__.__name__
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def check_database() -> tuple[bool, str | dict[str, object] | None]:
    try:
        with engine.connect() as connection:
            # Direct engine connections do not trigger Session.after_begin.
            # Apply the same least-privilege role before any catalog/schema reads.
            apply_application_role(connection)
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
                logger.warning(
                    "application_schema_readiness_failed",
                    extra={
                        "missing_tables": missing,
                        "database": actual["database"],
                        "project_id": actual["project_id"],
                        "branch_id": actual["branch_id"],
                    },
                )
                if settings.app_env.strip().lower() != "production":
                    return False, {
                        "code": "LEXA_SCHEMA_NOT_READY",
                        "missing_tables": missing,
                    }
                return False, "LEXA_SCHEMA_NOT_READY"

            # Check the exact migrations required by this API release. Full names
            # are used because historical migration number prefixes can collide.
            migration_result = connection.execute(
                text("SELECT version FROM public.schema_migrations WHERE version = ANY(:required_versions)"),
                {"required_versions": list(REQUIRED_APP_MIGRATIONS)},
            )
            present_migrations = {str(row[0]) for row in migration_result}
            missing_migrations = [v for v in REQUIRED_APP_MIGRATIONS if v not in present_migrations]

            column_result = connection.execute(text("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND (
                    (table_name = 'suppliers' AND column_name = 'supplier_party_id') OR
                    (table_name = 'expense_records' AND column_name = 'reversal_journal_entry_id') OR
                    (table_name = 'analytics_daily_business_metrics' AND column_name = 'expense_reversals_total')
                )
            """))
            present_columns = {(str(row[0]), str(row[1])) for row in column_result}
            missing_columns = [f"{table}.{column}" for table, column in REQUIRED_SCHEMA_COLUMNS if (table, column) not in present_columns]

            if missing_migrations or missing_columns:
                logger.warning(
                    "application_schema_readiness_failed",
                    extra={
                        "missing_migrations": missing_migrations,
                        "missing_columns": missing_columns,
                        "database": actual["database"],
                        "project_id": actual["project_id"],
                        "branch_id": actual["branch_id"],
                    },
                )
                if settings.app_env.strip().lower() != "production":
                    return False, {
                        "code": "LEXA_SCHEMA_NOT_READY",
                        "missing_migrations": missing_migrations,
                        "missing_columns": missing_columns,
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

            password_reset_contract = connection.execute(text("""
                SELECT
                  EXISTS (SELECT 1 FROM public.schema_migrations WHERE version='044_phase3_password_reset_security') AS migration_present,
                  to_regprocedure('public.lexa_issue_password_reset(text,text,timestamptz)') IS NOT NULL AS issue_present,
                  to_regprocedure('public.lexa_consume_password_reset(text,text)') IS NOT NULL AS consume_present,
                  to_regprocedure('public.lexa_revoke_password_reset(text)') IS NOT NULL AS revoke_present,
                  COALESCE(has_function_privilege('lexa_app', to_regprocedure('public.lexa_issue_password_reset(text,text,timestamptz)'), 'EXECUTE'), false) AS issue_executable,
                  COALESCE(has_function_privilege('lexa_app', to_regprocedure('public.lexa_consume_password_reset(text,text)'), 'EXECUTE'), false) AS consume_executable,
                  COALESCE(has_function_privilege('lexa_app', to_regprocedure('public.lexa_revoke_password_reset(text)'), 'EXECUTE'), false) AS revoke_executable,
                  (SELECT count(*)=3 FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
                    WHERE p.oid IN (
                      to_regprocedure('public.lexa_issue_password_reset(text,text,timestamptz)'),
                      to_regprocedure('public.lexa_consume_password_reset(text,text)'),
                      to_regprocedure('public.lexa_revoke_password_reset(text)')
                    ) AND p.prosecdef AND r.rolbypassrls) AS definer_owner_bypasses_rls
            """)).mappings().one()
            if not all(bool(password_reset_contract[key]) for key in password_reset_contract):
                logger.warning("password_reset_schema_readiness_failed", extra={key: bool(value) for key, value in password_reset_contract.items()})
                if settings.app_env.strip().lower() != "production":
                    return False, {"code": "LEXA_AUTH_SCHEMA_NOT_READY", **{key: bool(value) for key, value in password_reset_contract.items()}}
                return False, "LEXA_AUTH_SCHEMA_NOT_READY"

            reconciliation_snapshot_contract = connection.execute(text("""
                SELECT
                  EXISTS (SELECT 1 FROM public.schema_migrations WHERE version='045_phase8_reconciliation_closed_snapshot') AS migration_present,
                  to_regprocedure('public.refresh_reconciliation_channel_date(uuid,uuid,date)') IS NOT NULL AS function_present,
                  CASE WHEN to_regprocedure('public.refresh_reconciliation_channel_date(uuid,uuid,date)') IS NULL THEN false
                       ELSE array_length(regexp_split_to_array(
                         pg_get_functiondef(to_regprocedure('public.refresh_reconciliation_channel_date(uuid,uuid,date)')),
                         $$h.status <> 'CLOSED'$$), 1) = 3
                  END AS closed_snapshot_filter_present_twice
            """)).mappings().one()
            if not all(bool(reconciliation_snapshot_contract[key]) for key in reconciliation_snapshot_contract):
                logger.warning("closed_reconciliation_snapshot_schema_not_ready", extra={key: bool(value) for key, value in reconciliation_snapshot_contract.items()})
                if settings.app_env.strip().lower() != "production":
                    return False, {"code": "LEXA_FINANCE_SCHEMA_NOT_READY", **{key: bool(value) for key, value in reconciliation_snapshot_contract.items()}}
                return False, "LEXA_FINANCE_SCHEMA_NOT_READY"

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
