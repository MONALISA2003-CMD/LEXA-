from pathlib import Path

ROOT = Path(__file__).parents[2]

def test_required_migrations_exist():
    assert (ROOT / "migrations/001_phase1_foundation.sql").exists()
    assert (ROOT / "migrations/002_identity_rbac_organization.sql").exists()
    assert (ROOT / "migrations/003_rbac_sessions_organization_completion.sql").exists()

def test_required_routes_exist():
    assert (ROOT / "apps/api/app/routes/auth.py").exists()
    assert (ROOT / "apps/api/app/routes/organization.py").exists()
    assert (ROOT / "apps/api/app/routes/rbac.py").exists()
