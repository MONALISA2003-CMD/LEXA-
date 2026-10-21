#!/usr/bin/env python3
"""Generate an immutable per-commit CI gate summary without implying production acceptance."""
from __future__ import annotations
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase6-ci-gate-evidence.json"))
    args = parser.parse_args()
    commit = os.environ.get("GITHUB_SHA", "").strip()
    if not commit:
        print("ERROR: GITHUB_SHA is required to pin CI evidence to a source commit", file=sys.stderr)
        return 2
    statuses = {
        "backend_contracts": os.environ.get("BACKEND_RESULT", "unknown"),
        "frontend_contracts_node24": os.environ.get("FRONTEND_RESULT", "unknown"),
        "clean_database_replay": os.environ.get("REPLAY_RESULT", "unknown"),
    }
    required = {key: value == "success" for key, value in statuses.items()}
    pass_ci = all(required.values())
    evidence = {
        "schema_version": 1,
        "project": "LEXA",
        "phase": 6,
        "increment": "6.1-inventory-intelligence",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "ci_gate_status": "PASS_CI_CANDIDATE_GATES" if pass_ci else "FAIL_OR_INCOMPLETE",
        "production_release_accepted": False,
        "historical_source_recovery_gate": "CLOSED_BY_PHASE3_PERMANENT_DISPOSITION",
        "historical_byte_parity_claimed": False,
        "candidate_semantic_replay_status": statuses["clean_database_replay"].upper(),
        "jobs": statuses,
        "required_jobs_all_success": pass_ci,
        "not_covered_by_this_ci_summary": [
            "authenticated E2E against sanitized isolated staging",
            "same-SHA Render/Vercel deployment and readiness verification",
            "approved production database migration rollout and rollback evidence",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {args.output.name}\n", encoding="utf-8")
    print(f"CI gate evidence: {evidence['ci_gate_status']}")
    print(f"Source SHA: {commit}")
    print(f"SHA-256: {digest}")
    if not pass_ci:
        print("ERROR: one or more required CI jobs did not succeed; this candidate cannot pass the CI gate", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
