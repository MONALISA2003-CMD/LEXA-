"""Readiness gate for the Phase 7 purchasing authorization/accounting overlay.

The API must not report ready when the code requiring migration 048 is deployed
without its schema, RLS policy, or accounting triggers. This is a read-only gate.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from .config import settings
from .db import apply_application_role, engine

logger = logging.getLogger("lexa.health")
REQUIRED_MIGRATION = "048_phase7_approval_limits_reversals_accounting"


def check_phase7_release_schema() -> tuple[bool, str | dict[str, object] | None]:
    """Check the new Phase 7 database contract without touching business records."""
    try:
        with engine.connect() as connection:
            apply_application_role(connection)
            row = connection.execute(text("""
                SELECT
                  EXISTS (SELECT 1 FROM public.schema_migrations WHERE version=:version) AS migration_present,
                  to_regclass('public.purchase_approval_limits') IS NOT NULL AS approval_table_present,
                  to_regprocedure('public.enforce_purchase_order_approval_limit()') IS NOT NULL AS approval_guard_present,
                  to_regprocedure('public.post_purchase_receipt_journal(uuid)') IS NOT NULL AS receipt_journal_present,
                  to_regprocedure('public.post_supplier_ledger_journal(uuid)') IS NOT NULL AS supplier_journal_present,
                  EXISTS (
                    SELECT 1 FROM pg_class c
                    WHERE c.oid=to_regclass('public.purchase_approval_limits')
                      AND c.relrowsecurity AND c.relforcerowsecurity
                  ) AS approval_rls_forced,
                  EXISTS (
                    SELECT 1 FROM pg_policy p
                    WHERE p.polrelid=to_regclass('public.purchase_approval_limits')
                      AND p.polname='purchase_approval_limits_tenant_isolation'
                  ) AS approval_tenant_policy_present,
                  EXISTS (
                    SELECT 1 FROM pg_trigger t
                    WHERE t.tgrelid=to_regclass('public.purchase_receipts')
                      AND t.tgname='trg_purchasing_receipt_after_post' AND NOT t.tgisinternal
                  ) AS receipt_journal_trigger_present,
                  EXISTS (
                    SELECT 1 FROM pg_trigger t
                    WHERE t.tgrelid=to_regclass('public.supplier_ledger_entries')
                      AND t.tgname='trg_purchasing_supplier_ledger_after_insert' AND NOT t.tgisinternal
                  ) AS supplier_journal_trigger_present,
                  EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='purchase_returns'
                      AND column_name='reversal_reason'
                  ) AS return_reversal_columns_present
            """), {"version": REQUIRED_MIGRATION}).mappings().one()
            missing = [name for name, value in dict(row).items() if not bool(value)]
            if not missing:
                return True, None
            logger.warning("phase7_release_schema_not_ready", extra={"missing_contracts": missing})
            if settings.app_env.strip().lower() != "production":
                return False, {"code": "LEXA_SCHEMA_NOT_READY", "missing_phase7_contracts": missing}
            return False, "LEXA_SCHEMA_NOT_READY"
    except Exception as exc:
        logger.exception(
            "phase7_release_schema_probe_failed",
            extra={"exception_type": exc.__class__.__name__},
        )
        if settings.app_env.strip().lower() != "production":
            return False, {"code": "LEXA_SCHEMA_NOT_READY", "phase7_probe_error_type": exc.__class__.__name__}
        return False, "LEXA_SCHEMA_NOT_READY"
