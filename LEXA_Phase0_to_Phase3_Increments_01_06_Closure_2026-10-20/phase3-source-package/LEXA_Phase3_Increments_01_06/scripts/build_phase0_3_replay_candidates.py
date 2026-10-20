#!/usr/bin/env python3
"""Build explicitly labelled clean-replay-only SQL equivalents from pinned source bytes.

Never writes the expected historical migration path and never writes to a database.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

EXPECTED = {
    "migrations/004_catalog_and_rbac_hardening.sql": "a5b65091c2f31697ecd2caf5fdd235ceba468a66",
    "migrations/021_phase5_analytics_foundation.sql": "c32a60352f10a1463937ff4aa0b204adf38f470b",
}
ANCHOR_004 = "ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_category_tenant;"
ANCHOR_021 = "END $fn$;"
TRAILER_021 = "`; // outer transaction handled by PostgreSQL statement parser"


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def build_candidates(source_root: Path, output_root: Path) -> list[Path]:
    originals: dict[str, bytes] = {}
    for rel, expected_sha in EXPECTED.items():
        path = source_root / rel
        if not path.is_file():
            raise RuntimeError(f"Required canonical input is missing: {rel}")
        raw = path.read_bytes()
        actual = git_blob_sha(raw)
        if actual != expected_sha:
            raise RuntimeError(f"Source provenance guard failed for {rel}: expected {expected_sha}, got {actual}")
        originals[rel] = raw

    migration004 = originals["migrations/004_catalog_and_rbac_hardening.sql"].decode("utf-8")
    if migration004.count(ANCHOR_004) != 1:
        raise RuntimeError("Migration 004 replay-equivalent anchor is not unique")
    # Use the original future index names so later IF NOT EXISTS statements do not create duplicate indexes.
    tenant_keys = """-- Replay-only prerequisite keys: the historical 004 source adds these too late for its own composite FKs.
CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_tenant_id ON categories(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_brands_tenant_id ON brands(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_tenant_id ON products(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variants_tenant_id ON product_variants(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_barcodes_tenant_id ON barcodes(tenant_id,id);

"""
    replay004 = (
        "-- REPLAY-ONLY EQUIVALENT, NOT THE HISTORICAL 004 SOURCE BYTES.\n"
        f"-- Original Git blob SHA-1 verified by builder: {EXPECTED['migrations/004_catalog_and_rbac_hardening.sql']}\n"
        "-- Moves necessary composite unique keys ahead of constraints that reference them.\n"
        + migration004.replace(ANCHOR_004, tenant_keys + ANCHOR_004, 1)
    )

    migration021 = originals["migrations/021_phase5_analytics_foundation.sql"].decode("utf-8")
    if migration021.count(ANCHOR_021) != 1:
        raise RuntimeError("Migration 021 function terminator is not unique")
    anchor_end = migration021.index(ANCHOR_021) + len(ANCHOR_021)
    suffix = migration021[anchor_end:]
    trailer_index = suffix.find(TRAILER_021)
    if trailer_index < 0:
        raise RuntimeError("Migration 021 pasted-tool trailer marker was not found")
    encoded_sql_tail = suffix[:trailer_index]
    escaped_newlines = encoded_sql_tail.count(r"\n")
    if escaped_newlines < 10:
        raise RuntimeError(f"Migration 021 repair guard: expected escaped SQL tail, found {escaped_newlines} escaped newlines")
    repaired_body = (migration021[:anchor_end] + encoded_sql_tail.replace(r"\n", "\n")).strip()
    # Drop duplicate terminal COMMITs only; keep the original transaction start and SQL content.
    while repaired_body.upper().rstrip().endswith("COMMIT;"):
        repaired_body = repaired_body.rstrip()[:-len("COMMIT;")].rstrip()
    if any(x in repaired_body for x in ("tools.mcp__Neon", ".unregister;", " krwar=1;", "outer transaction handled")):
        raise RuntimeError("Migration 021 repair candidate still contains pasted non-SQL tool text")
    replay021 = (
        "-- RECONSTRUCTED REPAIR CANDIDATE, NOT HISTORICAL ORIGINAL BYTES.\n"
        f"-- Original malformed Git blob SHA-1 retained as provenance: {EXPECTED['migrations/021_phase5_analytics_foundation.sql']}\n"
        f"-- Decoded {escaped_newlines} literal \\n sequences in the SQL tail and removed pasted tool invocation/trailer.\n"
        "-- Review and compare before use; the original migration file is never overwritten by this script.\n"
        + repaired_body + "\nCOMMIT;\n"
    )
    # Check the SQL body (not this generator's provenance comment, which describes the literal \\n escape).
    if r"\n" in repaired_body or "text(await tools.mcp__Neon" in repaired_body:
        raise RuntimeError("Migration 021 repaired candidate contains literal escaped newlines or code")

    relative_targets = {
        "migrations/reconstructed/004_catalog_and_rbac_hardening.replay-equivalent.sql": replay004,
        "migrations/reconstructed/021_phase5_analytics_foundation.repair-candidate.sql": replay021,
    }
    outputs: list[Path] = []
    for rel, content in relative_targets.items():
        dst = output_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        outputs.append(dst)
    return outputs


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    created = build_candidates(args.source_root.resolve(), args.output_root.resolve())
    print("Created replay-only candidates; no SQL executed:")
    for path in created:
        print(f"- {path.relative_to(args.output_root.resolve())}")
