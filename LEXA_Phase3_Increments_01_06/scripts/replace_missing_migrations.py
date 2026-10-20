#!/usr/bin/env python3
"""Install clearly labelled SQL source replacements when exact historical bytes are unavailable.

This script never calls a database, deploys code, or claims recovered historical provenance.
It copies the existing, separately labelled equivalent SQL files into the canonical migration
paths only when those paths are absent (or already contain the exact same generated replacement).
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_EQUIVALENTS: dict[str, dict[str, str]] = {
    "010_phase2_catalog_intelligence": {
        "source": "migrations/reconstructed/010_phase2_catalog_intelligence.equivalent.sql",
        "git_blob_sha1": "6328329cd7240a448f82fd09e3701eb1ddd34e37",
    },
    "011_phase2_catalog_runtime_constraints": {
        "source": "migrations/reconstructed/011_phase2_catalog_runtime_constraints.equivalent.sql",
        "git_blob_sha1": "ca15ec0b51d712f251784009460a40223c10708b",
    },
    "023_phase4_purchasing_core": {
        "source": "migrations/reconstructed/023_phase4_purchasing_core.equivalent.sql",
        "git_blob_sha1": "e0c8c2174a048ec27eb76a3ab7f4436d7053870b",
    },
    "024_phase4_purchasing_security": {
        "source": "migrations/reconstructed/024_phase4_purchasing_security.equivalent.sql",
        "git_blob_sha1": "96ed17c27d2ab78935651ef6bf366a424f93eb5a",
    },
    "025_phase4_purchasing_permissions": {
        "source": "migrations/reconstructed/025_phase4_purchasing_permissions.equivalent.sql",
        "git_blob_sha1": "8fca13cbcc18d412f3d6a1bc4f84137dda5a6c53",
    },
    "026_phase4_membership_branch_integrity": {
        "source": "migrations/reconstructed/026_phase4_membership_branch_integrity.equivalent.sql",
        "git_blob_sha1": "2469080949aa636afc2bbe9e3f6eac325a21a4db",
    },
}

BANNER = """-- EXPLICIT HISTORICAL SOURCE REPLACEMENT — NOT THE ORIGINAL APPLIED SQL BYTES.
-- This file is a reviewed replacement assembled from the separately labelled reconstructed equivalent.
-- Historical source recovery failed; this file MUST NOT be reported as byte-recovered provenance.
-- See migrations/source_replacements_2026-10-20.json for source and output checksums.
"""


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replacement_bytes(source_bytes: bytes, version: str, source_hash: str) -> bytes:
    text = source_bytes.decode("utf-8")
    if not (text.startswith("-- RECONSTRUCTED EQUIVALENT") or text.startswith("-- RECONSTRUCTED EQUIVALENT of")):
        raise RuntimeError(f"{version}: equivalent source lacks the mandatory reconstruction label")
    body = text
    prefix = BANNER + f"-- Full migration identity: {version}\n-- Equivalent source Git blob SHA-1: {source_hash}\n\n"
    return (prefix + body).encode("utf-8")


def replacement_checker_wrapper() -> bytes:
    return (
        "#!/usr/bin/env python3\n"
        "\"\"\"Replacement-aware entrypoint; exact historical SQL provenance remains distinct.\"\"\"\n"
        "from check_migration_sources_replacement_aware import main\n"
        "if __name__ == \"__main__\":\n"
        "    raise SystemExit(main())\n"
    ).encode("utf-8")


def build(source_root: Path, *, apply: bool, expected: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    mapping = expected if expected is not None else EXPECTED_EQUIVALENTS
    migration_root = source_root / "migrations"
    manifest_path = migration_root / "source_replacements_2026-10-20.json"
    gaps_path = migration_root / "source_gaps.json"
    checker_path = source_root / "scripts" / "check_migration_sources.py"
    checker_backup = source_root / ".migration-source-audit" / "check_migration_sources.py.original"
    checker_impl_path = source_root / "scripts" / "check_migration_sources_replacement_aware.py"
    checker_impl_template = Path(__file__).with_name("check_migration_sources_replacement_aware.py")
    rows: list[dict[str, Any]] = []
    pending: list[tuple[Path, bytes, dict[str, Any]]] = []

    for version, spec in mapping.items():
        source_path = source_root / spec["source"]
        target_path = migration_root / f"{version}.sql"
        if not source_path.is_file():
            raise RuntimeError(f"Missing labelled equivalent source: {spec['source']}")
        source_bytes = source_path.read_bytes()
        source_hash = git_blob_sha(source_bytes)
        expected_hash = spec.get("git_blob_sha1")
        if expected_hash and source_hash != expected_hash:
            raise RuntimeError(f"Source provenance guard failed for {spec['source']}: expected {expected_hash}, got {source_hash}")
        replacement = replacement_bytes(source_bytes, version, source_hash)
        item = {
            "version": version,
            "expected_path": str(target_path.relative_to(source_root)),
            "replacement_kind": "reconstructed-equivalent-not-historical-original",
            "historical_bytes_recovered": False,
            "equivalent_source_path": str(source_path.relative_to(source_root)),
            "equivalent_source_git_blob_sha1": source_hash,
            "equivalent_source_sha256": sha256(source_bytes),
            "replacement_sha256": sha256(replacement),
            "replacement_size_bytes": len(replacement),
        }
        if target_path.exists():
            existing = target_path.read_bytes()
            if existing != replacement:
                raise RuntimeError(
                    f"Refusing to overwrite existing migration {target_path.relative_to(source_root)}. "
                    "Inspect the file; only an absent path or identical generated replacement is safe."
                )
            item["action"] = "already-present-identical-replacement"
        else:
            item["action"] = "create-replacement" if apply else "would-create-replacement"
            pending.append((target_path, replacement, item))
        rows.append(item)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "generated_date": "2026-10-20",
        "purpose": "Documented fallback when exact historical migration bytes cannot be recovered.",
        "status": "REPLACEMENTS_ONLY_NOT_HISTORICAL_SOURCE_RECOVERY",
        "historical_source_gate": "BLOCKED_FOR_EXACT_BYTE_PARITY",
        "production_execution_performed": False,
        "database_execution_performed": False,
        "replacements": rows,
    }

    # Validate release metadata before any writes. Keep unrelated gaps untouched.
    gaps_doc: dict[str, Any] | None = None
    checker_original: bytes | None = None
    wrapper = replacement_checker_wrapper()
    if apply and gaps_path.is_file():
        gaps_doc = json.loads(gaps_path.read_text(encoding="utf-8"))
        current_gaps = {row["version"]: row for row in gaps_doc.get("gaps", [])}
        current_replacements = {row["version"]: row for row in gaps_doc.get("replacements", [])}
        for item in rows:
            version = item["version"]
            if version not in current_gaps and version not in current_replacements:
                raise RuntimeError(f"source_gaps.json has no gap/replacement record for {version}; refusing an untracked substitution")
        if not checker_impl_template.is_file():
            raise RuntimeError("Replacement-aware checker template is missing from the package")
        checker_impl_bytes = checker_impl_template.read_bytes()
        if checker_impl_path.exists() and checker_impl_path.read_bytes() != checker_impl_bytes:
            raise RuntimeError("An existing replacement-aware checker has different bytes; review before overwriting")
        if checker_path.is_file():
            current_checker = checker_path.read_bytes()
            if b"check_migration_sources_replacement_aware" in current_checker:
                checker_original = None
            else:
                checker_text = current_checker.decode("utf-8")
                if "Track the exact applied live migration SQL sources" not in checker_text or "source now exists" not in checker_text:
                    raise RuntimeError("Migration checker source does not match the expected pre-replacement checker; refusing to replace it")
                if checker_backup.exists() and checker_backup.read_bytes() != current_checker:
                    raise RuntimeError("Historical migration-checker backup already exists with different bytes")
                checker_original = current_checker
    elif apply and checker_path.is_file():
        raise RuntimeError("source_gaps.json is missing; cannot update the checker without preserving gap metadata")

    if apply:
        migration_root.mkdir(parents=True, exist_ok=True)
        for target_path, data, _ in pending:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(data)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        if gaps_doc is not None:
            gap_rows = {row["version"]: row for row in gaps_doc.get("gaps", [])}
            replacement_rows = {row["version"]: row for row in gaps_doc.get("replacements", [])}
            for item in rows:
                replacement_rows[item["version"]] = {
                    **{k: v for k, v in item.items() if k != "action"},
                    "reason": "Exact historical bytes were not recovered; a separately labelled reconstructed equivalent is now at the canonical path.",
                    "next_step": "Validate the exact replacement checksum, run full disposable clean replay/schema parity, and retain the historical provenance blocker until that evidence is reviewed.",
                }
                gap_rows.pop(item["version"], None)
            gaps_doc["gaps"] = list(gap_rows.values())
            gaps_doc["replacements"] = list(replacement_rows.values())
            gaps_doc["status"] = "REPLACEMENTS_PRESENT_HISTORICAL_BYTE_PARITY_UNRESOLVED"
            gaps_doc["purpose"] = "Track original applied migration provenance gaps separately from explicitly labelled replacement SQL files."
            gaps_path.write_text(json.dumps(gaps_doc, indent=2) + "\n", encoding="utf-8")
            if checker_impl_path != checker_path and (not checker_impl_path.exists()):
                checker_impl_path.parent.mkdir(parents=True, exist_ok=True)
                checker_impl_path.write_bytes(checker_impl_bytes)
            if checker_original is not None:
                checker_backup.parent.mkdir(parents=True, exist_ok=True)
                if not checker_backup.exists():
                    checker_backup.write_bytes(checker_original)
                checker_path.write_bytes(wrapper)

        manifest["manifest_path"] = str(manifest_path.relative_to(source_root))
        manifest["files_written"] = len(pending) + 1 + (2 if gaps_doc is not None else 0) + (2 if checker_original is not None else 0)
    else:
        manifest["manifest_path"] = str(manifest_path.relative_to(source_root))
        manifest["files_written"] = 0
    return manifest

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd(), help="Root of the full LEXA checkout")
    parser.add_argument("--apply", action="store_true", help="Write replacement SQL files and a provenance manifest; default is dry run")
    args = parser.parse_args()
    try:
        manifest = build(args.source_root.resolve(), apply=args.apply)
    except (OSError, UnicodeDecodeError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(manifest, indent=2))
    if not args.apply:
        print("DRY RUN ONLY. Re-run with --apply to create files. No SQL was executed.")
    else:
        print("REPLACEMENT FILES WRITTEN. Original historical byte provenance remains unresolved; review and clean-replay before use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
