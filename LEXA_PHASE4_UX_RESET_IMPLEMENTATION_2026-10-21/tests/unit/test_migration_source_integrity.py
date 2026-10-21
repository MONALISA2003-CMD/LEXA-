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


def test_every_known_live_migration_source_gap_is_explicit_and_actionable():
    snapshot = json.loads((MIGRATIONS / "live_ledger_snapshot_2026-10-15.json").read_text())
    gaps = json.loads((MIGRATIONS / "source_gaps.json").read_text())
    ledger_versions = {row["version"] for row in snapshot["migrations"]}
    gap_versions = {row["version"] for row in gaps["gaps"]}
    assert gap_versions == {
        "010_phase2_catalog_intelligence",
        "011_phase2_catalog_runtime_constraints",
        "023_phase4_purchasing_core",
        "024_phase4_purchasing_security",
        "025_phase4_purchasing_permissions",
        "026_phase4_membership_branch_integrity",
    }
    assert gap_versions <= ledger_versions
    for gap in gaps["gaps"]:
        assert gap["expected_path"] == f"migrations/{gap['version']}.sql"
        assert gap["reason"].strip()
        assert gap["next_step"].strip()
        assert not (ROOT / gap["expected_path"]).exists()
    assert (MIGRATIONS / "019_phase4a_customer_credit_allocation.sql").is_file()
    restored_027 = MIGRATIONS / "027_release_convergence.sql"
    assert restored_027.is_file()
    assert "INSERT INTO schema_migrations(version) VALUES('027_release_convergence')" in restored_027.read_text()
    raw = restored_027.read_bytes()
    import hashlib
    git_blob_sha1 = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert git_blob_sha1 == "e6d9242d7dedb2cbf7b1a71a46fe635b3ab051d8"


def test_migration_source_checker_reports_known_gaps_but_strict_mode_blocks_replay():
    normal = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_migration_sources.py")],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert normal.returncode == 0, normal.stdout + normal.stderr
    assert "Strict replay is BLOCKED" in normal.stdout
    strict = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_migration_sources.py"), "--strict"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert strict.returncode == 1
    assert "SOURCE GAPS (6)" in strict.stdout


def test_deployment_docs_distinguish_liveness_from_readiness():
    guide = (ROOT / "docs/DEPLOYMENT_RENDER_VERCEL.md").read_text()
    render = (ROOT / "render.yaml").read_text()
    assert "healthCheckPath: /ready" in render
    assert "`/ready`" in guide
    assert "`/health` is process liveness only" in guide
    assert "name: LEXA" in render
