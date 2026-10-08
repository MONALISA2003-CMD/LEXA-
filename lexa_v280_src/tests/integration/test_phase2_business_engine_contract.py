from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_phase2_universal_business_engine_migration_is_additive_and_tenant_scoped():
    source = (ROOT / "migrations/013_phase2_universal_business_engine.sql").read_text()
    for table in [
        "business_capabilities", "business_configurations", "party_relationships", "transaction_types",
        "transaction_lines", "transaction_status_history", "workflow_definitions", "workflow_steps",
        "workflow_instances", "workflow_step_runs",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "transaction_lines_tenant_variant_fk" in source
    assert "transaction_lines_tenant_service_fk" in source
    assert "workflow_steps_tenant_definition_fk" in source
    assert "lexa_prevent_transaction_status_history_mutation" in source
    assert "REVOKE UPDATE, DELETE ON transaction_status_history" in source
    assert "DROP TABLE" not in source
    assert "TRUNCATE" not in source
    assert "DELETE FROM" not in source


def test_phase2_business_engine_is_internal_not_user_module():
    source = (ROOT / "apps/api/app/main.py").read_text()
    assert "business_engine" not in source
    assert not (ROOT / "apps/web/app/business-engine/page.tsx").exists()


def test_phase2_business_engine_permissions_are_explicit():
    source = (ROOT / "migrations/013_phase2_universal_business_engine.sql").read_text()
    for code in ["business.read","business.manage","transactions.read","transactions.manage","workflows.read","workflows.manage","context.read"]:
        assert f"('{code}'" in source


def test_business_engine_route_is_not_registered():
    source = (ROOT / "apps/api/app/main.py").read_text()
    assert "include_router(business_engine.router" not in source


def test_business_engine_frontend_surface_is_removed():
    assert not (ROOT / "apps/web/app/business-engine/page.tsx").exists()
    api = (ROOT / "apps/web/lib/api.ts").read_text()
    assert "/api/v1/business-engine/" not in api
