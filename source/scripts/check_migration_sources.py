#!/usr/bin/env python3
"""Reconcile the recorded production ledger against canonical sources and permanent dispositions.

Historical recovery is closed for sources explicitly approved for permanent replacement.
This script never claims historical bytes were recovered. Semantic clean replay is a separate gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
SNAPSHOT_PATH = MIGRATIONS / "live_ledger_snapshot_2026-10-21.json"
GAPS_PATH = MIGRATIONS / "source_gaps.json"
DISPOSITIONS_PATH = MIGRATIONS / "migration_dispositions.json"
RECONSTRUCTED_MANIFEST = MIGRATIONS / "reconstructed_source_manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail for any applied migration without a source or valid permanent disposition")
    parser.add_argument("--require-semantic-validation", action="store_true", help="also require a current clean-replay evidence artifact")
    parser.add_argument("--evidence", type=Path, help="evidence JSON emitted by run_clean_migration_replay.py --apply")
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH, help="path to a recorded read-only ledger snapshot")
    args = parser.parse_args()

    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        gap_manifest = json.loads(GAPS_PATH.read_text(encoding="utf-8"))
        disposition_manifest = json.loads(DISPOSITIONS_PATH.read_text(encoding="utf-8"))
        reconstructed = json.loads(RECONSTRUCTED_MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: unable to read source reconciliation inputs: {exc}", file=sys.stderr)
        return 2

    versions = [row.get("version") for row in snapshot.get("migrations", [])]
    if not versions or any(not isinstance(v, str) or not v for v in versions):
        print("ERROR: ledger snapshot has no valid full migration identities", file=sys.stderr)
        return 2
    if len(versions) != len(set(versions)):
        print("ERROR: duplicate full migration version strings in the ledger snapshot", file=sys.stderr)
        return 2

    gap_rows = gap_manifest.get("gaps", [])
    gap_by_version = {row.get("version"): row for row in gap_rows}
    if len(gap_by_version) != len(gap_rows):
        print("ERROR: source_gaps.json contains duplicate versions", file=sys.stderr)
        return 2

    disposition_rows = disposition_manifest.get("permanently_replaced_sources", [])
    disposition_by_version = {row.get("version"): row for row in disposition_rows}
    if len(disposition_by_version) != len(disposition_rows):
        print("ERROR: migration_dispositions.json contains duplicate full identifiers", file=sys.stderr)
        return 2

    reconstructed_by_version = {row.get("gap_version"): row for row in reconstructed.get("source_gap_equivalents", [])}
    if len(reconstructed_by_version) != len(reconstructed.get("source_gap_equivalents", [])):
        print("ERROR: reconstructed manifest contains duplicate equivalent mappings", file=sys.stderr)
        return 2

    ledger_set = set(versions)
    unknown_gap_ids = sorted(set(gap_by_version) - ledger_set)
    if unknown_gap_ids:
        print("ERROR: source gaps not present in ledger snapshot: " + ", ".join(unknown_gap_ids), file=sys.stderr)
        return 2

    unresolved: list[str] = []
    source_present: list[str] = []
    permanently_replaced: list[str] = []
    pending_semantic: list[str] = []
    errors: list[str] = []

    for version in versions:
        canonical = MIGRATIONS / f"{version}.sql"
        gap = gap_by_version.get(version)
        if canonical.is_file():
            if gap is not None and version not in disposition_by_version:
                errors.append(f"{version}: canonical source exists but is still marked as an un-dispositioned gap")
            else:
                source_present.append(version)
            continue

        disposition = disposition_by_version.get(version)
        if not disposition:
            unresolved.append(version)
            if gap is None:
                errors.append(f"{version}: missing source has no source-gap record or approved permanent disposition")
            continue

        replacement_rel = disposition.get("replacement_path", "")
        replacement = ROOT / replacement_rel
        manifest_entry = reconstructed_by_version.get(version)
        if disposition.get("disposition") != "PERMANENTLY_REPLACED":
            errors.append(f"{version}: unsupported permanent disposition value")
            continue
        if disposition.get("historical_bytes_recovered") is not False:
            errors.append(f"{version}: permanent replacement must explicitly state historical bytes were not recovered")
        if not replacement_rel or replacement.parent != (MIGRATIONS / "reconstructed"):
            errors.append(f"{version}: replacement path must remain isolated under migrations/reconstructed")
            continue
        if not replacement.is_file():
            errors.append(f"{version}: approved replacement is missing: {replacement_rel}")
            continue
        expected_hash = disposition.get("replacement_sha256")
        actual_hash = sha256(replacement)
        if not expected_hash or actual_hash != expected_hash:
            errors.append(f"{version}: permanent replacement SHA-256 mismatch")
        if not manifest_entry or manifest_entry.get("path") != replacement_rel:
            errors.append(f"{version}: replacement path does not match reconstructed source manifest")
        elif manifest_entry.get("sha256") != actual_hash or manifest_entry.get("bytes") != replacement.stat().st_size:
            errors.append(f"{version}: replacement manifest hash/byte count mismatch")
        if not gap or gap.get("disposition") != "PERMANENTLY_REPLACED" or gap.get("replacement_path") != replacement_rel:
            errors.append(f"{version}: source_gaps.json contradicts the permanent disposition register")
        else:
            permanently_replaced.append(version)
            if disposition.get("semantic_validation_status") != "PASS":
                pending_semantic.append(version)

    for recovered in gap_manifest.get("recovered_sources", []):
        rel = recovered.get("path", "")
        source = ROOT / rel
        if not rel or not source.is_file():
            errors.append(f"recovered source missing: {rel}")
            continue
        raw = source.read_bytes()
        git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if recovered.get("git_blob_sha1") and git_blob != recovered["git_blob_sha1"]:
            errors.append(f"recovered source Git blob SHA-1 mismatch: {rel}")
        if recovered.get("sha256") and sha256(source) != recovered["sha256"]:
            errors.append(f"recovered source SHA-256 mismatch: {rel}")
        if recovered.get("size_bytes") and source.stat().st_size != recovered["size_bytes"]:
            errors.append(f"recovered source byte count mismatch: {rel}")

    collision_errors = []
    for prefix, expected_versions in gap_manifest.get("numeric_prefix_collisions", {}).items():
        actual = sorted(v for v in versions if v.split("_", 1)[0] == prefix)
        if sorted(expected_versions) != actual:
            collision_errors.append(f"{prefix}: expected {actual}, manifest has {sorted(expected_versions)}")
    errors.extend("numeric prefix collision manifest drift " + item for item in collision_errors)

    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        return 2

    print(f"Recorded ledger snapshot: {snapshot.get('snapshot_date', 'unknown')} ({len(versions)} full migration identities).")
    print(f"CANONICAL SOURCES PRESENT: {len(source_present)}")
    print(f"PERMANENTLY REPLACED SOURCE HISTORIES: {len(permanently_replaced)}")
    if permanently_replaced:
        for version in permanently_replaced:
            print(f"  - {version} -> {disposition_by_version[version]['replacement_path']}")
    print("HISTORICAL RECOVERY GATE: CLOSED BY APPROVED PERMANENT DISPOSITION")
    if pending_semantic:
        print(f"REPLACEMENT SEMANTIC VALIDATION: PENDING ({len(pending_semantic)} approved equivalents require clean replay/schema/security validation)")
    else:
        print("REPLACEMENT SEMANTIC VALIDATION: PASS")
    if unresolved:
        print(f"UNRESOLVED SOURCE GAPS ({len(unresolved)}): " + ", ".join(unresolved))
        return 1 if args.strict else 0
    semantic_evidence_pass = False
    if args.evidence:
        checker = ROOT / "scripts/check_phase6_replay_evidence.py"
        check = __import__("subprocess").run(
            [sys.executable, str(checker), "--evidence", str(args.evidence)],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        if check.returncode == 0:
            semantic_evidence_pass = True
            print(check.stdout.strip())
        else:
            print((check.stdout + check.stderr).strip(), file=sys.stderr)
    if args.require_semantic_validation and not semantic_evidence_pass:
        print("ERROR: current clean replay/schema/security evidence is required; historical source closure alone is not a release pass", file=sys.stderr)
        return 1
    if args.require_semantic_validation:
        print("REPLACEMENT SEMANTIC VALIDATION: PASS (verified current evidence artifact)")
    print("SOURCE RECONCILIATION: PASS (historical exact-byte parity is intentionally not asserted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
