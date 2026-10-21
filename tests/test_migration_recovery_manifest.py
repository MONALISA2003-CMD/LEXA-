import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_migration_recovery_manifest.py"


def test_reconstructed_manifest_is_hash_checked_and_kept_separate():
    result = subprocess.run([sys.executable, str(CHECKER)], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HISTORICAL BYTE SOURCES UNRECOVERED BY APPROVED DECISION: 6" in result.stdout
    assert "PERMANENT REPLACEMENT DISPOSITION: PASS" in result.stdout


def test_forensic_exact_byte_check_is_not_the_active_release_gate():
    result = subprocess.run([sys.executable, str(CHECKER), "--strict-exact"], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 1
    assert "STRICT EXACT-BYTE PARITY: NOT POSSIBLE BY APPROVED DISPOSITION" in result.stderr


def test_missing_source_names_do_not_exist_at_historical_paths():
    gaps = [
        "010_phase2_catalog_intelligence", "011_phase2_catalog_runtime_constraints",
        "023_phase4_purchasing_core", "024_phase4_purchasing_security",
        "025_phase4_purchasing_permissions", "026_phase4_membership_branch_integrity",
    ]
    for version in gaps:
        assert not (ROOT / "migrations" / f"{version}.sql").exists()
