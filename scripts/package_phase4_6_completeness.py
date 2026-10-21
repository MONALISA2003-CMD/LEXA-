#!/usr/bin/env python3
"""Build and verify a complete, source-only LEXA Phase 4–6 handoff archive.

The ZIP overlays the repository root. It excludes runtime caches, build output,
node_modules, symlinks, and actual secret environment files. Two package-internal
SHA-256 inventories and a full embedded file manifest are regenerated on each run.
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
INVENTORIES = ("SHA256SUMS.txt", "PACKAGE_FILE_SHA256SUMS.txt")
INTERNAL_MANIFEST = "LEXA_PHASE4_6_COMPLETENESS_MANIFEST_2026-10-21.json"
EXCLUDED_DIRS = {
    ".git", ".pytest_cache", "node_modules", ".next", "__pycache__", ".venv",
    "venv", "dist", "build", ".turbo", ".cache", "coverage", "target",
    "playwright-report", "test-results", "htmlcov",
}
EXCLUDED_FILES = {".DS_Store", "Thumbs.db"}
REQUIRED = {
    "README.md", "FRESH_NEW_PRODUCT_STRATEGY.md", "RELEASE.txt", ".env.example",
    ".github/workflows/lexa-ci.yml", "apps/web/package.json",
    "apps/api/app/routes/commerce.py", "apps/api/app/routes/inventory.py",
    "migrations/migration_dispositions.json", "migrations/038_phase6_movement_health_indexes.sql",
    "PHASE4_6_COMPLETENESS_IMPLEMENTATION_REPORT_2026-10-21.md",
    "PHASE4_6_COMPLETENESS_ACCEPTANCE_MATRIX_2026-10-21.md",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def secret_env(path: Path) -> bool:
    name = path.name
    if name == ".env.example":
        return False
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def source_files() -> list[Path]:
    result: list[Path] = []
    for current, dirs, names in os.walk(ROOT, topdown=True, followlinks=False):
        base = Path(current)
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS and not (base / d).is_symlink())
        for name in sorted(names):
            path = base / name
            if path.is_symlink() or name in EXCLUDED_FILES or secret_env(path):
                continue
            if path.suffix.lower() in {".pyc", ".pyo", ".log"}:
                continue
            if path.name == INTERNAL_MANIFEST:
                continue
            result.append(path)
    return sorted(result, key=lambda p: p.relative_to(ROOT).as_posix())


def write_inventory(path: Path, label: str, files: list[Path]) -> None:
    lines = [label, "Generated from the packageable source tree. Both checksum inventory files are excluded from the inventories.", ""]
    for source in files:
        relative = source.relative_to(ROOT).as_posix()
        lines.append(f"{sha256(source.read_bytes())}  {relative}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="ZIP output path outside the repository")
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("output ZIP must be outside the project tree")
    output.parent.mkdir(parents=True, exist_ok=True)

    # Inventory files hash every packageable source file except the two inventories.
    inventory_targets = {ROOT / name for name in INVENTORIES}
    files = [p for p in source_files() if p not in inventory_targets]
    write_inventory(ROOT / INVENTORIES[0], "LEXA Phase 4–6 completeness source inventory", files)
    write_inventory(ROOT / INVENTORIES[1], "LEXA package-file SHA-256 inventory", files)

    files = source_files()
    entries: dict[str, bytes] = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in files}
    missing = sorted(REQUIRED - set(entries))
    if missing:
        print(f"ERROR: required source files missing: {missing}", file=sys.stderr)
        return 2

    records = [
        {"path": name, "size_bytes": len(data), "sha256": sha256(data)}
        for name, data in entries.items()
    ]
    manifest = {
        "manifest_version": 1,
        "project": "LEXA",
        "package_version": "2.11.0",
        "candidate": "2.11.0+phase4-6.completeness.increment03",
        "date": "2026-10-21",
        "archive_layout": "repository-root-overlay",
        "source_file_count": len(records),
        "sha256_inventories": list(INVENTORIES),
        "exclusions": {
            "directories": sorted(EXCLUDED_DIRS),
            "secret_env_files": "excluded except .env.example",
            "symlinks": "excluded",
            "compiled_and_log_files": "excluded",
        },
        "files": records,
        "release_boundary": {
            "production_release_accepted": False,
            "candidate_committed_or_deployed_by_this_package_job": False,
            "production_schema_mutated": False,
            "historical_six_file_recovery": "closed by approved permanent replacement disposition; no historical byte-parity claim",
            "clean_replay": "plan-only locally; actual disposable database replay remains CI gate",
        },
    }
    manifest_data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
        zf.writestr(INTERNAL_MANIFEST, manifest_data)

    # Full post-write verification: path safety, source coverage, all hashes and ZIP CRC.
    with zipfile.ZipFile(output, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failure at {bad}")
        names = zf.namelist()
        expected_names = set(entries) | {INTERNAL_MANIFEST}
        if len(names) != len(set(names)) or set(names) != expected_names:
            raise RuntimeError("archive entry coverage mismatch or duplicate paths")
        for name in names:
            posix = PurePosixPath(name)
            if posix.is_absolute() or ".." in posix.parts or "\\" in name:
                raise RuntimeError(f"unsafe archive path: {name}")
            if secret_env(Path(posix.name)):
                raise RuntimeError(f"secret environment file in archive: {name}")
        parsed = json.loads(zf.read(INTERNAL_MANIFEST))
        if len(parsed["files"]) != len(entries):
            raise RuntimeError("embedded manifest file count differs from archive source count")
        for record in parsed["files"]:
            data = zf.read(record["path"])
            if len(data) != record["size_bytes"] or sha256(data) != record["sha256"]:
                raise RuntimeError(f"embedded source hash mismatch: {record['path']}")
            if data != entries[record["path"]]:
                raise RuntimeError(f"packaged source differs from working tree: {record['path']}")

    archive_hash = sha256(output.read_bytes())
    sidecar = Path(str(output) + ".sha256")
    sidecar.write_text(f"{archive_hash}  {output.name}\n", encoding="utf-8")
    external_manifest = Path(str(output) + ".manifest.json")
    external_manifest.write_bytes(manifest_data)
    print(f"PASS: packaged and verified {len(entries)} source files plus embedded manifest")
    print(f"Archive: {output}")
    print(f"Size: {output.stat().st_size} bytes")
    print(f"SHA-256: {archive_hash}")
    print(f"SHA-256 sidecar: {sidecar}")
    print(f"External manifest: {external_manifest}")
    print("Actual .env files excluded; .env.example retained; no SQL executed during packaging.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
