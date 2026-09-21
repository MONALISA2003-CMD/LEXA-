from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_phase1_kernel_migration_is_additive_and_tenant_scoped():
    sql = (ROOT / "migrations" / "012_phase1_business_kernel.sql").read_text()
    for table in [
        "parties", "party_roles", "services", "resources", "assets", "documents",
        "business_transactions", "payments", "tasks", "business_cases",
        "business_projects", "contracts",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert 'ENABLE ROW LEVEL SECURITY' in sql
    assert 'FORCE ROW LEVEL SECURITY' in sql
    assert 'CREATE POLICY parties_tenant_isolation' in sql
    assert 'CREATE POLICY contracts_tenant_isolation' in sql
    assert "DROP TABLE" not in sql
    assert "TRUNCATE" not in sql
    assert "DELETE FROM" not in sql


def test_kernel_api_surface_exists():
    text = (ROOT / "apps/api/app/kernel.py").read_text()
    for marker in [
        '@router.get("/summary")',
        '@router.post("/parties"',
        '@router.post("/services"',
        '@router.post("/resources"',
        '@router.post("/assets"',
        '@router.post("/documents"',
        '@router.post("/transactions"',
        '@router.post("/payments"',
        '@router.post("/tasks"',
        '@router.post("/cases"',
        '@router.post("/projects"',
        '@router.post("/contracts"',
    ]:
        assert marker in text


def test_canonical_neon_guard_remains_in_configuration():
    config = (ROOT / "apps/api/app/config.py").read_text()
    assert 'lexa_neon_project_id: str = "wispy-mud-75323042"' in config
    assert 'lexa_neon_branch_id: str = "br-soft-star-b1dj2m2w"' in config
