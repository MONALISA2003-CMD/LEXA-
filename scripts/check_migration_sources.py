#!/usr/bin/env python3
"""Verify live migration identities have canonical SQL or documented source loss."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
SNAPSHOT_PATH = MIGRATIONS / "live_ledger_snapshot_2026-10-21.json"
MANIFEST_PATH = MIGRATIONS / "source_gaps.json"
BANNER = "-- ACCEPTED REPLACEMENT — ORIGINAL HISTORICAL SOURCE LOST; NOT BYTE-IDENTICAL.\n"
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail on unresolved missing migration paths")
    args = parser.parse_args()
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    versions = [row["version"] for row in snapshot["migrations"]]
    if len(versions) != len(set(versions)):
        print("ERROR: duplicate full migration identities in live ledger snapshot", file=sys.stderr); return 2
    gaps = manifest.get("gaps", [])
    replacements = manifest.get("replacements", [])
    gap_map = {row["version"]: row for row in gaps}
    replacement_map = {row["version"]: row for row in replacements}
    if len(gap_map) != len(gaps) or len(replacement_map) != len(replacements):
        print("ERROR: duplicate source gap or replacement identity", file=sys.stderr); return 2
    if set(gap_map) & set(replacement_map):
        print("ERROR: a migration cannot be both a gap and accepted replacement", file=sys.stderr); return 2
    ledger = set(versions)
    if (set(gap_map) | set(replacement_map)) - ledger:
        print("ERROR: manifest references migration identities absent from the live ledger snapshot", file=sys.stderr); return 2
    missing = []
    canonical = 0
    checked = 0
    for version in versions:
        path = MIGRATIONS / f"{version}.sql"
        if version in replacement_map:
            entry = replacement_map[version]
            if entry.get("expected_path") != str(path.relative_to(ROOT)):
                print(f"ERROR: wrong replacement path for {version}", file=sys.stderr); return 2
            if not path.is_file():
                missing.append(version); continue
            raw = path.read_bytes()
            if not raw.startswith(BANNER.encode("utf-8")):
                print(f"ERROR: accepted replacement banner missing for {version}", file=sys.stderr); return 2
            if entry.get("original_source_status") != "LOST_DECLARED":
                print(f"ERROR: replacement source-loss decision missing for {version}", file=sys.stderr); return 2
            expected = entry.get("replacement_sha256")
            actual = hashlib.sha256(raw).hexdigest()
            if not expected or actual != expected:
                print(f"ERROR: replacement checksum mismatch for {version}", file=sys.stderr); return 2
            checked += 1
        elif path.is_file():
            if version in gap_map:
                print(f"ERROR: {version} is marked as a gap but a file exists; reconcile manifest", file=sys.stderr); return 2
            canonical += 1
        else:
            entry = gap_map.get(version)
            if not entry or entry.get("expected_path") != str(path.relative_to(ROOT)) or not entry.get("reason"):
                print(f"ERROR: undocumented missing migration source: {version}", file=sys.stderr); return 2
            missing.append(version)
    for prefix, listed in manifest.get("numeric_prefix_collisions", {}).items():
        actual = sorted(v for v in versions if v.split("_", 1)[0] == prefix)
        if sorted(listed) != actual:
            print(f"ERROR: numeric-prefix collision manifest drift for {prefix}: {actual}", file=sys.stderr); return 2
    print(f"Live migration identities checked: {len(versions)}; canonical sources: {canonical}; accepted replacements checksum-verified: {checked}; unresolved source paths: {len(missing)}.")
    if checked:
        print("Historical SQL bytes for accepted replacements are declared lost; replacements are not represented as byte-identical originals.")
    if missing:
        print("UNRESOLVED MIGRATION SOURCE PATHS: " + ", ".join(missing))
        if args.strict:
            print("Strict migration-source gate: BLOCKED."); return 1
    print("Migration source availability gate: PASS. Clean replay and live-schema parity remain separate release gates.")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
