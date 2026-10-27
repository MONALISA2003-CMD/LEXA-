#!/usr/bin/env python3
"""Safely replace a Git checkout with one verified LEXA source archive.

Default behaviour is dry-run. Destructive application requires --apply, an exact
expected HEAD SHA, a clean working tree, a SHA-256 checksum, and a valid canonical
LEXA archive. The .git metadata is never removed.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

REQUIRED_FILES = (
    "README.md",
    "apps/web/package.json",
    "apps/api/app/main.py",
    "migrations/README.md",
    ".github/workflows/ci.yml",
    ".github/workflows/replace-from-archive.yml",
)
MAX_ARCHIVE_BYTES = 500 * 1024 * 1024
MAX_ARCHIVE_FILES = 20_000


class ReplacementError(RuntimeError):
    pass


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise ReplacementError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(archive: Path, expected_sha: str, stage: Path) -> int:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha):
        raise ReplacementError("Expected SHA-256 must be exactly 64 hexadecimal characters")
    actual_sha = sha256_file(archive)
    if actual_sha.lower() != expected_sha.lower():
        raise ReplacementError(f"Archive checksum mismatch: expected {expected_sha.lower()}, got {actual_sha}")

    try:
        zf = ZipFile(archive, "r")
    except (OSError, BadZipFile) as exc:
        raise ReplacementError(f"Cannot open a valid ZIP archive: {exc}") from exc

    with zf:
        infos = zf.infolist()
        files = [info for info in infos if not info.is_dir()]
        if not files:
            raise ReplacementError("The ZIP contains no files")
        if len(files) > MAX_ARCHIVE_FILES:
            raise ReplacementError(f"Archive contains too many files ({len(files)})")
        total_uncompressed = sum(info.file_size for info in files)
        if total_uncompressed > MAX_ARCHIVE_BYTES:
            raise ReplacementError(f"Archive uncompressed size is too large ({total_uncompressed} bytes)")

        seen: set[str] = set()
        folded: set[str] = set()
        for info in infos:
            raw = info.filename
            if "\\" in raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
                raise ReplacementError(f"Unsafe path in ZIP: {raw!r}")
            path = PurePosixPath(raw.rstrip("/"))
            if not path.parts or any(part in (".", "..", "") for part in path.parts):
                raise ReplacementError(f"Unsafe path in ZIP: {raw!r}")
            if ".git" in path.parts:
                raise ReplacementError("Archive must not contain Git metadata")
            if path.parts[0] in ("", "/"):
                raise ReplacementError(f"Archive path is not relative: {raw!r}")
            # Reject symlinks, devices and other non-regular file entries.
            mode = (info.external_attr >> 16) & 0xFFFF
            kind = stat.S_IFMT(mode)
            if kind and kind not in (stat.S_IFREG, stat.S_IFDIR):
                raise ReplacementError(f"Non-regular ZIP entry is not allowed: {raw!r}")
            if info.is_dir():
                continue
            norm = path.as_posix()
            if norm in seen:
                raise ReplacementError(f"Duplicate path in ZIP: {norm}")
            seen.add(norm)
            lower = norm.casefold()
            if lower in folded:
                raise ReplacementError(f"Case-insensitive path collision in ZIP: {norm}")
            folded.add(lower)

        missing = [name for name in REQUIRED_FILES if name not in seen]
        if missing:
            raise ReplacementError(
                "ZIP is not a canonical LEXA source archive; required root paths missing: "
                + ", ".join(missing)
            )

        for info in files:
            path = PurePosixPath(info.filename)
            destination = stage.joinpath(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                # Keep ordinary permission bits only; never carry special permission bits.
                destination.chmod(mode & 0o755)
    return len(files)


def tracked_tree_summary(root: Path) -> tuple[int, list[str]]:
    old_paths = [child.name for child in root.iterdir() if child.name != ".git"]
    tracked = run_git(root, "ls-files", "-z").split("\0")
    tracked_count = sum(bool(item) for item in tracked)
    return tracked_count, sorted(old_paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Verified clean LEXA source ZIP")
    parser.add_argument("--sha256", required=True, help="Expected SHA-256 checksum for the ZIP")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--expected-head", help="Exact current Git HEAD required when applying")
    parser.add_argument("--apply", action="store_true", help="Perform the full replacement; without this flag only preview")
    args = parser.parse_args()

    root = args.repo_root.resolve()
    archive = args.archive.resolve()
    if not root.is_dir() or not (root / ".git").exists():
        raise SystemExit("ERROR: repository root must be a real Git checkout with .git metadata")
    if not archive.is_file():
        raise SystemExit(f"ERROR: archive not found: {archive}")

    try:
        git_root = Path(run_git(root, "rev-parse", "--show-toplevel")).resolve()
        if git_root != root:
            raise ReplacementError(f"--repo-root must be the Git root ({git_root})")
        current_head = run_git(root, "rev-parse", "HEAD")
        status = run_git(root, "status", "--porcelain")
        ignored_status = run_git(root, "status", "--porcelain", "--ignored", "--untracked-files=all")
        if status:
            raise ReplacementError("Working tree is not clean; commit or stash changes before replacement")
        if ignored_status:
            raise ReplacementError("Ignored or untracked files are present; use a fresh clean checkout so local secrets/build files cannot be deleted silently")
        if args.apply:
            if not args.expected_head:
                raise ReplacementError("--apply requires --expected-head with an exact commit SHA")
            if not re.fullmatch(r"[0-9a-fA-F]{40}", args.expected_head):
                raise ReplacementError("--expected-head must be a full 40-character Git commit SHA")
            if current_head.lower() != args.expected_head.lower():
                raise ReplacementError(f"HEAD changed: expected {args.expected_head}, found {current_head}")

        with tempfile.TemporaryDirectory(prefix="lexa-source-stage-") as tmp:
            stage = Path(tmp) / "source"
            stage.mkdir()
            new_count = validate_archive(archive, args.sha256, stage)
            old_count, top_level = tracked_tree_summary(root)
            print(f"Repository root: {root}")
            print(f"Current HEAD: {current_head}")
            print(f"Current tracked files: {old_count}")
            print(f"Current top-level entries to replace: {', '.join(top_level) if top_level else '(none)'}")
            print(f"Validated archive: {archive}")
            print(f"Archive SHA-256: {sha256_file(archive)}")
            print(f"New source files: {new_count}")
            if not args.apply:
                print("DRY RUN ONLY: no files were deleted or replaced. Add --apply and --expected-head to apply.")
                return 0

            # The staging directory is outside the checkout; preserve only Git metadata from the old tree.
            for child in list(root.iterdir()):
                if child.name == ".git":
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            for child in stage.iterdir():
                destination = root / child.name
                if child.is_dir():
                    shutil.copytree(child, destination)
                else:
                    shutil.copy2(child, destination)
            print("REPLACEMENT COMPLETE: all repository files were replaced from the verified archive; .git was preserved.")
            print("Review `git status --short`, run CI, and commit only through the guarded workflow.")
        return 0
    except ReplacementError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
