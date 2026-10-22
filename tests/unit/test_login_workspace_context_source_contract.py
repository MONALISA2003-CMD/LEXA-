from pathlib import Path

ROOT = Path(__file__).parents[2]
AUTH = ROOT / "apps/api/app/routes/auth.py"
WEB_API = ROOT / "apps/web/lib/api.ts"


def test_login_sets_user_context_before_loading_active_workspaces():
    source = AUTH.read_text()
    login = source.split('@router.post("/login")', 1)[1].split('@router.get("/me")', 1)[0]

    pre_tenant_context = login.index("set_config('app.pre_tenant_access', 'login', true)")
    user_lookup = login.index("user = db.scalar(select(User).where(User.email == email))")
    password_check = login.index("verify_password(body.password, user.password_hash)")
    user_context = login.index("set_config('app.user_id', :user_id, true)")
    workspace_lookup = login.index("lexa_list_active_user_workspaces(:user_id)")
    assert pre_tenant_context < user_lookup < password_check < user_context < workspace_lookup
    assert "set_config('app.pre_tenant_email', :email, true)" in login
    assert "set_config('app.pre_tenant_access', '', true)" in login
    assert "set_config('app.pre_tenant_email', '', true)" in login
    assert "set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)" in login


def test_login_distinguishes_missing_workspace_from_wrong_password():
    source = AUTH.read_text()
    login = source.split('@router.post("/login")', 1)[1].split('@router.get("/me")', 1)[0]
    assert '"code": "NO_ACTIVE_WORKSPACE"' in login
    assert '"message": "This account has no active workspace.' in login

    web_api = WEB_API.read_text()
    assert 'if (code === "NO_ACTIVE_WORKSPACE")' in web_api
    assert 'We couldn\'t sign you in. Check your email and password, then try again.' in web_api
