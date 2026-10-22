from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
MIGRATIONS = ROOT / "migrations"


def test_brain_migration_policy_sql_uses_safe_empty_tenant_context_and_quoted_identifiers():
    sql = (MIGRATIONS / "022_phase6a_brain_foundation.sql").read_text()
    assert "policy_name := t || '_tenant_isolation'" in sql
    assert "format('DROP POLICY IF EXISTS %I ON %I', policy_name, t)" in sql
    assert "current_setting(%L, true), %L)::uuid" in sql
    assert "      'app.tenant_id'," in sql
    assert "      ''," in sql
    assert "NULLIF(current_setting(''app.tenant_id'', true), )::uuid" not in sql
    assert "%I_tenant_isolation" not in sql


def test_six_phase3_sources_are_permanently_dispositioned_not_reopened():
    snapshot = json.loads((MIGRATIONS / "live_ledger_snapshot_2026-10-21.json").read_text())
    gaps = json.loads((MIGRATIONS / "source_gaps.json").read_text())
    dispositions = json.loads((MIGRATIONS / "migration_dispositions.json").read_text())
    ledger_versions = {row["version"] for row in snapshot["migrations"]}
    gap_versions = {row["version"] for row in gaps["gaps"]}
    expected = {
        "010_phase2_catalog_intelligence", "011_phase2_catalog_runtime_constraints",
        "023_phase4_purchasing_core", "024_phase4_purchasing_security",
        "025_phase4_purchasing_permissions", "026_phase4_membership_branch_integrity",
    }
    assert gap_versions == expected
    assert gap_versions <= ledger_versions
    disposition_map = {row["version"]: row for row in dispositions["permanently_replaced_sources"]}
    assert set(disposition_map) == expected
    for row in gaps["gaps"]:
        item = disposition_map[row["version"]]
        assert row["disposition"] == item["disposition"] == "PERMANENTLY_REPLACED"
        assert row["recovery_status"] == "CLOSED_NO_FURTHER_SEARCH"
        assert row["historical_bytes_recovered"] is False
        assert row["replacement_path"] == item["replacement_path"]
        assert (ROOT / row["replacement_path"]).is_file()
        assert not (ROOT / row["expected_path"]).exists()
    assert "032_phase5_return_settlement_reconciliation" not in ledger_versions
    assert dispositions["known_nonproduction_qa_only_migration_entry"]["status"] == "QA_BRANCH_ONLY_NOT_IN_CANONICAL_PRODUCTION_LEDGER"


def test_latest_observed_live_migration_sources_are_present_and_collision_is_explicit():
    snapshot = json.loads((MIGRATIONS / "live_ledger_snapshot_2026-10-21.json").read_text())
    gaps = json.loads((MIGRATIONS / "source_gaps.json").read_text())
    versions = {row["version"] for row in snapshot["migrations"]}
    assert "029_phase3_runtime_privilege_surface" in versions
    assert "031_phase3_auth_surface_rls" in versions
    assert (MIGRATIONS / "029_phase3_runtime_privilege_surface.sql").is_file()
    assert (MIGRATIONS / "031_phase3_auth_surface_rls.sql").is_file()
    assert sorted(gaps["numeric_prefix_collisions"]["029"]) == sorted(v for v in versions if v.startswith("029_"))
    assert sorted(gaps["numeric_prefix_collisions"]["023"]) == sorted(v for v in versions if v.startswith("023_"))
    assert (MIGRATIONS / "019_phase4a_customer_credit_allocation.sql").is_file()
    assert (MIGRATIONS / "027_release_convergence.sql").is_file()


def test_migration_source_checker_closes_historical_gate_but_keeps_semantic_gate_separate():
    normal = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_migration_sources.py"), "--strict"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert normal.returncode == 0, normal.stdout + normal.stderr
    assert "HISTORICAL RECOVERY GATE: CLOSED BY APPROVED PERMANENT DISPOSITION" in normal.stdout
    assert "PERMANENTLY REPLACED SOURCE HISTORIES: 6" in normal.stdout
    semantic = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_migration_sources.py"), "--strict", "--require-semantic-validation"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert semantic.returncode == 1
    assert "semantic validation" in (semantic.stdout + semantic.stderr).lower()


def test_phase6_clean_replay_manifest_and_new_migration_are_additive_and_tenant_scoped():
    migration = (MIGRATIONS / "036_phase6_inventory_intelligence.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS public.inventory_replenishment_policies" in migration
    assert "FOREIGN KEY (tenant_id, location_id)" in migration
    assert "FOREIGN KEY (tenant_id, variant_id)" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "CREATE POLICY inventory_replenishment_policies_tenant_isolation" in migration
    assert "INSERT INTO public.schema_migrations(version)" in migration

def test_deployment_docs_distinguish_liveness_from_readiness():
    guide = (ROOT / "docs/DEPLOYMENT_RENDER_VERCEL.md").read_text()
    render = (ROOT / "render.yaml").read_text()
    assert "healthCheckPath: /health" in render
    assert "`/ready`" in guide
    assert "`/health` is process liveness only" in guide
    assert "name: LEXA" in render


def test_clean_replay_plan_hashes_all_inputs_without_touching_database():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_clean_migration_replay.py"), "--plan-only"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PLAN PASS: 44 migration inputs are present and hashed." in result.stdout
    assert "No database connection opened; no SQL executed." in result.stdout


def test_clean_replay_apply_requires_explicit_opt_in_and_never_accepts_remote_host():
    import os
    import subprocess
    env = os.environ.copy()
    env["LEXA_ALLOW_DISPOSABLE_REPLAY"] = "1"
    env["DATABASE_URL"] = "postgresql://u:p@ep.example.neon.tech/neondb"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_clean_migration_replay.py"), "--apply"],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert "DATABASE_URL host must be loopback" in result.stderr


def test_evidence_checker_rejects_missing_or_stale_evidence():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_phase6_replay_evidence.py"), "--evidence", str(ROOT / "artifacts/not-created.json"), "--expected-commit", "deadbeef"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert "replay evidence/input unavailable" in result.stderr



def test_clean_replay_plan_rejects_stale_declared_git_blob_hashes(tmp_path):
    import importlib.util
    import pytest

    script = ROOT / "scripts/run_clean_migration_replay.py"
    spec = importlib.util.spec_from_file_location("phase6_replay_test_module", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest_path = tmp_path / "clean_replay_order.json"
    manifest_path.write_text(json.dumps({"steps": [{
        "path": "migrations/001_phase1_foundation.sql",
        "mode": "original-source",
        "git_blob_sha1": "0" * 40,
    }]}), encoding="utf-8")
    module.ORDER_PATH = manifest_path
    with pytest.raises(ValueError, match="declared Git blob SHA-1 mismatch"):
        module.canonical_inputs()
