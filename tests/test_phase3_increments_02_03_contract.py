from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "overrides/apps/api/app/routes/workspace_context.py"
MEMBERS = ROOT / "overrides/apps/api/app/routes/membership_admin.py"
MIGRATION = ROOT / "overrides/migrations/027_phase3_workspace_memberships.sql"
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
    assert "FOREIGN KEY (membership_id, tenant_id)" in source
    assert "FOREIGN KEY (branch_id, tenant_id)" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "lexa_find_workspace_invitation" in source
    assert "lexa_list_active_user_workspaces" in source
    assert "only established Owner roles receive member management" in source
    assert "Do not execute until historical migrations" in source


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
