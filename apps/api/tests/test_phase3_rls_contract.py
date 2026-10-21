from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api"
MIGRATION = ROOT / "migrations" / "031_phase3_auth_surface_rls.sql"


def test_login_and_registration_set_scoped_pretenant_access_before_reads():
    source = (API / "app" / "routes" / "auth.py").read_text(encoding="utf-8")
    register = source.index("def register(")
    login = source.index("def login(")
    registration_flag = source.index("set_config('app.pre_tenant_access', 'registration', true)", register)
    registration_insert = source.index("insert(RegistrationRequest)", register)
    login_flag = source.index("set_config('app.pre_tenant_access', 'login', true)", login)
    login_user_read = source.index("select(User).where(User.email == email)", login)
    login_clear = source.index("set_config('app.pre_tenant_access', '', true)", login)
    assert registration_flag < registration_insert
    assert login_flag < login_user_read < login_clear


def test_login_persists_tenant_context_across_commit_boundary():
    source = (API / "app" / "routes" / "auth.py").read_text(encoding="utf-8")
    login = source[source.index("def login("):source.index('@router.get("/me")')]
    assert 'db.info["lexa_tenant_id"] = str(tenant_id)' in login
    assert 'db.info["lexa_user_id"] = str(user.id)' in login
    assert "db.commit()" in login
    assert "tenant = db.get(Tenant, tenant_id)" in login


def test_phase3_migration_forces_rls_on_all_five_remaining_surfaces():
    sql = MIGRATION.read_text(encoding="utf-8")
    for table in ("permissions", "schema_migrations", "users", "tenants", "registration_requests"):
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in sql
    assert "REVOKE DELETE ON public.registration_requests FROM lexa_app" in sql
    assert "VALUES ('031_phase3_auth_surface_rls')" in sql
    assert "app.pre_tenant_email" in sql
    assert "app.registration_key" in sql


def test_root_021_source_is_valid_sql_not_escaped_script_text():
    source = (ROOT / "migrations" / "021_phase5_analytics_foundation.sql").read_text(encoding="utf-8")
    assert "\\nCOMMIT" not in source
    assert "text(await tools.mcp__Neon__run_sql" not in source
    assert source.rstrip().endswith("ON CONFLICT(version) DO NOTHING;")
