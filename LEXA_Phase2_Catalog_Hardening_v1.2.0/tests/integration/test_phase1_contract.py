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


def test_phase1_security_migration_exists():
    migration = (ROOT / "migrations/006_phase1_security_reliability.sql").read_text()
    for token in ("outbox_events", "event_consumptions", "idempotency_records", "FORCE ROW LEVEL SECURITY", "lexa_app", "audit_logs_append_only"):
        assert token in migration


def test_application_uses_restricted_database_role_when_configured():
    source = (ROOT / "apps/api/app/db.py").read_text()
    assert "SET ROLE" in source
    config = (ROOT / "apps/api/app/config.py").read_text()
    assert "database_app_role" in config
