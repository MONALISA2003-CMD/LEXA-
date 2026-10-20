from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_phase0_3_replay_candidates.py"
SPEC = importlib.util.spec_from_file_location("build_phase0_3_replay_candidates", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _sources(root: Path) -> tuple[bytes, bytes]:
    migration004 = (
        "-- synthetic 004 source fixture\n"
        "CREATE TABLE products(id uuid PRIMARY KEY);\n"
        "ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_category_tenant;\n"
        "ALTER TABLE products ADD CONSTRAINT fk_products_category_tenant "
        "FOREIGN KEY (tenant_id, category_id) REFERENCES categories(tenant_id,id);\n"
    ).encode()
    # The literal backslash-n sequences simulate the malformed stored tail.
    tail = (
        r"\n\nALTER TABLE analytics_refresh_runs ENABLE ROW LEVEL SECURITY;"
        r"\nALTER TABLE analytics_refresh_runs FORCE ROW LEVEL SECURITY;"
        r"\nCREATE INDEX IF NOT EXISTS ix_analytics_refresh_tenant ON analytics_refresh_runs(tenant_id);"
        r"\nDROP POLICY IF EXISTS analytics_refresh_runs_tenant ON analytics_refresh_runs;"
        r"\nCREATE POLICY analytics_refresh_runs_tenant ON analytics_refresh_runs USING (true) WITH CHECK (true);"
        r"\nINSERT INTO schema_migrations(version) VALUES('021_phase5_analytics_foundation') ON CONFLICT(version) DO NOTHING;"
        r"\nCOMMIT;\nCOMMIT;\n"
    )
    migration021 = (
        "BEGIN;\n-- synthetic function body was already terminated above in the real source\nEND $fn$;" + tail +
        "`; // outer transaction handled by PostgreSQL statement parser\n"
        "text(await tools.mcp__Neon__run_sql({sql,project_id:p,branch_id:b,database_name:d}));\n"
        ".unregister; \n krwar=1;\n"
    ).encode()
    for rel, data in [
        ("migrations/004_catalog_and_rbac_hardening.sql", migration004),
        ("migrations/021_phase5_analytics_foundation.sql", migration021),
    ]:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return migration004, migration021


def test_builder_emits_separately_labelled_replay_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source_root = tmp_path / "source"
    output_root = tmp_path / "output"
    source_root.mkdir()
    source004, source021 = _sources(source_root)
    monkeypatch.setattr(builder, "EXPECTED", {
        "migrations/004_catalog_and_rbac_hardening.sql": _git_blob_sha(source004),
        "migrations/021_phase5_analytics_foundation.sql": _git_blob_sha(source021),
    })

    created = builder.build_candidates(source_root, output_root)
    assert len(created) == 2
    out004 = (output_root / "migrations/reconstructed/004_catalog_and_rbac_hardening.replay-equivalent.sql").read_text()
    out021 = (output_root / "migrations/reconstructed/021_phase5_analytics_foundation.repair-candidate.sql").read_text()
    anchor = out004.index("ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_category_tenant;")
    assert out004.index("uq_brands_tenant_id") < anchor
    assert "REPLAY-ONLY EQUIVALENT, NOT THE HISTORICAL 004 SOURCE BYTES" in out004
    assert "RECONSTRUCTED REPAIR CANDIDATE, NOT HISTORICAL ORIGINAL BYTES" in out021
    assert "ALTER TABLE analytics_refresh_runs ENABLE ROW LEVEL SECURITY;\nALTER TABLE analytics_refresh_runs FORCE ROW LEVEL SECURITY;" in out021
    assert "INSERT INTO schema_migrations(version)" in out021
    assert r"\n\nALTER TABLE" not in out021
    assert "tools.mcp__Neon" not in out021 and ".unregister;" not in out021
    # Builder never overwrites the original malformed input paths.
    assert (source_root / "migrations/004_catalog_and_rbac_hardening.sql").read_bytes() == source004
    assert (source_root / "migrations/021_phase5_analytics_foundation.sql").read_bytes() == source021


def test_builder_refuses_mutated_source_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    source004, source021 = _sources(source_root)
    monkeypatch.setattr(builder, "EXPECTED", {
        "migrations/004_catalog_and_rbac_hardening.sql": _git_blob_sha(source004),
        "migrations/021_phase5_analytics_foundation.sql": _git_blob_sha(source021),
    })
    (source_root / "migrations/004_catalog_and_rbac_hardening.sql").write_text("-- modified after pin\n")
    with pytest.raises(RuntimeError, match="Source provenance guard failed"):
        builder.build_candidates(source_root, tmp_path / "output")


def test_025a_replay_step_promotes_assignment_id_before_026_and_drops_temp_index():
    replay = (ROOT / "overrides/migrations/reconstructed/025a_phase2_membership_branch_contract_reconciliation.replay-only.sql").read_text()
    assert "PRIMARY KEY(id)" in replay
    assert "DROP INDEX IF EXISTS public.lexa_phase2_uq_membership_branch_assignment_id" in replay
    assert "CREATE INDEX IF NOT EXISTS idx_mba_tenant_branch" in replay
    assert "NOT A HISTORICAL MIGRATION" in replay
