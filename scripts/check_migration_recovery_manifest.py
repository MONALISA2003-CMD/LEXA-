#!/usr/bin/env python3
"""Validate LEXA reconstructed-source separation and content hashes.

Default success means only that the forensic manifest is internally consistent. It does not
mean the six exact historical SQL sources have been recovered. --strict-exact intentionally
fails until the exact bytes are recovered and independently verified.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
GAPS_PATH = MIGRATIONS / "source_gaps.json"
MANIFEST_PATH = MIGRATIONS / "reconstructed_source_manifest.json"
EXPECTED = {
    "010_phase2_catalog_intelligence": "migrations/reconstructed/010_phase2_catalog_intelligence.equivalent.sql",
    "011_phase2_catalog_runtime_constraints": "migrations/reconstructed/011_phase2_catalog_runtime_constraints.equivalent.sql",
    "023_phase4_purchasing_core": "migrations/reconstructed/023_phase4_purchasing_core.equivalent.sql",
    "024_phase4_purchasing_security": "migrations/reconstructed/024_phase4_purchasing_security.equivalent.sql",
    "025_phase4_purchasing_permissions": "migrations/reconstructed/025_phase4_purchasing_permissions.equivalent.sql",
    "026_phase4_membership_branch_integrity": "migrations/reconstructed/026_phase4_membership_branch_integrity.equivalent.sql",
}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-exact", action="store_true", help="fail unless all six original source files exist and are verified")
    args=parser.parse_args()
    try:
        gaps=json.loads(GAPS_PATH.read_text(encoding="utf-8"))["gaps"]
        manifest=json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: unable to read recovery manifest: {exc}",file=sys.stderr); return 2
    gap_map={item["version"]:item for item in gaps}
    if len(gap_map)!=len(gaps):
        print("ERROR: duplicate source gap identities",file=sys.stderr); return 2
    if set(gap_map)!=set(EXPECTED):
        print("ERROR: source_gaps.json no longer contains the exact six expected full identifiers",file=sys.stderr)
        print("expected="+", ".join(sorted(EXPECTED)),file=sys.stderr)
        print("actual="+", ".join(sorted(gap_map)),file=sys.stderr)
        return 2
    entries={item.get("gap_version"):item for item in manifest.get("source_gap_equivalents",[])}
    if set(entries)!=set(EXPECTED):
        print("ERROR: reconstructed manifest must map each of the six gaps exactly once",file=sys.stderr); return 2
    errors=[]
    for version,rel in EXPECTED.items():
        target=ROOT/rel
        if target.parent != (MIGRATIONS/"reconstructed"):
            errors.append(f"{version}: equivalent is not isolated under migrations/reconstructed")
        if not target.is_file():
            errors.append(f"{version}: equivalent file missing: {rel}")
        else:
            entry=entries[version]
            actual=sha256(target)
            if actual != entry.get("sha256"):
                errors.append(f"{version}: SHA-256 mismatch for {rel}")
            if target.stat().st_size != entry.get("bytes"):
                errors.append(f"{version}: byte-count mismatch for {rel}")
        historical=MIGRATIONS/f"{version}.sql"
        if historical.exists():
            errors.append(f"{version}: a file exists at the historical path; do not let reconstruction impersonate source recovery")
        if entry.get("path") != rel:
            errors.append(f"{version}: manifest path mismatch")
        if entry.get("status") != "reconstructed_equivalent_not_historical_source":
            errors.append(f"{version}: status must remain reconstructed_equivalent_not_historical_source")
    for entry in manifest.get("additional_isolated_replay_files", []):
        rel = entry.get("path", "")
        target = ROOT / rel
        if target.parent != (MIGRATIONS / "reconstructed"):
            errors.append(f"compatibility delta {rel}: file is not isolated under migrations/reconstructed")
        elif not target.is_file():
            errors.append(f"compatibility delta {rel}: file missing")
        else:
            if sha256(target) != entry.get("sha256"):
                errors.append(f"compatibility delta {rel}: SHA-256 mismatch")
            if target.stat().st_size != entry.get("bytes"):
                errors.append(f"compatibility delta {rel}: byte-count mismatch")
    if errors:
        for error in errors: print("ERROR: "+error,file=sys.stderr)
        return 2
    print("PASS: manifest/hash/separation checks are internally consistent.")
    print(f"EXACT HISTORICAL SOURCES STILL MISSING: {len(gap_map)}")
    print("Versions: "+", ".join(sorted(gap_map)))
    print("This check does not validate semantic schema parity or make the source-release gate pass.")
    if args.strict_exact:
        print("STRICT EXACT-SOURCE GATE: BLOCKED (expected until original SQL bytes are recovered).",file=sys.stderr)
        return 1
    return 0
if __name__=="__main__":
    raise SystemExit(main())
