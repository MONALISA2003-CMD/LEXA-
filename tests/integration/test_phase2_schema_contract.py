from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_phase2_hardening_migration_exists():
    path = ROOT / "migrations/007_phase2_catalog_hardening.sql"
    assert path.exists()
    source = path.read_text()
    for token in [
        "btree_gist",
        "product_prices_no_overlap",
        "lexa_validate_category_parent",
        "lexa_validate_variant_unit",
        "FORCE ROW LEVEL SECURITY",
        "uq_variants_tenant_sku_active",
        "uq_barcodes_tenant_value_active",
    ]:
        assert token in source


def test_phase2_does_not_replace_phase1_outbox_contract():
    source = (ROOT / "migrations/007_phase2_catalog_hardening.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS outbox_events" not in source
    assert "actor_user_id" not in source


def test_phase2_schema_has_database_level_price_overlap_protection():
    source = (ROOT / "migrations/007_phase2_catalog_hardening.sql").read_text()
    assert "EXCLUDE USING gist" in source
    assert "minimum_quantity WITH =" in source
    assert "tstzrange(effective_from, effective_to, '[)') WITH &&" in source


def test_phase2_identity_tenancy_authorization_migration_contract():
    path = ROOT / "migrations/023_phase2_identity_tenancy_authorization_foundation.sql"
    assert path.exists()
    source = path.read_text()
    for token in [
        "display_name", "tenant_settings", "membership_branch_assignments", "tenant_invitations",
        "user_security_tokens", "tenant.settings.manage", "users.invite", "branches.assign",
        "users.sessions.revoke", "lexa_can_access_branch", "lexa_get_invitation_by_token",
        "FORCE ROW LEVEL SECURITY", "ON DELETE CASCADE",
    ]:
        assert token in source
    assert "DROP TABLE" not in source.upper()
    assert "TRUNCATE" not in source.upper()
    assert "DELETE FROM" not in source.upper()
    assert source.index("uq_tenant_memberships_tenant_id") < source.index("CREATE TABLE IF NOT EXISTS membership_branch_assignments")


def test_phase2_identity_models_and_routes_are_present():
    models = (ROOT / "apps/api/app/models.py").read_text()
    auth = (ROOT / "apps/api/app/routes/auth.py").read_text()
    rbac = (ROOT / "apps/api/app/routes/rbac.py").read_text()
    organization = (ROOT / "apps/api/app/routes/organization.py").read_text()
    dependencies = (ROOT / "apps/api/app/dependencies.py").read_text()
    for token in ["TenantSettings", "MembershipBranchAssignment", "TenantInvitation", "UserSecurityToken"]:
        assert token in models
    for token in ['@router.get("/me")', '@router.get("/sessions")', '@router.post("/sessions/{session_id}/revoke")', '@router.post("/invitations/accept")']:
        assert token in auth
    for token in ['@router.get("/members")', '@router.patch("/members/{membership_id}")', '@router.post("/branch-assignments")', '@router.post("/invitations")']:
        assert token in rbac
    assert '@router.put("/settings"' in organization
    assert 'X-LEXA-Branch-ID' in dependencies
    assert 'app.user_id' in dependencies


def test_phase2_cors_allows_branch_context_header():
    source = (ROOT / "apps/api/app/main.py").read_text()
    assert '"X-LEXA-Branch-ID"' in source


def test_phase2_branch_rls_is_assignment_aware():
    source = (ROOT / "migrations/023_phase2_identity_tenancy_authorization_foundation.sql").read_text()
    for table in ["branches", "warehouses", "pos_terminals", "business_transactions", "price_contexts", "sales", "analytics_branch_daily_metrics"]:
        marker = f"CREATE POLICY {table}_tenant_isolation" if table != "analytics_branch_daily_metrics" else "CREATE POLICY analytics_branch_daily_metrics_tenant_isolation"
        assert marker in source
    assert "membership_branch_assignments" in source
    assert "public.lexa_can_access_branch" in source
    assert "Owner', 'Administrator', 'Manager" in source


def test_phase2_frontend_administration_surfaces_are_present_and_kernel_is_not_user_surface():
    admin = ROOT / "apps/web/app/administration/page.tsx"
    invite = ROOT / "apps/web/app/invite/page.tsx"
    settings = ROOT / "apps/web/app/settings/page.tsx"
    home = ROOT / "apps/web/app/page.tsx"
    assert admin.exists() and invite.exists() and settings.exists()
    home_source = home.read_text()
    admin_source = admin.read_text()
    for token in ["getMe", "getRbacMembers", "createRbacInvitation", "assignMemberBranch", "getOrganizationSettings", "getAuthSessions"]:
        assert token in admin_source
    assert 'href="/administration"' in home_source
    assert 'href="/kernel"' not in home_source
    assert '/business-engine' not in home_source
