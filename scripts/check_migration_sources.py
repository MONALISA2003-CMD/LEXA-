#!/usr/bin/env python3
"""Check that every observed live migration is sourced or an explicit tracked gap.

This is a local source-integrity check; it does not connect to Neon. The JSON
ledger is a dated read-only snapshot. Pass --strict to fail while gaps remain.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
SNAPSHOT_PATH = MIGRATIONS / "live_ledger_snapshot_2026-10-15.json"
GAPS_PATH = MIGRATIONS / "source_gaps.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return failure if any applied live migration source remains missing",
    )
    args = parser.parse_args()

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    gap_manifest = json.loads(GAPS_PATH.read_text(encoding="utf-8"))
    ledger_versions = [row["version"] for row in snapshot["migrations"]]
    if len(ledger_versions) != len(set(ledger_versions)):
        print("ERROR: duplicate full migration version strings in the snapshot", file=sys.stderr)
        return 2

    gap_rows = gap_manifest["gaps"]
    gap_by_version = {row["version"]: row for row in gap_rows}
    if len(gap_by_version) != len(gap_rows):
        print("ERROR: source_gaps.json contains duplicate versions", file=sys.stderr)
        return 2

    ledger_set = set(ledger_versions)
    unknown_gaps = sorted(set(gap_by_version) - ledger_set)
    if unknown_gaps:
        print("ERROR: source gaps not present in observed ledger: " + ", ".join(unknown_gaps), file=sys.stderr)
        return 2

    missing: list[str] = []
    for version in ledger_versions:
        source_path = MIGRATIONS / f"{version}.sql"
        if source_path.is_file():
            if version in gap_by_version:
                print(f"ERROR: {version} is still marked as a gap but source now exists: {source_path}", file=sys.stderr)
                return 2
            continue
        entry = gap_by_version.get(version)
        if not entry:
            print(f"ERROR: missing source is not documented: {version} -> {source_path.relative_to(ROOT)}", file=sys.stderr)
            return 2
        if entry.get("expected_path") != str(source_path.relative_to(ROOT)) or not entry.get("reason") or not entry.get("next_step"):
            print(f"ERROR: incomplete/wrong gap documentation for {version}", file=sys.stderr)
            return 2
        missing.append(version)

    for prefix, versions in gap_manifest.get("numeric_prefix_collisions", {}).items():
        actual = sorted(v for v in ledger_versions if v.split("_", 1)[0] == prefix)
        if sorted(versions) != actual:
            print(f"ERROR: numeric prefix collision manifest drift for {prefix}: expected {actual}, got {versions}", file=sys.stderr)
            return 2

    print(f"Observed ledger snapshot: {snapshot['snapshot_date']} ({len(ledger_versions)} migration rows).")
    if missing:
        print(f"SOURCE GAPS ({len(missing)}):")
        for version in missing:
            print(f"  - {version}: {gap_by_version[version]['expected_path']}")
        print("Strict replay is BLOCKED until the exact historical SQL sources are recovered.")
        return 1 if args.strict else 0

    print("All observed ledger versions have matching SQL source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
