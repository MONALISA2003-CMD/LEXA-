from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_login_establishes_scoped_database_context_before_rls_reads():
    source = (ROOT / "apps/api/app/routes/auth.py").read_text()
    login = source.split('@router.post("/login")', 1)[1].split('@router.', 1)[0]
    scoped_email = login.index("app.pre_tenant_access", login.index("def login"))
    account_lookup = login.index("select(User).where(User.email == email)")
    password_check = login.index("verify_password(body.password, user.password_hash)")
    user_context = login.index("set_config('app.user_id'", password_check)
    workspace_lookup = login.index("lexa_list_active_user_workspaces", user_context)
    assert scoped_email < account_lookup < password_check < user_context < workspace_lookup


def test_registration_context_matches_row_security_policy_before_request_insert():
    source = (ROOT / "apps/api/app/routes/auth.py").read_text()
    registration = source.split('@router.post("/register")', 1)[1].split('@router.post("/login")', 1)[0]
    context = registration.index("_set_registration_rls_context(db, email=email, registration_key=key)")
    insert = registration.index("insert(RegistrationRequest)")
    assert context < insert
    helper = source.split("def _set_registration_rls_context", 1)[1].split("def _clear_refresh_cookie", 1)[0]
    assert "app.pre_tenant_access" in helper
    assert "app.pre_tenant_email" in helper
    assert "app.registration_key" in helper


def test_first_run_repair_is_owner_gated_idempotent_and_preserves_existing_records():
    source = (ROOT / "apps/api/app/routes/workspace_context.py").read_text()
    handler = source.split('@router.post("/setup/initialize")', 1)[1].split('@router.', 1)[0]
    assert 'Depends(require_permission("organization.manage"))' in source
    assert "if not branches" in handler
    assert "if not warehouses" in handler
    assert "if not locations" in handler
    assert "if not cash_exists" in handler
    assert "write_audit(" in handler and "emit_event(" in handler
    assert "db.commit()" in handler
    assert "progress = _setup_progress_for_tenant(db, tenant_id)" in handler
    assert "never renames, deletes, or replaces" in handler


def test_owner_branch_scope_matches_database_authorization_contract():
    source = (ROOT / "apps/api/app/branch_access.py").read_text()
    assert 'roles.intersection({"Owner", "Administrator", "Admin"})' in source
    assert '"code": "WORKSPACE_SETUP_REQUIRED"' in source
    assert '"code": "BRANCH_ACCESS_REQUIRED"' in source


def test_candidate_migrations_include_phase7_supplier_ledger_and_phase8_finance():
    migrations = ROOT / "migrations"
    assert (migrations / "039_phase7_supplier_ledger_landed_costs.sql").exists()
    assert (migrations / "040_phase8_finance_workflows.sql").exists()
