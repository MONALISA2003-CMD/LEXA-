import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "010_phase2_catalog_intelligence", "011_phase2_catalog_runtime_constraints",
    "023_phase4_purchasing_core", "024_phase4_purchasing_security",
    "025_phase4_purchasing_permissions", "026_phase4_membership_branch_integrity",
}

def test_accepted_replacements_are_checksum_pinned_and_historical_loss_is_explicit():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/check_migration_recovery_manifest.py")], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ACCEPTED REPLACEMENTS VERIFIED: 6" in result.stdout
    assert "UNRESOLVED SOURCE PATH GAPS: 0" in result.stdout
    assert "declared lost" in result.stdout
    manifest = json.loads((ROOT / "migrations/source_gaps.json").read_text())
    replacements = {row["version"]: row for row in manifest["replacements"]}
    assert set(replacements) == EXPECTED
    assert manifest["gaps"] == []
    for version, row in replacements.items():
        path = ROOT / row["expected_path"]
        assert path.is_file(), version
        assert path.read_text().startswith("-- ACCEPTED REPLACEMENT — ORIGINAL HISTORICAL SOURCE LOST; NOT BYTE-IDENTICAL.")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["replacement_sha256"]

def test_full_migration_identity_handles_023_prefix_collision():
    root_migration = ROOT / "migrations/023_phase2_identity_tenancy_authorization_foundation.sql"
    purchasing_migration = ROOT / "migrations/023_phase4_purchasing_core.sql"
    assert root_migration.is_file()
    assert purchasing_migration.is_file()
    snapshot = json.loads((ROOT / "migrations/live_ledger_snapshot_2026-10-15.json").read_text())
    versions = {row["version"] for row in snapshot["migrations"]}
    assert "023_phase2_identity_tenancy_authorization_foundation" in versions
    assert "023_phase4_purchasing_core" in versions
