#!/usr/bin/env python3
"""Plan or execute the documented LEXA clean-replay candidate against a disposable PostgreSQL DB.

Default mode is plan-only and never opens a database connection. `--apply` has deliberately
strict loopback/database-name/empty-schema guards and should only be used by CI or a disposable
local database. It must never be pointed at Neon or any production hostname.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ORDER_PATH = ROOT / "migrations/reconstructed/clean_replay_order.json"
DISPOSITION_PATH = ROOT / "migrations/migration_dispositions.json"
OUT_DIR = ROOT / "artifacts"
EVIDENCE_PATH = OUT_DIR / "phase6-replay-evidence.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_inputs() -> tuple[list[dict[str, str]], str]:
    manifest = json.loads(ORDER_PATH.read_text(encoding="utf-8"))
    inputs: list[dict[str, str]] = []
    seen: set[str] = set()
    for step in manifest.get("steps", []):
        rel = step.get("path", "")
        if not rel or rel in seen:
            raise ValueError(f"empty or duplicate replay path: {rel!r}")
        seen.add(rel)
        path = (ROOT / rel).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():
            raise ValueError(f"replay input missing or escapes repository: {rel}")
        raw = path.read_bytes()
        declared_blob = step.get("git_blob_sha1")
        if declared_blob:
            actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if actual_blob != declared_blob:
                raise ValueError(f"declared Git blob SHA-1 mismatch for {rel}: expected {declared_blob}, got {actual_blob}")
        inputs.append({"path": rel, "sha256": sha256_bytes(raw), "mode": str(step.get("mode", "unspecified"))})
    if not inputs:
        raise ValueError("clean replay manifest has no steps")
    blob = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return inputs, sha256_bytes(blob)


def safe_target(url: str) -> tuple[bool, str]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    dbname = (parsed.path or "").lstrip("/").lower()
    loopback = host in {"127.0.0.1", "localhost", "::1"}
    disposable_name = any(token in dbname for token in ("replay", "test", "ci"))
    forbidden_name = dbname in {"neondb", "postgres", "production", "prod", "lexa"}
    if parsed.scheme not in {"postgres", "postgresql"}:
        return False, "DATABASE_URL must use postgres/postgresql"
    if not loopback:
        return False, "DATABASE_URL host must be loopback; remote databases are forbidden"
    if not disposable_name or forbidden_name:
        return False, "database name must explicitly identify a disposable replay/test/CI database"
    return True, "safe disposable local target"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--plan-only", action="store_true", help="validate all paths and checksums without connecting to a DB (default)")
    group.add_argument("--apply", action="store_true", help="apply candidate sequence to an empty disposable loopback PostgreSQL database")
    parser.add_argument("--output", type=Path, default=EVIDENCE_PATH, help="replay evidence JSON destination")
    args = parser.parse_args()

    try:
        manifest = json.loads(ORDER_PATH.read_text(encoding="utf-8"))
        dispositions = json.loads(DISPOSITION_PATH.read_text(encoding="utf-8"))
        inputs, bundle_sha = canonical_inputs()
    except Exception as exc:
        print(f"ERROR: replay plan invalid: {exc}", file=sys.stderr)
        return 2

    if dispositions.get("historical_recovery_gate") != "CLOSED_BY_PERMANENT_DISPOSITION":
        print("ERROR: historical recovery policy has drifted; review permanent dispositions", file=sys.stderr)
        return 2
    if len(dispositions.get("permanently_replaced_sources", [])) != 6:
        print("ERROR: Phase 3 disposition register must contain exactly six approved replacements", file=sys.stderr)
        return 2

    if not args.apply:
        print(f"PLAN PASS: {len(inputs)} migration inputs are present and hashed.")
        print(f"Migration bundle SHA-256: {bundle_sha}")
        print("No database connection opened; no SQL executed.")
        for item in inputs:
            print(f"  {item['mode']}: {item['path']} [{item['sha256'][:12]}]")
        return 0

    if os.environ.get("LEXA_ALLOW_DISPOSABLE_REPLAY") != "1":
        print("ERROR: --apply requires LEXA_ALLOW_DISPOSABLE_REPLAY=1", file=sys.stderr)
        return 2
    database_url = os.environ.get("DATABASE_URL", "").strip()
    allowed, reason = safe_target(database_url)
    if not allowed:
        print(f"ERROR: unsafe replay target: {reason}", file=sys.stderr)
        return 2
    if not shutil.which("psql"):
        print("ERROR: psql client is required to apply the replay sequence", file=sys.stderr)
        return 2
    try:
        import psycopg
    except ImportError:
        print("ERROR: psycopg is required for replay safety and postcondition checks", file=sys.stderr)
        return 2

    try:
        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
                count = cur.fetchone()[0]
                if count:
                    raise RuntimeError(f"refusing to replay into a non-empty public schema ({count} tables found)")
                cur.execute("SELECT current_database(), inet_server_addr()::text")
                dbname, server_addr = cur.fetchone()
                if dbname.lower() in {"neondb", "postgres", "production", "prod", "lexa"}:
                    raise RuntimeError("target database name is not an allowed disposable name")
        # Migration 029 references Neon’s platform role when checking role
        # membership. Vanilla PostgreSQL CI containers do not have that role,
        # so create an empty NOLOGIN compatibility role only in this already-
        # guarded disposable loopback database. This gives it no privileges and
        # never connects to or modifies a Neon/production database.
        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s",
                    ("neon_superuser",),
                )
                if cur.fetchone() is None:
                    cur.execute("CREATE ROLE neon_superuser NOLOGIN")
                    print(
                        "Created disposable replay compatibility role "
                        "neon_superuser (NOLOGIN)."
                    )

        completed: list[str] = []
        env = os.environ.copy()
        env["PGCONNECT_TIMEOUT"] = "5"
        for step, item in zip(manifest["steps"], inputs, strict=True):
            path = ROOT / item["path"]
            result = subprocess.run(
                ["psql", "-X", "-v", "ON_ERROR_STOP=1", database_url, "-f", str(path)],
                cwd=ROOT, env=env, text=True, capture_output=True, timeout=120, check=False,
            )
            if result.returncode:
                raise RuntimeError(
                    f"SQL replay failed at {item['path']} ({result.returncode})\n"
                    f"STDOUT tail:\n{result.stdout[-5000:]}\nSTDERR tail:\n{result.stderr[-5000:]}"
                )
            completed.append(item["path"])

        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT count(*) AS total,
                           count(*) FILTER (WHERE c.relrowsecurity) AS enabled,
                           count(*) FILTER (WHERE c.relforcerowsecurity) AS forced,
                           count(*) FILTER (WHERE NOT c.relrowsecurity OR NOT c.relforcerowsecurity) AS gaps
                      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                     WHERE n.nspname='public' AND c.relkind='r'
                """)
                rls_total, rls_enabled, rls_forced, rls_gaps = cur.fetchone()
                cur.execute("""
                    SELECT version FROM public.schema_migrations
                     WHERE version IN ('029_phase3_runtime_privilege_surface','029_phase1_runtime_role_least_privilege',
                       '030_phase3_workspace_memberships','031_phase3_auth_surface_rls',
                       '033_phase5_refund_settlement_consistency','034_phase5_return_accounting_journals',
                       '035_phase5_none_return_receivable_guard','036_phase6_inventory_intelligence',
                       '037_phase6_inventory_ageing_index','038_phase6_movement_health_indexes','039_phase7_supplier_ledger_landed_costs',
                       '040_phase8_finance_workflows','041_commerce_integrity_scaling','042_team_chat_foundation','043_phase5_journal_currency_guard','044_phase3_password_reset_security')
                """)
                migration_rows = sorted(row[0] for row in cur.fetchall())
                expected_migrations = sorted([
                    '029_phase3_runtime_privilege_surface','029_phase1_runtime_role_least_privilege',
                    '030_phase3_workspace_memberships','031_phase3_auth_surface_rls',
                    '033_phase5_refund_settlement_consistency','034_phase5_return_accounting_journals',
                    '035_phase5_none_return_receivable_guard','036_phase6_inventory_intelligence',
                    '037_phase6_inventory_ageing_index','038_phase6_movement_health_indexes','039_phase7_supplier_ledger_landed_costs',
                    '040_phase8_finance_workflows','041_commerce_integrity_scaling','042_team_chat_foundation','043_phase5_journal_currency_guard','044_phase3_password_reset_security',
                ])
                cur.execute("""
                    SELECT
                      EXISTS (SELECT 1 FROM public.schema_migrations WHERE version='044_phase3_password_reset_security'),
                      to_regprocedure('public.lexa_issue_password_reset(text,text,timestamptz)') IS NOT NULL,
                      to_regprocedure('public.lexa_consume_password_reset(text,text)') IS NOT NULL,
                      to_regprocedure('public.lexa_revoke_password_reset(text)') IS NOT NULL,
                      (SELECT count(*)=3 FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
                        WHERE p.oid IN (
                          to_regprocedure('public.lexa_issue_password_reset(text,text,timestamptz)'),
                          to_regprocedure('public.lexa_consume_password_reset(text,text)'),
                          to_regprocedure('public.lexa_revoke_password_reset(text)')
                        ) AND p.prosecdef AND r.rolbypassrls),
                      has_function_privilege('lexa_app', to_regprocedure('public.lexa_issue_password_reset(text,text,timestamptz)'), 'EXECUTE'),
                      has_function_privilege('lexa_app', to_regprocedure('public.lexa_consume_password_reset(text,text)'), 'EXECUTE'),
                      has_function_privilege('lexa_app', to_regprocedure('public.lexa_revoke_password_reset(text)'), 'EXECUTE')
                """)
                (password_reset_migration, password_reset_issue, password_reset_consume, password_reset_revoke,
                 password_reset_owner_rls, password_reset_exec_issue, password_reset_exec_consume,
                 password_reset_exec_revoke) = cur.fetchone()
                password_reset_contract_count = sum(bool(x) for x in (
                    password_reset_migration, password_reset_issue, password_reset_consume, password_reset_revoke,
                    password_reset_owner_rls, password_reset_exec_issue, password_reset_exec_consume,
                    password_reset_exec_revoke))
                cur.execute("""
                    SELECT to_regclass('public.inventory_replenishment_policies') IS NOT NULL,
                           COALESCE((SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='public.inventory_replenishment_policies'::regclass), false),
                           has_table_privilege('lexa_app','public.permissions','INSERT'),
                           has_table_privilege('lexa_app','public.schema_migrations','INSERT'),
                           (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                             WHERE n.nspname='public' AND p.proname IN ('refresh_sale_payment_totals','post_sale_return_journal','post_sale_return_cogs_journal','create_fiscal_document_for_return'))
                """)
                policy_exists, policy_rls, can_write_permissions, can_write_migrations, routine_count = cur.fetchone()
                cur.execute("""
                    SELECT count(*) FROM pg_policies
                     WHERE schemaname='public' AND tablename='inventory_replenishment_policies'
                       AND policyname='inventory_replenishment_policies_tenant_isolation'
                """)
                policy_count = cur.fetchone()[0]
                cur.execute("""
                    SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND indexname='idx_inventory_transactions_age_analysis'
                """)
                age_index_count = cur.fetchone()[0]
                cur.execute("""
                    SELECT count(*)
                      FROM pg_index i
                      JOIN pg_class idx ON idx.oid=i.indexrelid
                      JOIN pg_namespace n ON n.oid=idx.relnamespace
                     WHERE n.nspname='public' AND i.indisvalid AND i.indisready
                       AND idx.relname IN (
                         'idx_sales_inventory_movement_history',
                         'idx_transaction_lines_variant_demand',
                         'idx_sale_returns_movement_history',
                         'idx_sale_return_lines_variant_movement'
                       )
                """)
                health_index_count = cur.fetchone()[0]
                cur.execute("""
                    SELECT
                      count(*) FILTER (WHERE t.relname IN ('purchase_landed_costs','purchase_landed_cost_allocations','supplier_bills','supplier_payments','supplier_payment_allocations','supplier_ledger_entries') AND t.relrowsecurity AND t.relforcerowsecurity),
                      count(*) FILTER (WHERE t.relname IN ('purchase_landed_costs','purchase_landed_cost_allocations','supplier_bills','supplier_payments','supplier_payment_allocations','supplier_ledger_entries')),
                      count(*) FILTER (WHERE t.relname IN ('purchase_landed_costs','purchase_landed_cost_allocations','supplier_bills','supplier_payments','supplier_payment_allocations','supplier_ledger_entries') AND EXISTS (
                        SELECT 1 FROM pg_policies p WHERE p.schemaname='public' AND p.tablename=t.relname AND p.policyname=t.relname || '_tenant_isolation'
                      )),
                      (SELECT to_regclass('public.uq_supplier_variant_cost_active_tier') IS NOT NULL),
                      (SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='purchase_orders' AND column_name='updated_at')),
                      (SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='supplier_bills' AND column_name='match_status')),
                      (SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='purchase_return_lines' AND column_name='supplier_credit_unit_cost')),
                      (NOT has_table_privilege('lexa_app','public.purchase_landed_costs','UPDATE') AND NOT has_table_privilege('lexa_app','public.purchase_landed_costs','DELETE')
                       AND NOT has_table_privilege('lexa_app','public.purchase_landed_cost_allocations','UPDATE') AND NOT has_table_privilege('lexa_app','public.purchase_landed_cost_allocations','DELETE')
                       AND NOT has_table_privilege('lexa_app','public.supplier_payment_allocations','UPDATE') AND NOT has_table_privilege('lexa_app','public.supplier_payment_allocations','DELETE')
                       AND NOT has_table_privilege('lexa_app','public.supplier_ledger_entries','UPDATE') AND NOT has_table_privilege('lexa_app','public.supplier_ledger_entries','DELETE')),
                      (has_table_privilege('lexa_app','public.supplier_bills','UPDATE') AND has_table_privilege('lexa_app','public.supplier_payments','UPDATE')
                       AND NOT has_table_privilege('lexa_app','public.supplier_bills','DELETE') AND NOT has_table_privilege('lexa_app','public.supplier_payments','DELETE'))
                    FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace
                    WHERE n.nspname='public' AND t.relkind='r'
                """)
                (phase7_rls_forced, phase7_table_count, phase7_policy_count, phase7_cost_index, po_updated_at,
                 bill_match_column, return_supplier_cost, phase7_append_only_grants, phase7_bill_payment_lifecycle_grants) = cur.fetchone()
                cur.execute("""
                    SELECT
                      EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='expense_records' AND column_name='reversal_journal_entry_id'),
                      EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_expense_records_reversal'),
                      to_regprocedure('public.post_expense_journal(uuid,uuid)') IS NOT NULL,
                      EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='analytics_daily_business_metrics' AND column_name='expense_reversals_total'),
                      EXISTS (SELECT 1 FROM pg_constraint WHERE conname='expense_records_reversal_journal_tenant_fk' AND conrelid='public.expense_records'::regclass),
                      EXISTS (SELECT 1 FROM pg_constraint WHERE conname='expense_records_status_check' AND conrelid='public.expense_records'::regclass AND pg_get_constraintdef(oid) LIKE '%REVERSED%')
                """)
                (phase8_reversal_column, phase8_reversal_index, phase8_expense_posting_function,
                 phase8_expense_reversal_metric, phase8_reversal_fk, phase8_status_constraint) = cur.fetchone()
                cur.execute("""
                    SELECT
                      count(*) FILTER (WHERE c.relname IN ('team_conversations','team_messages','team_conversation_reads')),
                      count(*) FILTER (WHERE c.relname IN ('team_conversations','team_messages','team_conversation_reads') AND c.relrowsecurity AND c.relforcerowsecurity),
                      count(*) FILTER (WHERE c.relname IN ('team_conversations','team_messages','team_conversation_reads') AND EXISTS (
                        SELECT 1 FROM pg_policies p WHERE p.schemaname='public' AND p.tablename=c.relname
                      )),
                      EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='sales' AND column_name='business_date'),
                      EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_sales_tenant_business_date_status'),
                      (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='public.analytics_refresh_queue'::regclass),
                      to_regprocedure('public.process_analytics_refresh_queue(integer)') IS NOT NULL,
                      position('Journal lines and any account denomination must use the journal entry currency' in
                        pg_get_functiondef(to_regprocedure('public.post_journal_entry(uuid,uuid)'))) > 0,
                      has_function_privilege('lexa_app','public.post_journal_entry(uuid,uuid)','EXECUTE')
                    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND c.relkind='r'
                """)
                (team_chat_tables, team_chat_rls_forced, team_chat_policy_tables, sales_business_date_column,
                 sales_business_date_index, analytics_queue_rls_forced, analytics_queue_worker,
                 journal_entry_currency_guard, journal_posting_grant) = cur.fetchone()
                cur.execute("""
                    SELECT count(*) FROM information_schema.tables
                     WHERE table_schema='public' AND table_type='BASE TABLE'
                """)
                table_count = cur.fetchone()[0]

        # Runtime-role adversarial probe: create disposable tenant context, prove that
        # lexa_app cannot read or create another tenant's settings, then roll back ALL fixtures.
        tenant_read_isolated = False
        tenant_write_denied = False
        try:
            import uuid
            tenant_a, tenant_b = str(uuid.uuid4()), str(uuid.uuid4())
            with psycopg.connect(database_url, connect_timeout=5) as conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO public.tenants(id,name) VALUES (%s,'Phase6 replay tenant A'),(%s,'Phase6 replay tenant B')", (tenant_a, tenant_b))
                        cur.execute("INSERT INTO public.tenant_settings(tenant_id) VALUES (%s)", (tenant_a,))
                        cur.execute("SET LOCAL ROLE lexa_app")
                        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))
                        cur.execute("SELECT count(*) FROM public.tenant_settings WHERE tenant_id=%s", (tenant_b,))
                        tenant_read_isolated = cur.fetchone()[0] == 0
                        cur.execute("SAVEPOINT phase6_cross_tenant_write_probe")
                        try:
                            cur.execute("INSERT INTO public.tenant_settings(tenant_id) VALUES (%s)", (tenant_b,))
                        except psycopg.errors.InsufficientPrivilege:
                            cur.execute("ROLLBACK TO SAVEPOINT phase6_cross_tenant_write_probe")
                            tenant_write_denied = True
                        else:
                            cur.execute("ROLLBACK TO SAVEPOINT phase6_cross_tenant_write_probe")
                            tenant_write_denied = False
                        cur.execute("RELEASE SAVEPOINT phase6_cross_tenant_write_probe")
                finally:
                    conn.rollback()
        except Exception as probe_error:
            failures_for_probe = f"runtime tenant-isolation probe failed: {type(probe_error).__name__}: {probe_error}"
        else:
            failures_for_probe = None

        failures = []
        if failures_for_probe: failures.append(failures_for_probe)
        if not tenant_read_isolated: failures.append("lexa_app could read another tenant's settings in runtime RLS probe")
        if not tenant_write_denied: failures.append("lexa_app could write another tenant's settings in runtime RLS probe")
        if rls_gaps: failures.append(f"{rls_gaps} of {rls_total} public tables lack enabled+forced RLS")
        if migration_rows != expected_migrations: failures.append(f"required migration ledger rows differ: found {migration_rows}")
        if not policy_exists or not policy_rls or policy_count != 1: failures.append("Phase 6 replenishment table/RLS/policy contract failed")
        if can_write_permissions or can_write_migrations: failures.append("lexa_app can mutate permission or schema migration reference data")
        if routine_count != 4: failures.append(f"expected four required return/accounting routines, found {routine_count}")
        if age_index_count != 1: failures.append("Phase 6 stock-age analysis index is missing")
        if health_index_count != 4: failures.append(f"Phase 6 movement-health indexes are incomplete or invalid: found {health_index_count}/4")
        if password_reset_contract_count != 8:
            failures.append(f"Phase 3 password-reset migration/functions/owner/grants contract failed: {password_reset_contract_count}/8 checks passed")
        if phase7_table_count != 6 or phase7_rls_forced != 6 or phase7_policy_count != 6:
            failures.append(f"Phase 7 supplier/landed-cost tables must all exist with forced RLS and tenant policies: tables={phase7_table_count}/6, forced={phase7_rls_forced}/6, policies={phase7_policy_count}/6")
        if not phase7_cost_index: failures.append("Phase 7 active supplier cost tier uniqueness index is missing")
        if not po_updated_at: failures.append("Phase 7 purchase-order updated_at contract is missing")
        if not bill_match_column: failures.append("Phase 7 supplier bill receipt-match contract is missing")
        if not return_supplier_cost: failures.append("Phase 7 supplier-return credit unit-cost separation is missing")
        if not phase7_append_only_grants: failures.append("Phase 7 landed-cost/allocation/supplier-ledger rows are not protected by append-only runtime grants")
        if not phase7_bill_payment_lifecycle_grants: failures.append("Phase 7 bills/payments lifecycle grants are broader than required or do not permit updates")
        if not phase8_reversal_column: failures.append("Phase 8 expense reversal reference column is missing")
        if not phase8_reversal_index: failures.append("Phase 8 expense reversal lookup index is missing")
        if not phase8_expense_posting_function: failures.append("Phase 8 expense journal posting routine is missing")
        if not phase8_expense_reversal_metric: failures.append("Phase 8 expense-correction reporting column is missing")
        if not phase8_reversal_fk: failures.append("Phase 8 expense reversal journal reference is not tenant-safe")
        if not phase8_status_constraint: failures.append("Phase 8 expense lifecycle does not allow the supported correction status")
        if team_chat_tables != 3 or team_chat_rls_forced != 3 or team_chat_policy_tables != 3:
            failures.append(f"Team chat tables must all exist with forced RLS and scoped policies: tables={team_chat_tables}/3, forced={team_chat_rls_forced}/3, policies={team_chat_policy_tables}/3")
        if not sales_business_date_column or not sales_business_date_index:
            failures.append("Commerce business-date ledger column or query index is missing")
        if not analytics_queue_rls_forced or not analytics_queue_worker:
            failures.append("Durable analytics queue forced-RLS or worker function is missing")
        if not journal_entry_currency_guard:
            failures.append("Journal posting routine lacks the single-currency guard")
        if not journal_posting_grant:
            failures.append("Runtime role lacks the approved execute grant for journal posting")

        evidence = {
            "schema_version": 1,
            "status": "FAIL" if failures else "PASS",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_commit": os.environ.get("GITHUB_SHA") or os.environ.get("LEXA_SOURCE_COMMIT") or "LOCAL_UNPINNED",
            "target_database": dbname,
            "target_server_addr": server_addr,
            "disposable_target_guard": reason,
            "historical_recovery_gate": "CLOSED_BY_PERMANENT_DISPOSITION",
            "historical_byte_parity_asserted": False,
            "migration_bundle_sha256": bundle_sha,
            "migration_inputs": inputs,
            "completed_sql_steps": completed,
            "public_table_count": table_count,
            "rls": {"public_tables": rls_total, "enabled": rls_enabled, "forced": rls_forced, "gaps": rls_gaps},
            "required_live_source_rows": migration_rows,
            "phase6_replenishment_table_exists": bool(policy_exists),
            "phase6_replenishment_rls_forced": bool(policy_rls),
            "phase6_replenishment_tenant_policy_count": policy_count,
            "phase6_inventory_age_index_count": age_index_count,
            "phase6_inventory_health_index_count": health_index_count,
            "phase7_supplier_ledger_tables": phase7_table_count,
            "phase7_supplier_ledger_rls_forced": phase7_rls_forced,
            "phase7_supplier_ledger_tenant_policy_count": phase7_policy_count,
            "phase7_active_supplier_cost_tier_index": bool(phase7_cost_index),
            "phase7_purchase_order_updated_at": bool(po_updated_at),
            "phase7_supplier_bill_match_contract": bool(bill_match_column),
            "phase7_supplier_return_credit_cost_contract": bool(return_supplier_cost),
            "phase7_append_only_runtime_grants": bool(phase7_append_only_grants),
            "phase7_bill_payment_lifecycle_grants": bool(phase7_bill_payment_lifecycle_grants),
            "phase8_expense_reversal_reference": bool(phase8_reversal_column),
            "phase8_expense_reversal_index": bool(phase8_reversal_index),
            "phase8_expense_posting_routine": bool(phase8_expense_posting_function),
            "phase8_expense_reversal_reporting_metric": bool(phase8_expense_reversal_metric),
            "phase8_expense_reversal_tenant_safe_fk": bool(phase8_reversal_fk),
            "phase8_expense_correction_status": bool(phase8_status_constraint),
            "team_chat_tables": team_chat_tables,
            "team_chat_rls_forced": team_chat_rls_forced,
            "team_chat_policy_tables": team_chat_policy_tables,
            "sales_business_date_column": bool(sales_business_date_column),
            "sales_business_date_index": bool(sales_business_date_index),
            "analytics_refresh_queue_rls_forced": bool(analytics_queue_rls_forced),
            "analytics_refresh_queue_worker": bool(analytics_queue_worker),
            "journal_entry_currency_guard": bool(journal_entry_currency_guard),
            "journal_posting_grant": bool(journal_posting_grant),
            "lexa_app_can_write_permissions_reference": bool(can_write_permissions),
            "lexa_app_can_write_schema_migrations": bool(can_write_migrations),
            "required_phase5_return_routines_found": routine_count,
            "runtime_tenant_isolation_probe": {
                "cross_tenant_read_hidden": tenant_read_isolated,
                "cross_tenant_insert_denied": tenant_write_denied,
                "fixtures_rolled_back": True,
            },
            "failures": failures,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        (args.output.with_suffix(args.output.suffix + ".sha256")).write_text(
            f"{sha256_bytes(args.output.read_bytes())}  {args.output.name}\n", encoding="utf-8"
        )
        if failures:
            for failure in failures: print("FAIL: " + failure, file=sys.stderr)
            print(f"Replay evidence written to {args.output}", file=sys.stderr)
            return 1
        print(f"PASS: {len(completed)} SQL steps applied to disposable database {dbname}.")
        print(f"PASS: RLS enabled/forced on all {rls_total} public tables; least-privilege and return/accounting routines verified.")
        print("PASS: runtime role cross-tenant read/write isolation verified; all probe fixtures rolled back.")
        print("PASS: Phase 6 inventory age-analysis index and four movement-health indexes exist and are valid.")
        print("PASS: Phase 8 expense corrections, reversal references, journal routine, and reporting schema verified.")
        print(f"Evidence: {args.output}")
        return 0
    except Exception as exc:
        print(f"ERROR: clean replay failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
