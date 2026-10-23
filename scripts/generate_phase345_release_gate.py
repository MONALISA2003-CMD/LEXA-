#!/usr/bin/env python3
"""Generate fail-closed, exact-source-SHA candidate acceptance evidence.

This is staging acceptance only. It deliberately does not authorize production
DB migration, deployment promotion, alias changes, or external integrations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_RESULTS = {
    "backend_contracts": "BACKEND_RESULT",
    "frontend_build_typecheck": "FRONTEND_RESULT",
    "disposable_postgres_replay": "DATABASE_REPLAY_RESULT",
    "sales_inventory_accounting_e2e": "SALES_ACCOUNTING_E2E_RESULT",
    "purchasing_lifecycle_e2e": "PURCHASING_E2E_RESULT",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_sha = os.environ.get("LEXA_SOURCE_SHA", "").strip().lower()
    results = {
        name: os.environ.get(env_name, "missing").strip().lower() or "missing"
        for name, env_name in REQUIRED_RESULTS.items()
    }
    errors: list[str] = []
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        errors.append("LEXA_SOURCE_SHA must be an immutable 40-character Git commit SHA")
    for name, result in results.items():
        if result != "success":
            errors.append(f"{name} result must be success, got {result}")

    accepted = not errors
    evidence = {
        "schema_version": 1,
        "candidate_type": "phase3-5-connected-operations",
        "acceptance_scope": "staging_candidate_only",
        "source_commit_sha": source_sha if re.fullmatch(r"[0-9a-f]{40}", source_sha) else None,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ACCEPTED_FOR_RELEASE_REVIEW" if accepted else "BLOCKED",
        "checks": results,
        "production_deployment_authorized": False,
        "production_database_mutation_performed": False,
        "production_alias_changed": False,
        "errors": errors,
    }
    payload = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        f"{digest}  {args.output.name}\n", encoding="ascii"
    )

    print(json.dumps({"status": evidence["status"], "source_commit_sha": evidence["source_commit_sha"], "checks": results, "errors": errors}, indent=2))
    if not accepted:
        print("BLOCKED: release acceptance requires every build, replay and staging E2E gate to pass.", file=sys.stderr)
        return 1
    print(f"PASS: exact-SHA staging acceptance recorded; evidence sha256={digest}")
    print("PRODUCTION NOTE: this artifact is not approval to apply migrations or promote a production deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
