#!/usr/bin/env python3
"""Build and verify a complete, source-only LEXA archive.

The archive includes every regular source/project file under the repository root,
except local runtime artifacts, dependency installations, build output, and actual
secret environment files. It writes a path/hash manifest into the archive and a
separate archive/hash manifest beside the ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INTERNAL_MANIFEST_TEMPLATE = "PHASE{phase}_INCREMENT_{increment}_MANIFEST.json"
REQUIRED_ROOT_PATHS = {
    "README.md",
    ".env.example",
    "render.yaml",
    ".github/workflows/lexa-ci.yml",
    "apps/web/package.json",
    "apps/web/app/page.tsx",
    "apps/api/app/routes/commerce.py",
    "migrations/README.md",
    "scripts/check_migration_sources.py",
}
EXCLUDED_DIRS = {
    ".git", ".pytest_cache", "node_modules", ".next", "__pycache__", ".venv",
    "venv", "dist", "build", ".turbo", ".cache", "coverage", "target",
}
EXCLUDED_FILES = {".DS_Store", "Thumbs.db"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_env_secret(path: Path) -> bool:
    name = path.name
    if name == ".env.example":
        return False
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(ROOT, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            d for d in dirs
            if d not in EXCLUDED_DIRS and not (current_path / d).is_symlink()
        )
        for name in sorted(names):
            path = current_path / name
            if path.is_symlink() or name in EXCLUDED_FILES or is_env_secret(path):
                continue
            if path.suffix in {".pyc", ".pyo", ".log"}:
                continue
            if path.name.startswith("PHASE") and "_INCREMENT_" in path.name and path.name.endswith("_MANIFEST.json"):
                # Never include a stale generated manifest in a new package.
                continue
            files.append(path)
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Path of output ZIP")
    parser.add_argument("--phase", default="2", choices=[str(n) for n in range(1, 10)], help="Phase label")
    parser.add_argument("--increment", default="03", help="Increment label")
    args = parser.parse_args()
    out = Path(args.output).resolve()
    if out == ROOT or ROOT in out.parents:
        parser.error("Output ZIP must be outside the project tree")
    out.parent.mkdir(parents=True, exist_ok=True)

    internal_manifest_name = INTERNAL_MANIFEST_TEMPLATE.format(phase=args.phase, increment=args.increment)
    files = iter_source_files()
    if not files:
        raise SystemExit("Refusing to create an empty source archive")

    entries: dict[str, bytes] = {}
    file_records = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        entries[rel] = data
        file_records.append({"path": rel, "size_bytes": len(data), "sha256": sha256_bytes(data)})

    missing_required = sorted(REQUIRED_ROOT_PATHS - set(entries))
    if missing_required:
        raise SystemExit(f"Required repository-root files missing from source: {missing_required}")

    internal = {
        "manifest_version": 2,
        "project": "LEXA",
        "phase": args.phase,
        "increment": args.increment,
        "archive_layout": "repository-root-overlay",
        "archive_root": ".",
        "files_included": len(file_records),
        "exclusion_policy": {
            "directories": sorted(EXCLUDED_DIRS),
            "actual_env_files": "excluded except .env.example",
            "compiled_and_log_files": "excluded",
        },
        "files": file_records,
    }
    manifest_bytes = (json.dumps(internal, indent=2, sort_keys=True) + "\n").encode()
    internal_path = internal_manifest_name

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, data in entries.items():
            zf.writestr(rel, data)
        zf.writestr(internal_path, manifest_bytes)

    # Re-open and verify archive integrity, exact file coverage, hashes, and secret exclusions.
    with zipfile.ZipFile(out, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise SystemExit(f"ZIP CRC check failed: {bad}")
        names = set(zf.namelist())
        expected_names = set(entries)
        expected_names.add(internal_path)
        if names != expected_names:
            missing = sorted(expected_names - names)
            extra = sorted(names - expected_names)
            raise SystemExit(f"ZIP coverage mismatch; missing={missing[:10]}, extra={extra[:10]}")
        if any(PurePosixPath(n).parts[0] == ROOT.name for n in names):
            raise SystemExit("Archive contains an invalid enclosing project directory; paths must overlay repository root")
        if any(PurePosixPath(n).name == ".env" or (PurePosixPath(n).name.startswith(".env.") and PurePosixPath(n).name != ".env.example") for n in names):
            raise SystemExit("Refusing archive with secret environment file")
        for rel, source_bytes in entries.items():
            packaged = zf.read(rel)
            if packaged != source_bytes:
                raise SystemExit(f"Source content mismatch in archive: {rel}")
        parsed = json.loads(zf.read(internal_path))
        if len(parsed["files"]) != len(entries):
            raise SystemExit("Internal manifest file count mismatch")
        for record in parsed["files"]:
            packed = zf.read(record["path"])
            if sha256_bytes(packed) != record["sha256"]:
                raise SystemExit(f"Internal manifest hash mismatch: {record['path']}")

    archive_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    external = {
        "project": "LEXA",
        "phase": args.phase,
        "increment": args.increment,
        "archive": out.name,
        "archive_path": str(out),
        "archive_sha256": archive_sha,
        "archive_size_bytes": out.stat().st_size,
        "source_file_count": len(entries),
        "internal_manifest": internal_path,
        "archive_layout": "repository-root-overlay",
        "required_root_paths": sorted(REQUIRED_ROOT_PATHS),
        "required_root_paths_check": "passed",
        "verification": {
            "zip_crc": "passed",
            "source_file_coverage": "passed",
            "per_file_content_match": "passed",
            "per_file_sha256_match": "passed",
            "secret_env_exclusion": "passed",
        },
        "files": file_records,
    }
    manifest_path = out.with_name(out.stem + "_Manifest.json")
    manifest_path.write_text(json.dumps(external, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "archive": str(out),
        "archive_sha256": archive_sha,
        "archive_size_bytes": out.stat().st_size,
        "source_file_count": len(entries),
        "manifest": str(manifest_path),
        "zip_crc": "passed",
        "source_coverage": "passed",
        "file_content_and_hash_validation": "passed",
        "secret_env_exclusion": "passed",
        "repository_root_layout": "passed",
        "required_root_paths": "passed",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
