from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "replace_missing_migrations.py"
SPEC = importlib.util.spec_from_file_location("replace_missing_migrations", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def fixture(tmp_path: Path):
    source_root = tmp_path / "repo"
    source = source_root / "migrations/reconstructed/010_phase2_catalog_intelligence.equivalent.sql"
    source.parent.mkdir(parents=True)
    data = b"-- RECONSTRUCTED EQUIVALENT - NOT HISTORICAL\nBEGIN;\nCREATE TABLE test_rows(id uuid PRIMARY KEY);\nCOMMIT;\n"
    source.write_bytes(data)
    mapping = {"010_phase2_catalog_intelligence": {"source": "migrations/reconstructed/010_phase2_catalog_intelligence.equivalent.sql", "git_blob_sha1": git_blob_sha(data)}}
    return source_root, source, data, mapping


def test_dry_run_does_not_write_and_marks_historical_source_unrecovered(tmp_path: Path):
    root, source, _, mapping = fixture(tmp_path)
    result = mod.build(root, apply=False, expected=mapping)
    target = root / "migrations/010_phase2_catalog_intelligence.sql"
    assert not target.exists()
    assert result["status"] == "REPLACEMENTS_ONLY_NOT_HISTORICAL_SOURCE_RECOVERY"
    assert result["historical_source_gate"] == "BLOCKED_FOR_EXACT_BYTE_PARITY"
    assert result["replacements"][0]["action"] == "would-create-replacement"


def test_apply_writes_labelled_replacement_and_manifest(tmp_path: Path):
    root, _, _, mapping = fixture(tmp_path)
    result = mod.build(root, apply=True, expected=mapping)
    target = root / "migrations/010_phase2_catalog_intelligence.sql"
    content = target.read_text()
    assert content.startswith("-- EXPLICIT HISTORICAL SOURCE REPLACEMENT")
    assert "NOT THE ORIGINAL APPLIED SQL BYTES" in content
    assert "BEGIN;" in content and "COMMIT;" in content
    manifest = json.loads((root / "migrations/source_replacements_2026-10-20.json").read_text())
    assert manifest["replacements"][0]["historical_bytes_recovered"] is False
    assert manifest["replacements"][0]["replacement_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert result["files_written"] == 2


def test_apply_is_idempotent_for_identical_generated_replacement(tmp_path: Path):
    root, _, _, mapping = fixture(tmp_path)
    mod.build(root, apply=True, expected=mapping)
    result = mod.build(root, apply=True, expected=mapping)
    assert result["replacements"][0]["action"] == "already-present-identical-replacement"
    assert result["files_written"] == 1  # manifest refresh only


def test_refuses_to_overwrite_nonreplacement_migration(tmp_path: Path):
    root, _, _, mapping = fixture(tmp_path)
    target = root / "migrations/010_phase2_catalog_intelligence.sql"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("-- unknown content, must preserve\n")
    with pytest.raises(RuntimeError, match="Refusing to overwrite existing migration"):
        mod.build(root, apply=True, expected=mapping)


def test_refuses_source_without_reconstruction_header(tmp_path: Path):
    root, source, _, mapping = fixture(tmp_path)
    source.write_text("BEGIN; SELECT 1; COMMIT;\n")
    mapping["010_phase2_catalog_intelligence"]["git_blob_sha1"] = git_blob_sha(source.read_bytes())
    with pytest.raises(RuntimeError, match="mandatory reconstruction label"):
        mod.build(root, apply=True, expected=mapping)


def test_full_repo_apply_updates_gap_metadata_and_preserves_historical_checker(tmp_path: Path):
    root, _, data, mapping = fixture(tmp_path)
    (root / "migrations/live_ledger_snapshot_2026-10-15.json").write_text(json.dumps({"snapshot_date":"2026-10-15","migrations":[{"version":"010_phase2_catalog_intelligence"}]}))
    (root / "migrations/source_gaps.json").write_text(json.dumps({
        "schema_version":1,
        "purpose":"Track the exact applied live migration SQL sources that remain unavailable.",
        "status":"BLOCKS_REPRODUCIBLE_FROM_ZERO_MIGRATION_REPLAY",
        "gaps":[{"version":"010_phase2_catalog_intelligence","expected_path":"migrations/010_phase2_catalog_intelligence.sql","reason":"Historical bytes absent","next_step":"Recover exact SQL"}],
        "numeric_prefix_collisions":{},
        "recovered_sources":[]
    }))
    checker = root / "scripts/check_migration_sources.py"
    checker.parent.mkdir(parents=True, exist_ok=True)
    checker.write_text('"""Check that every observed live migration SQL source remains available.\nTrack the exact applied live migration SQL sources\nsource now exists\n"""\n')
    mod.build(root, apply=True, expected=mapping)
    gaps = json.loads((root / "migrations/source_gaps.json").read_text())
    assert gaps["gaps"] == []
    assert gaps["status"] == "REPLACEMENTS_PRESENT_HISTORICAL_BYTE_PARITY_UNRESOLVED"
    assert len(gaps["replacements"]) == 1
    assert (root / ".migration-source-audit/check_migration_sources.py.original").is_file()
    assert "check_migration_sources_replacement_aware" in checker.read_text()
    assert (root / "scripts/check_migration_sources_replacement_aware.py").is_file()


def test_replacement_aware_checker_keeps_default_strict_gate_blocked(tmp_path: Path):
    root, _, _, mapping = fixture(tmp_path)
    (root / "migrations/live_ledger_snapshot_2026-10-15.json").write_text(json.dumps({"snapshot_date":"2026-10-15","migrations":[{"version":"010_phase2_catalog_intelligence"}]}))
    (root / "migrations/source_gaps.json").write_text(json.dumps({
        "schema_version":1, "purpose":"Track the exact applied live migration SQL sources.",
        "status":"BLOCKS_REPRODUCIBLE_FROM_ZERO_MIGRATION_REPLAY",
        "gaps":[{"version":"010_phase2_catalog_intelligence","expected_path":"migrations/010_phase2_catalog_intelligence.sql","reason":"Historical bytes absent","next_step":"Recover exact SQL"}],
        "numeric_prefix_collisions":{}, "recovered_sources":[]
    }))
    checker = root / "scripts/check_migration_sources.py"
    checker.parent.mkdir(parents=True, exist_ok=True)
    checker.write_text('"""Check that every observed live migration SQL source remains available.\nTrack the exact applied live migration SQL sources\nsource now exists\n"""\n')
    mod.build(root, apply=True, expected=mapping)
    strict = subprocess.run([sys.executable, str(checker), "--strict"], cwd=root, capture_output=True, text=True)
    allowed = subprocess.run([sys.executable, str(checker), "--strict", "--allow-replacements"], cwd=root, capture_output=True, text=True)
    assert strict.returncode == 1
    assert "HISTORICAL BYTE PROVENANCE STILL UNRESOLVED" in strict.stdout
    assert allowed.returncode == 0
    assert "replacements remain explicitly non-historical" in allowed.stdout


def test_ci_candidate_uses_node24_redis_and_strict_provenance_gate():
    workflow = (ROOT / "release-controls/lexa-ci.yml").read_text()
    assert 'node-version: "24.x"' in workflow
    assert 'image: redis:7-alpine' in workflow
    assert 'python -m pytest -q tests apps/api/tests' in workflow
    assert 'npm run typecheck' in workflow and 'npm run build' in workflow
    assert 'python scripts/check_migration_sources.py --strict' in workflow
    assert '--allow-replacements' in workflow
