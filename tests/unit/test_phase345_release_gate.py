from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "generate_phase345_release_gate.py"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
RESULTS = {
    "BACKEND_RESULT": "success",
    "FRONTEND_RESULT": "success",
    "DATABASE_REPLAY_RESULT": "success",
    "SALES_ACCOUNTING_E2E_RESULT": "success",
    "PURCHASING_E2E_RESULT": "success",
}


def _run(output: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"LEXA_SOURCE_SHA": COMMIT, **RESULTS, **overrides})
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )


def test_phase345_release_gate_accepts_only_all_green_exact_sha(tmp_path: Path):
    output = tmp_path / "phase345-release-acceptance.json"
    result = _run(output)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(output.read_text())
    assert evidence["status"] == "ACCEPTED_FOR_RELEASE_REVIEW"
    assert evidence["source_commit_sha"] == COMMIT
    assert evidence["acceptance_scope"] == "staging_candidate_only"
    assert evidence["production_deployment_authorized"] is False
    assert evidence["production_database_mutation_performed"] is False
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert output.with_suffix(output.suffix + ".sha256").read_text().startswith(digest)


def test_phase345_release_gate_fails_closed_on_skipped_or_wrong_source(tmp_path: Path):
    output = tmp_path / "blocked.json"
    result = _run(output, PURCHASING_E2E_RESULT="skipped", LEXA_SOURCE_SHA="not-a-commit")
    assert result.returncode == 1
    evidence = json.loads(output.read_text())
    assert evidence["status"] == "BLOCKED"
    assert evidence["source_commit_sha"] is None
    assert any("purchasing_lifecycle_e2e" in error for error in evidence["errors"])
    assert any("immutable 40-character" in error for error in evidence["errors"])
