import logging

import redis
from sqlalchemy import text

from .db import engine
from .config import settings

EXPECTED_DATABASE = "neondb"
logger = logging.getLogger("lexa.health")

REQUIRED_TABLES = (
    "schema_migrations", "tenants", "users", "tenant_memberships", "roles", "permissions", "membership_roles",
    "business_profiles", "registration_requests", "tenant_settings", "membership_branch_assignments",
    "tenant_invitations", "user_security_tokens", "business_capabilities", "business_configurations",
    "party_relationships", "transaction_types", "transaction_lines", "transaction_status_history",
    "workflow_definitions", "workflow_steps", "workflow_instances", "workflow_step_runs", "idempotency_keys",
    "inventory_balances", "inventory_transactions", "inventory_adjustments", "inventory_adjustment_lines",
    "stock_counts", "stock_count_lines", "inventory_transfers", "inventory_transfer_lines",
    "analytics_refresh_runs", "analytics_daily_business_metrics", "analytics_branch_daily_metrics",
    "analytics_product_daily_metrics", "analytics_customer_purchase_patterns", "analytics_inventory_health_metrics",
    "brain_model_routes", "brain_runs", "brain_evidence", "brain_memories", "brain_recommendations",
    "brain_tool_definitions", "brain_tool_runs", "suppliers", "supplier_profiles", "supplier_product_prices",
    "supplier_variant_costs", "purchase_orders", "purchase_order_lines", "purchase_order_status_history",
    "purchase_receipts", "purchase_receipt_lines", "purchase_returns", "purchase_return_lines",
)

REQUIRED_MIGRATIONS = (
    "021_phase5_analytics_foundation",
    "022_phase6a_brain_foundation",
    "023_phase2_identity_tenancy_authorization_foundation",
    "027_release_convergence",
)

def _clean(value: object | None) -> str:
    return str(value or "").strip()

def canonical_identity() -> dict[str, str]:
    return {
        "database": EXPECTED_DATABASE,
        "project_id": _clean(settings.lexa_neon_project_id),
        "branch_id": _clean(settings.lexa_neon_branch_id),
    }

def check_database() -> tuple[bool, str | dict[str, object] | None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            identity = connection.execute(text("""
                SELECT current_database() AS database_name,
                       current_setting('neon.branch_id', true) AS branch_id,
                       current_setting('neon.project_id', true) AS project_id,
                       current_setting('neon.endpoint_id', true) AS endpoint_id
            """)).mappings().one()
            actual = {
                "database": _clean(identity["database_name"]),
                "branch_id": _clean(identity["branch_id"]),
                "project_id": _clean(identity["project_id"]),
                "endpoint_id": _clean(identity["endpoint_id"]),
            }
            expected = canonical_identity()
            for key in ("database", "project_id", "branch_id"):
                if actual[key] != expected[key]:
                    return False, "LEXA_DATABASE_NOT_CANONICAL" if settings.app_env.strip().lower() == "production" else {
                        "code": "LEXA_DATABASE_NOT_CANONICAL", "expected": expected, "actual": actual, "field": key
                    }
            present = {row[0] for row in connection.execute(text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = ANY(:required_tables)
            """), {"required_tables": list(REQUIRED_TABLES)})}
            missing = [t for t in REQUIRED_TABLES if t not in present]
            if missing:
                return False, "LEXA_SCHEMA_NOT_READY" if settings.app_env.strip().lower() == "production" else {
                    "code": "LEXA_SCHEMA_NOT_READY", "missing_tables": missing
                }
            migrations = {row[0] for row in connection.execute(text("""
                SELECT version FROM schema_migrations WHERE version = ANY(:required_migrations)
            """), {"required_migrations": list(REQUIRED_MIGRATIONS)})}
            missing_migrations = [m for m in REQUIRED_MIGRATIONS if m not in migrations]
            if missing_migrations:
                return False, "LEXA_MIGRATION_CONTRACT_NOT_READY" if settings.app_env.strip().lower() == "production" else {
                    "code": "LEXA_MIGRATION_CONTRACT_NOT_READY", "missing_migrations": missing_migrations
                }
        return True, None
    except Exception as exc:
        logger.exception("database_readiness_failed", extra={
            "database": EXPECTED_DATABASE,
            "project_id": canonical_identity()["project_id"],
            "branch_id": canonical_identity()["branch_id"],
            "exception_type": exc.__class__.__name__,
            "exception_message": str(exc)[:500],
        })
        return False, exc.__class__.__name__

def check_redis() -> tuple[bool, str | None]:
    client = None
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        return True, None
    except Exception as exc:
        logger.exception("redis_readiness_failed", extra={"exception_type": exc.__class__.__name__, "exception_message": str(exc)[:500]})
        return False, exc.__class__.__name__
    finally:
        if client is not None:
            try: client.close()
            except Exception: pass
