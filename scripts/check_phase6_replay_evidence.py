#!/usr/bin/env python3
"""Reject Stage 5 replay evidence from a stale commit or changed migration source bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from run_clean_migration_replay import canonical_inputs, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-commit", default=os.environ.get("GITHUB_SHA", ""))
    args = parser.parse_args()
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        expected_inputs, expected_bundle = canonical_inputs()
    except Exception as exc:
        print(f"ERROR: replay evidence/input unavailable: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    if evidence.get("status") != "PASS":
        errors.append("replay evidence status is not PASS")
    if evidence.get("historical_recovery_gate") != "CLOSED_BY_PERMANENT_DISPOSITION":
        errors.append("historical source disposition status does not match policy")
    if evidence.get("historical_byte_parity_asserted") is not False:
        errors.append("evidence must not claim historical byte parity")
    database_name = str(evidence.get("target_database") or "").lower()
    if not any(token in database_name for token in ("replay", "test", "ci")) or database_name in {"neondb", "postgres", "production", "prod", "lexa"}:
        errors.append("evidence target is not an explicitly named disposable replay/test/CI database")
    rls = evidence.get("rls") or {}
    if not rls.get("public_tables") or rls.get("enabled") != rls.get("public_tables") or rls.get("forced") != rls.get("public_tables") or rls.get("gaps") != 0:
        errors.append("evidence does not show enabled and forced RLS on every public table")
    tenant_probe = evidence.get("runtime_tenant_isolation_probe") or {}
    if tenant_probe.get("cross_tenant_read_hidden") is not True or tenant_probe.get("cross_tenant_insert_denied") is not True or tenant_probe.get("fixtures_rolled_back") is not True:
        errors.append("evidence lacks a successful rollback-only runtime cross-tenant read/write isolation probe")
    if evidence.get("phase6_replenishment_table_exists") is not True or evidence.get("phase6_replenishment_rls_forced") is not True or evidence.get("phase6_replenishment_tenant_policy_count") != 1:
        errors.append("evidence lacks the Phase 6 table/forced-RLS/tenant-policy contract")
    if evidence.get("lexa_app_can_write_permissions_reference") is not False or evidence.get("lexa_app_can_write_schema_migrations") is not False:
        errors.append("evidence does not prove least-privilege protection for permission and migration reference data")
    if evidence.get("phase6_inventory_age_index_count") != 1:
        errors.append("evidence lacks the Phase 6 inventory age-analysis index")
    if evidence.get("phase6_inventory_health_index_count") != 4:
        errors.append("evidence lacks all four valid Phase 6 stock-movement health indexes")
    if evidence.get("phase7_supplier_ledger_tables") != 6 or evidence.get("phase7_supplier_ledger_rls_forced") != 6 or evidence.get("phase7_supplier_ledger_tenant_policy_count") != 6:
        errors.append("evidence lacks all six Phase 7 supplier/landed-cost tables with forced tenant RLS and policies")
    if evidence.get("phase7_active_supplier_cost_tier_index") is not True:
        errors.append("evidence lacks the Phase 7 active supplier cost tier uniqueness index")
    if evidence.get("phase7_purchase_order_updated_at") is not True or evidence.get("phase7_supplier_bill_match_contract") is not True or evidence.get("phase7_supplier_return_credit_cost_contract") is not True:
        errors.append("evidence lacks Phase 7 PO, invoice-match or supplier-return cost correctness contracts")
    if evidence.get("phase7_append_only_runtime_grants") is not True or evidence.get("phase7_bill_payment_lifecycle_grants") is not True:
        errors.append("evidence lacks Phase 7 append-only ledger/allocation and least-privilege bill/payment lifecycle grant assertions")
    if evidence.get("phase8_expense_reversal_reference") is not True:
        errors.append("evidence lacks the Phase 8 expense correction reference column")
    if evidence.get("phase8_expense_reversal_index") is not True:
        errors.append("evidence lacks the Phase 8 expense correction lookup index")
    if evidence.get("phase8_expense_posting_routine") is not True:
        errors.append("evidence lacks the Phase 8 expense journal posting routine")
    if evidence.get("phase8_expense_reversal_reporting_metric") is not True:
        errors.append("evidence lacks the Phase 8 expense correction reporting metric")
    if evidence.get("phase8_expense_reversal_tenant_safe_fk") is not True:
        errors.append("evidence lacks the tenant-safe Phase 8 expense correction journal reference")
    if evidence.get("phase8_expense_correction_status") is not True:
        errors.append("evidence lacks the Phase 8 expense correction lifecycle status")
    if evidence.get("required_phase5_return_routines_found") != 4:
        errors.append("evidence is missing one or more required Phase 5 return/accounting routines")
    if evidence.get("migration_bundle_sha256") != expected_bundle:
        errors.append("migration bundle SHA-256 differs from current source files")
    recorded = evidence.get("migration_inputs")
    if recorded != expected_inputs:
        errors.append("migration input path/hash manifest differs from current checkout")
    if evidence.get("completed_sql_steps") != [item["path"] for item in expected_inputs]:
        errors.append("completed SQL replay steps do not match the exact reviewed source sequence")
    if args.expected_commit and evidence.get("source_commit") != args.expected_commit:
        errors.append("replay evidence commit does not match the expected checkout SHA")
    if not args.expected_commit and evidence.get("source_commit") in (None, "", "LOCAL_UNPINNED"):
        errors.append("replay evidence is not tied to an immutable source commit")
    sidecar = args.evidence.with_suffix(args.evidence.suffix + ".sha256")
    if not sidecar.is_file():
        errors.append("replay evidence checksum sidecar is missing")
    else:
        expected_sha = sidecar.read_text(encoding="utf-8").split()[0]
        if sha256_bytes(args.evidence.read_bytes()) != expected_sha:
            errors.append("replay evidence checksum sidecar mismatch")
    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        return 1
    print("PASS: clean-replay evidence through Phase 8 is tied to the current migration bundle and expected source SHA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
