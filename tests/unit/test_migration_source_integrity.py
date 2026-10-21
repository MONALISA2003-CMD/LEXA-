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


def test_every_known_live_migration_source_gap_is_replaced_by_a_labelled_checksum_pinned_source():
    import hashlib
    snapshot = json.loads((MIGRATIONS / "live_ledger_snapshot_2026-10-15.json").read_text())
    manifest = json.loads((MIGRATIONS / "source_gaps.json").read_text())
    ledger_versions = {row["version"] for row in snapshot["migrations"]}
    expected = {
        "010_phase2_catalog_intelligence", "011_phase2_catalog_runtime_constraints",
        "023_phase4_purchasing_core", "024_phase4_purchasing_security",
        "025_phase4_purchasing_permissions", "026_phase4_membership_branch_integrity",
    }
    replacements = {row["version"]: row for row in manifest["replacements"]}
    assert set(replacements) == expected
    assert set(manifest["gaps"]) == set()
    assert expected <= ledger_versions
    assert manifest["decision"]["decision"]
    for version, row in replacements.items():
        path = ROOT / row["expected_path"]
        raw = path.read_bytes()
        assert row["original_source_status"] == "LOST_DECLARED"
        assert raw.startswith("-- ACCEPTED REPLACEMENT — ORIGINAL HISTORICAL SOURCE LOST; NOT BYTE-IDENTICAL.".encode("utf-8"))
        assert hashlib.sha256(raw).hexdigest() == row["replacement_sha256"]
        assert "NOT BYTE-IDENTICAL" in raw.decode("utf-8").splitlines()[0]
    assert (MIGRATIONS / "023_phase2_identity_tenancy_authorization_foundation.sql").is_file()
    restored_027 = MIGRATIONS / "027_release_convergence.sql"
    assert restored_027.is_file()
    assert "INSERT INTO schema_migrations(version) VALUES('027_release_convergence')" in restored_027.read_text()


def test_migration_source_checker_accepts_declared_replacements_but_records_historical_loss():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/check_migration_sources.py"), "--strict"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "accepted replacements checksum-verified: 6" in result.stdout
    assert "declared lost" in result.stdout
    assert "availability gate: PASS" in result.stdout


def test_deployment_docs_distinguish_liveness_from_readiness():
    guide = (ROOT / "docs/DEPLOYMENT_RENDER_VERCEL.md").read_text()
    render = (ROOT / "render.yaml").read_text()
    assert "healthCheckPath: /ready" in render
    assert "`/ready`" in guide
    assert "`/health` is process liveness only" in guide
    assert "name: LEXA" in render
