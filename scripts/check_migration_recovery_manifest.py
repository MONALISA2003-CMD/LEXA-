#!/usr/bin/env python3
"""Verify accepted migration replacements and retained reconstruction-source checksums."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MIGRATIONS=ROOT/"migrations"
GAPS=MIGRATIONS/"source_gaps.json"
RECON=MIGRATIONS/"reconstructed_source_manifest.json"
EXPECTED={
"010_phase2_catalog_intelligence","011_phase2_catalog_runtime_constraints",
"023_phase4_purchasing_core","024_phase4_purchasing_security",
"025_phase4_purchasing_permissions","026_phase4_membership_branch_integrity",
}
BANNER="-- ACCEPTED REPLACEMENT — ORIGINAL HISTORICAL SOURCE LOST; NOT BYTE-IDENTICAL."
def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def main()->int:
 try:
  source=json.loads(GAPS.read_text(encoding="utf-8")); recon=json.loads(RECON.read_text(encoding="utf-8"))
 except Exception as exc:
  print(f"ERROR: unable to read migration provenance manifests: {exc}",file=sys.stderr); return 2
 replacements={row["version"]:row for row in source.get("replacements",[])}
 if set(replacements)!=EXPECTED or source.get("gaps"):
  print("ERROR: accepted replacement manifest must cover exactly the six declared-lost sources and contain no unresolved path gaps",file=sys.stderr); return 2
 errors=[]
 for version,row in replacements.items():
  target=ROOT/row.get("expected_path","")
  if row.get("original_source_status")!="LOST_DECLARED": errors.append(f"{version}: source loss not declared")
  if not target.is_file(): errors.append(f"{version}: accepted replacement missing")
  elif not target.read_text(encoding="utf-8").startswith(BANNER): errors.append(f"{version}: accepted replacement banner missing")
  elif sha(target)!=row.get("replacement_sha256"): errors.append(f"{version}: accepted replacement SHA-256 mismatch")
 entries={row.get("gap_version"):row for row in recon.get("source_gap_equivalents",[])}
 if set(entries)!=EXPECTED: errors.append("reconstructed_source_manifest.json must retain all six equivalent-source checksums")
 for version,row in entries.items():
  path=ROOT/row.get("path","")
  if not path.is_file(): errors.append(f"{version}: reconstruction reference missing")
  elif sha(path)!=row.get("sha256"): errors.append(f"{version}: reconstruction reference SHA-256 mismatch")
 if errors:
  print("MIGRATION REPLACEMENT GATE: FAIL",file=sys.stderr)
  for e in errors: print(" - "+e,file=sys.stderr)
  return 2
 print("ACCEPTED REPLACEMENTS VERIFIED: 6")
 print("UNRESOLVED SOURCE PATH GAPS: 0")
 print("HISTORICAL BYTE PROVENANCE: original files declared lost; accepted replacements are explicitly not byte-identical")
 print("CLEAN REPLAY AND LIVE-SCHEMA PARITY: required separate release gates")
 return 0
if __name__=="__main__": raise SystemExit(main())
