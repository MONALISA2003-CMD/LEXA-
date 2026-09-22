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


def test_phase2_business_engine_api_surface_exists():
    source = (ROOT / "apps/api/app/routes/business_engine.py").read_text()
    for marker in [
        '@router.get("/capabilities")', '@router.put("/capabilities/{code}")',
        '@router.get("/configuration")', '@router.put("/configuration/{key}")',
        '@router.post("/relationships", status_code=201)', '@router.get("/transaction-types")',
        '@router.post("/transactions", status_code=201)', '@router.post("/transactions/{transaction_id}/transition")',
        '@router.post("/workflows/definitions", status_code=201)', '@router.post("/workflows/instances", status_code=201)',
        '@router.post("/workflows/instances/{instance_id}/advance")', '@router.get("/context/{entity_type}/{entity_id}", response_model=ContextOut)',
    ]:
        assert marker in source


def test_phase2_business_engine_permissions_are_explicit():
    source = (ROOT / "migrations/013_phase2_universal_business_engine.sql").read_text()
    for code in ["business.read","business.manage","transactions.read","transactions.manage","workflows.read","workflows.manage","context.read"]:
        assert f"('{code}'" in source


def test_business_engine_is_registered_with_api():
    source = (ROOT / "apps/api/app/main.py").read_text()
    assert "business_engine" in source
    assert "app.include_router(business_engine.router" in source


def test_frontend_business_engine_surface_exists():
    page = (ROOT / "apps/web/app/business-engine/page.tsx").read_text()
    api = (ROOT / "apps/web/lib/api.ts").read_text()
    assert "Universal business engine" in page
    for marker in ["getBusinessCapabilities", "createBusinessTransaction", "createWorkflowDefinition", "getBusinessContext"]:
        assert marker in api
