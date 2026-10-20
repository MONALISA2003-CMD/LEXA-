from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "overrides/apps/api/app/routes/workspace_context.py"
MEMBERS = ROOT / "overrides/apps/api/app/routes/membership_admin.py"
MIGRATION = ROOT / "overrides/migrations/030_phase3_workspace_memberships.sql"
API_TS = ROOT / "overrides/apps/web/lib/api.phase3-increments-02-03.append.ts.txt"


def test_workspace_switch_checks_active_server_side_membership_list():
    source = API.read_text()
    assert "lexa_list_active_user_workspaces" in source
    assert 'raise HTTPException(status_code=403, detail="You do not have an active membership in that workspace")' in source
    assert 'Tenant.status == "ACTIVE"' in source


def test_switch_revokes_old_session_before_switching_tenant_rls_context():
    source = API.read_text()
    assert source.index("old_session.revoked_at = now") < source.index('set_config(\'app.tenant_id\', :tenant_id, true)', source.index("old_session.revoked_at = now"))
    assert "db.flush()" in source[source.index("old_session.revoked_at = now"):source.index("refresh = new_refresh_token()")]


def test_setup_progress_is_derived_from_saved_configuration_not_shadow_state():
    source = API.read_text()
    assert "BusinessProfile" in source and "Warehouse" in source and "Location" in source and "Branch" in source
    assert "setup_progress(" in source
    assert "tenant.setup_completed" not in source
    assert "Warehouse.status == \"ACTIVE\"" in source
    assert "Location.warehouse_id == Warehouse.id" in source


def test_membership_mutation_is_tenant_scoped_and_revokes_sessions():
    source = MEMBERS.read_text()
    assert "TenantMembership.tenant_id == tenant_id" in source
    assert "UPDATE sessions SET revoked_at = now()" in source
    assert "_active_owner_count(db, tenant_id) <= 1" in source
    assert "pg_advisory_xact_lock" in source
    assert "permission_dependency = require_permission(permission_code)" in source
    assert 'Depends(require_active_workspace_permission("members.manage"))' in source


def test_branch_assignment_rejects_foreign_or_inactive_branches():
    source = MEMBERS.read_text()
    assert "Branch.tenant_id == tenant_id" in source
    assert "Branch.status == \"ACTIVE\"" in source
    assert "membership_branch_assignments" not in source or "MembershipBranchAssignment" in source


def test_invitation_token_is_not_persisted_or_written_to_outbox_payloads():
    source = MEMBERS.read_text()
    assert "token_hash=invitation_token_digest(token)" in source
    assert '"invite_url": "/invite#token=" + quote(token)' in source
    assert '@invitations_router.post("/preview")' in source
    assert 'def invitation_preview(body: InvitationPreviewIn' in source
    assert 'payload={"invitation_id": str(row.id), "email": email' in source
    assert '"token": token' not in source
    assert "finish_idempotency(db, idem, status_code=201, response_body=stored_response" in source


def test_invitation_acceptance_checks_hash_expiry_status_and_invited_account():
    source = MEMBERS.read_text()
    assert "lexa_find_workspace_invitation(:token_hash)" in source
    assert "WorkspaceInvitation.token_hash == token_hash" in source
    assert "invitation_is_expired(invitation.expires_at)" in source
    assert "verify_password(body.password, user.password_hash)" in source
    assert "invitation.status = \"ACCEPTED\"" in source


def test_migration_has_composite_tenant_integrity_and_rls():
    source = MIGRATION.read_text()
    assert "ALTER TABLE public.tenant_invitations ADD COLUMN IF NOT EXISTS branch_ids" in source
    assert "ALTER TABLE public.membership_branch_assignments ADD COLUMN IF NOT EXISTS status" in source
    assert "FOREIGN KEY (membership_id, tenant_id)" not in source  # existing migration 023 owns this contract
    assert "workspace_invitations" not in source  # reuse existing migration-023 table
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "lexa_find_workspace_invitation" in source
    assert "lexa_list_active_user_workspaces" in source
    assert "lower(r.name)='owner'" in source
    assert "complete Phase 0–2 migration chain" in source


def test_frontend_exposes_workspaces_members_invitations_and_setup_contracts():
    source = API_TS.read_text()
    for name in ["getWorkspaceOptions", "selectWorkspace", "getSetupProgress", "getWorkspaceMembers", "createWorkspaceInvitation", "acceptWorkspaceInvitation", "replaceWorkspaceMemberBranches"]:
        assert name in source


def test_invitation_refuses_duplicate_membership_in_same_workspace():
    source = MEMBERS.read_text()
    assert "existing_user = db.scalar(select(User).where(func.lower(User.email) == email))" in source
    assert "This account already has a membership in the invited workspace" in source


def test_public_invitation_preview_and_accept_reject_suspended_tenants():
    source = MEMBERS.read_text()
    assert 'select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "ACTIVE")' in source
    assert 'raise HTTPException(status_code=404, detail="Invitation is invalid or expired")' in source


def test_member_and_invitation_admin_require_active_workspace():
    source = MEMBERS.read_text()
    assert "def require_active_workspace_permission(permission_code: str)" in source
    assert 'Depends(require_active_workspace_permission("members.manage"))' in source
    assert 'Depends(require_active_workspace_permission("members.read"))' in source


