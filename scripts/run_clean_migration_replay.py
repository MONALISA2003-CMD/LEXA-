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
                       '037_phase6_inventory_ageing_index','038_phase6_movement_health_indexes')
                """)
                migration_rows = sorted(row[0] for row in cur.fetchall())
                expected_migrations = sorted([
                    '029_phase3_runtime_privilege_surface','029_phase1_runtime_role_least_privilege',
                    '030_phase3_workspace_memberships','031_phase3_auth_surface_rls',
                    '033_phase5_refund_settlement_consistency','034_phase5_return_accounting_journals',
                    '035_phase5_none_return_receivable_guard','036_phase6_inventory_intelligence',
                    '037_phase6_inventory_ageing_index','038_phase6_movement_health_indexes',
                ])
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
        print(f"Evidence: {args.output}")
        return 0
    except Exception as exc:
        print(f"ERROR: clean replay failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
