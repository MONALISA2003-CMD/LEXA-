#!/usr/bin/env python3
"""Check migration coverage while keeping original-byte provenance separate from replacements."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
SNAPSHOT_PATH = MIGRATIONS / "live_ledger_snapshot_2026-10-15.json"
GAPS_PATH = MIGRATIONS / "source_gaps.json"
REPLACEMENTS_PATH = MIGRATIONS / "source_replacements_2026-10-20.json"
BANNER = "-- EXPLICIT HISTORICAL SOURCE REPLACEMENT — NOT THE ORIGINAL APPLIED SQL BYTES."


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail if any historical source gap or replacement remains")
    parser.add_argument("--allow-replacements", action="store_true", help="allow hash-verified labelled replacements for disposable replay only")
    args = parser.parse_args(argv)
    for path in (SNAPSHOT_PATH, GAPS_PATH):
        if not path.is_file():
            print(f"ERROR: required migration source metadata is missing: {path.relative_to(ROOT)}", file=sys.stderr)
            return 2
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    gaps_doc = json.loads(GAPS_PATH.read_text(encoding="utf-8"))
    replacements_doc = json.loads(REPLACEMENTS_PATH.read_text(encoding="utf-8")) if REPLACEMENTS_PATH.is_file() else {"replacements": []}
    ledger = [row["version"] for row in snapshot["migrations"]]
    if len(ledger) != len(set(ledger)):
        print("ERROR: duplicate full migration version strings in ledger snapshot", file=sys.stderr)
        return 2
    gaps = {row["version"]: row for row in gaps_doc.get("gaps", [])}
    replacements = {row["version"]: row for row in replacements_doc.get("replacements", [])}
    replacements.update({row["version"]: row for row in gaps_doc.get("replacements", []) if row["version"] not in replacements})
    if set(gaps) & set(replacements):
        print("ERROR: a migration cannot be both a gap and a source replacement", file=sys.stderr)
        return 2
    if set(gaps) - set(ledger) or set(replacements) - set(ledger):
        print("ERROR: migration gap/replacement metadata refers to a version absent from the observed ledger", file=sys.stderr)
        return 2

    missing: list[str] = []
    original_sources = 0
    checked_replacements = 0
    for version in ledger:
        target = MIGRATIONS / f"{version}.sql"
        if version in replacements:
            entry = replacements[version]
            if not target.is_file():
                missing.append(version)
                continue
            raw = target.read_bytes()
            expected_sha = entry.get("replacement_sha256")
            if not raw.startswith(BANNER.encode("utf-8")) or not expected_sha or sha256(raw) != expected_sha:
                print(f"ERROR: replacement marker/checksum mismatch for {target.relative_to(ROOT)}", file=sys.stderr)
                return 2
            checked_replacements += 1
        elif target.is_file():
            if version in gaps:
                print(f"ERROR: {version} is still marked as a source gap although a file exists; reconcile metadata", file=sys.stderr)
                return 2
            original_sources += 1
        else:
            if version not in gaps:
                print(f"ERROR: undocumented missing source: {target.relative_to(ROOT)}", file=sys.stderr)
                return 2
            missing.append(version)

    if gaps_doc.get("numeric_prefix_collisions"):
        for prefix, versions in gaps_doc["numeric_prefix_collisions"].items():
            actual = sorted(v for v in ledger if v.split("_", 1)[0] == prefix)
            if sorted(versions) != actual:
                print(f"ERROR: numeric prefix collision manifest drift for {prefix}", file=sys.stderr)
                return 2

    print(f"Observed ledger snapshot: {snapshot['snapshot_date']} ({len(ledger)} migration identities).")
    print(f"Canonical source files: {original_sources}; labelled replacements verified: {checked_replacements}; unresolved path gaps: {len(missing)}.")
    if checked_replacements:
        print(f"HISTORICAL BYTE PROVENANCE STILL UNRESOLVED for {checked_replacements} replacement(s). Exact applied SQL has not been recovered.")
    if missing:
        print("UNRESOLVED MIGRATION SOURCE PATHS:")
        for version in missing:
            print(f"  - {version}")
    if missing or (args.strict and checked_replacements and not args.allow_replacements):
        print("Migration-source gate: BLOCKED. Use --allow-replacements only for a disposable replay with explicit acceptance.")
        return 1
    if checked_replacements and not args.allow_replacements:
        print("Path coverage is verified, but exact-source parity is not. Use --strict to keep this release gate blocked.")
        return 0
    print("Path coverage passed. Any replacements remain explicitly non-historical and need clean replay/schema parity before release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