def test_invitation_replay_never_returns_old_bearer_and_expired_can_be_resent():
    source = MEMBERS.read_text()
    assert '"invite_url": None, "replayed": True' in source
    assert 'row.status not in ("PENDING", "EXPIRED")' in source
    assert 'Only a pending or expired invitation can be resent' in source


def test_invitation_user_matching_is_case_insensitive():
    source = MEMBERS.read_text()
    assert source.count("func.lower(User.email) == email") >= 1
    assert "func.lower(User.email) == invitation.email" in source


def test_phase3_migration_reuses_existing_tenant_keys_and_avoids_duplicate_branch_index():
    source = MIGRATION.read_text()
    assert "CREATE UNIQUE INDEX IF NOT EXISTS lexa_030_uq_membership_id_tenant" not in source
    assert "CREATE UNIQUE INDEX IF NOT EXISTS lexa_030_uq_branch_id_tenant" not in source
    assert "CREATE UNIQUE INDEX IF NOT EXISTS lexa_030_uq_role_id_tenant" not in source
    assert "CREATE UNIQUE INDEX IF NOT EXISTS lexa_030_uq_membership_tenant_user" not in source
    assert "FROM pg_indexes" in source and "indexdef ILIKE '%(tenant_id, branch_id, status)%'" in source


def test_phase3_migration_preflights_pending_invitation_data_before_unique_index():
    source = MIGRATION.read_text()
    assert "A live pending invitation has no role" in source
    assert "Duplicate pending invitations exist for the same workspace/email" in source
    assert "GROUP BY tenant_id,lower(email) HAVING count(*)>1" in source
    assert "WHERE status='PENDING'" in source and "lexa_030_uq_invitations_pending_email" in source


def test_member_role_replacement_is_tenant_scoped_audited_and_last_owner_safe():
    source = MEMBERS.read_text()
    assert '@members_router.put("/{membership_id}/roles")' in source
    assert 'Role.tenant_id == tenant_id' in source
    assert 'Only a current workspace owner may grant the Owner role' in source
    assert 'The last active workspace owner cannot lose the Owner role' in source
    assert "pg_advisory_xact_lock(hashtext('lexa:owner:' || :tenant_id))" in source
    assert 'workspace.membership.roles_replaced' in source
    assert 'write_audit(db' in source and 'emit_event(db' in source

def test_member_role_assignment_ui_uses_server_api_and_blocks_empty_role_set():
    page = (ROOT / "overrides/apps/web/app/administration/members/page.tsx").read_text()
    api = API_TS.read_text()
    assert 'replaceWorkspaceMemberRoles' in page
    assert 'Save role assignments' in page
    assert 'selected.length === 0' in page
    assert 'role_ids: roleIds' in api


def test_branch_access_helpers_fail_closed_and_use_active_membership_assignments():
    helper = (ROOT / "overrides/apps/api/app/branch_access.py").read_text()
    assert 'MembershipBranchAssignment.status == "ACTIVE"' in helper
    assert 'Branch.status == "ACTIVE"' in helper
    assert 'Access to this branch has not been assigned' in helper
    assert 'Stock location must be linked to an active branch' in helper
    assert 'require_full_branch_scope' in helper

def test_inventory_core_reads_and_commands_apply_assignment_filters():
    source = (ROOT / "overrides/apps/api/app/routes/inventory.py").read_text()
    assert 'accessible_location_ids' in source
    assert 'ensure_location_access' in source
    assert 'InventoryTransfer.destination_location_id.in_(allowed_locations)' in source
    assert 'require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor)' in source

def test_commerce_sales_returns_and_tenant_wide_day_close_are_branch_guarded():
    source = (ROOT / "overrides/apps/api/app/routes/commerce.py").read_text()
    assert 'ensure_location_access' in source and 'ensure_branch_access' in source
    assert 'membership_branch_assignments mba' in source
    assert 'require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])' in source


def test_role_permission_catalog_is_owner_only_and_owner_role_is_immutable():
    source = MEMBERS.read_text()
    assert '@members_router.get("/role-permissions")' in source
    assert '@members_router.post("/roles", status_code=201)' in source
    assert '@members_router.put("/roles/{role_id}/permissions")' in source
    assert 'Only a workspace owner may manage role permissions' in source
    assert 'The built-in Owner role permission set is protected' in source
    assert 'workspace.role.permissions_replaced' in source
    assert 'role_id' in source and 'permission_ids' in source

def test_role_permission_admin_ui_uses_live_api_and_exposes_protected_owner_role():
    page = (ROOT / "overrides/apps/web/app/administration/members/page.tsx").read_text()
    api = API_TS.read_text()
    for required in ['Roles and permissions', 'Create role', 'Save role permissions', 'getWorkspaceRolePermissionCatalog']:
        assert required in page
    assert 'createWorkspaceRole' in api and 'replaceWorkspaceRolePermissions' in api
    assert 'built-in Owner role is protected' in page


def test_tenant_wide_finance_and_analytics_reports_require_full_branch_assignment():
    finance = (ROOT / "overrides/apps/api/app/routes/finance.py").read_text()
    analytics = (ROOT / "overrides/apps/api/app/routes/analytics.py").read_text()
    assert 'from ..branch_access import require_full_branch_scope' in finance
    assert finance.count('require_full_branch_scope(') >= 15
    assert analytics.count('require_full_branch_scope(') >= 5
    assert 'membership_branch_assignments mba' in analytics
    assert 'a.location_id IN (SELECT loc.id' in analytics
