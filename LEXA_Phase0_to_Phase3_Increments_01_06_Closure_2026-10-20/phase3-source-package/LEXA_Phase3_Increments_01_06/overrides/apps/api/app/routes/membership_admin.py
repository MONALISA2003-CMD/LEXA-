"""Tenant-scoped memberships, one-time invitations and branch assignments."""
from datetime import datetime, timedelta, timezone
import secrets
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, text, delete, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password, verify_password, new_refresh_token, hash_refresh_token, _set_refresh_cookie
from ..catalog import begin_idempotency, emit_event, finish_idempotency, write_audit
from ..catalog_rules import CatalogValidation
from ..config import settings
from ..dependencies import get_db, require_permission
from ..models import (
    Branch, MembershipRole, Permission, Role, RolePermission,
    Session as AuthSession, Tenant, TenantMembership, User,
)
from ..workspace_domain import invitation_is_expired, invitation_token_digest, normalize_branch_ids
from ..workspace_models import MembershipBranchAssignment, WorkspaceInvitation

members_router = APIRouter(prefix="/members", tags=["memberships"])
invitations_router = APIRouter(prefix="/invitations", tags=["workspace invitations"])


def require_active_workspace_permission(permission_code: str):
    permission_dependency = require_permission(permission_code)

    def dependency(ctx=Depends(permission_dependency)):
        db, _actor_id, tenant_id, _session_id = ctx
        tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "ACTIVE"))
        if not tenant:
            raise HTTPException(status_code=403, detail="This workspace is not active")
        return ctx

    return dependency


class InvitationCreateIn(BaseModel):
    email: EmailStr
    role_id: UUID
    branch_ids: list[UUID] = Field(default_factory=list, max_length=250)
    expires_in_days: int = Field(default=7, ge=1, le=30)


class MemberStatusIn(BaseModel):
    status: Literal["ACTIVE", "INACTIVE"]


class BranchAssignmentsIn(BaseModel):
    branch_ids: list[UUID] = Field(default_factory=list, max_length=250)


class MemberRolesIn(BaseModel):
    # Empty role sets lock the user out and are not accepted here. Deactivate instead.
    role_ids: list[UUID] = Field(min_length=1, max_length=50)


class WorkspaceRoleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class WorkspaceRolePermissionsIn(BaseModel):
    permission_ids: list[UUID] = Field(default_factory=list, max_length=300)


class InvitationPreviewIn(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class InvitationAcceptIn(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=12, max_length=256)


def _invitation_summary(row: WorkspaceInvitation) -> dict:
    displayed_status = "EXPIRED" if row.status == "PENDING" and invitation_is_expired(row.expires_at) else row.status
    return {
        "id": str(row.id), "email": row.email, "status": displayed_status,
        "role_id": str(row.role_id) if row.role_id else None, "branch_ids": [str(x) for x in (row.branch_ids or [])],
        "expires_at": row.expires_at.isoformat(), "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _validate_role_and_branches(db: Session, *, tenant_id: UUID, role_id: UUID, branch_ids: list[UUID]):
    role = db.scalar(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id))
    if not role:
        raise HTTPException(status_code=400, detail="Role must belong to the current workspace")
    unique_ids = list(dict.fromkeys(branch_ids))
    if unique_ids:
        rows = db.scalars(select(Branch.id).where(
            Branch.tenant_id == tenant_id, Branch.status == "ACTIVE", Branch.id.in_(unique_ids)
        )).all()
        if {str(item) for item in rows} != {str(item) for item in unique_ids}:
            raise HTTPException(status_code=400, detail="Every assigned branch must be active and belong to the current workspace")
    return role, unique_ids


def _actor_is_owner(db: Session, *, tenant_id: UUID, actor_id: UUID) -> bool:
    return bool(db.execute(text("""
        SELECT 1 FROM tenant_memberships tm
        JOIN membership_roles mr ON mr.membership_id = tm.id
        JOIN roles r ON r.id = mr.role_id AND r.tenant_id = tm.tenant_id
        WHERE tm.tenant_id = :tenant_id AND tm.user_id = :actor_id
          AND tm.status = 'ACTIVE' AND lower(r.name) = 'owner'
        LIMIT 1
    """), {"tenant_id": str(tenant_id), "actor_id": str(actor_id)}).first())


def _target_is_owner(db: Session, membership_id: UUID) -> bool:
    return bool(db.execute(text("""
        SELECT 1 FROM membership_roles mr JOIN roles r ON r.id = mr.role_id
        WHERE mr.membership_id = :membership_id AND lower(r.name) = 'owner' LIMIT 1
    """), {"membership_id": str(membership_id)}).first())


def _active_owner_count(db: Session, tenant_id: UUID) -> int:
    return int(db.scalar(text("""
        SELECT count(DISTINCT tm.id) FROM tenant_memberships tm
        JOIN membership_roles mr ON mr.membership_id = tm.id
        JOIN roles r ON r.id = mr.role_id AND r.tenant_id = tm.tenant_id
        WHERE tm.tenant_id = :tenant_id AND tm.status = 'ACTIVE' AND lower(r.name) = 'owner'
    """), {"tenant_id": str(tenant_id)}) or 0)


def _create_invitation(db: Session, *, tenant_id: UUID, actor_id: UUID, email: str, role_id: UUID,
                       branch_ids: list[UUID], expires_in_days: int, request_id: str | None) -> tuple[WorkspaceInvitation, str]:
    role, unique_branches = _validate_role_and_branches(db, tenant_id=tenant_id, role_id=role_id, branch_ids=branch_ids)
    if role.name.strip().lower() == "owner" and not _actor_is_owner(db, tenant_id=tenant_id, actor_id=actor_id):
        raise HTTPException(status_code=403, detail="Only a current workspace owner may invite another owner")
    email = email.strip().lower()
    existing_user = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing_user and db.scalar(select(TenantMembership.id).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.user_id == existing_user.id,
    ).limit(1)):
        raise HTTPException(status_code=409, detail="This account already has a membership in the invited workspace; reactivate it if needed")
    now = datetime.now(timezone.utc)
    stale = db.scalars(select(WorkspaceInvitation).where(
        WorkspaceInvitation.tenant_id == tenant_id,
        WorkspaceInvitation.email == email,
        WorkspaceInvitation.status == "PENDING",
        WorkspaceInvitation.expires_at <= now,
    ).with_for_update()).all()
    for old in stale:
        old.status = "EXPIRED"
    existing = db.scalar(select(WorkspaceInvitation.id).where(
        WorkspaceInvitation.tenant_id == tenant_id,
        WorkspaceInvitation.email == email,
        WorkspaceInvitation.status == "PENDING",
        WorkspaceInvitation.expires_at > now,
    ).limit(1))
    if existing:
        raise HTTPException(status_code=409, detail="A pending invitation already exists. Revoke it or resend it.")

    token = secrets.token_urlsafe(32)
    row = WorkspaceInvitation(
        tenant_id=tenant_id, email=email, token_hash=invitation_token_digest(token), status="PENDING",
        invited_by_user_id=actor_id, role_id=role.id, branch_ids=[str(item) for item in unique_branches],
        expires_at=now + timedelta(days=expires_in_days),
    )
    db.add(row)
    db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="workspace.invitation.create",
                target_type="workspace_invitation", target_id=row.id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type="workspace.invitation.created", aggregate_type="workspace_invitation",
               aggregate_id=row.id, actor_user_id=actor_id,
               payload={"invitation_id": str(row.id), "email": email, "role_id": str(role.id),
                        "branch_ids": [str(item) for item in unique_branches], "expires_at": row.expires_at.isoformat()},
               correlation_id=request_id)
    return row, token


@members_router.get("")
def list_members(ctx=Depends(require_active_workspace_permission("members.read"))):
    db, _actor_id, tenant_id, _session_id = ctx
    memberships = db.execute(
        select(TenantMembership, User.email).join(User, User.id == TenantMembership.user_id)
        .where(TenantMembership.tenant_id == tenant_id).order_by(User.email)
    ).all()
    result = []
    for membership, email in memberships:
        roles = db.execute(text("""
            SELECT r.id, r.name FROM membership_roles mr JOIN roles r ON r.id = mr.role_id
            WHERE mr.membership_id = :membership_id AND r.tenant_id = :tenant_id ORDER BY r.name
        """), {"membership_id": str(membership.id), "tenant_id": str(tenant_id)}).mappings().all()
        branches = db.scalars(select(MembershipBranchAssignment.branch_id).where(
            MembershipBranchAssignment.membership_id == membership.id,
            MembershipBranchAssignment.tenant_id == tenant_id,
            MembershipBranchAssignment.status == "ACTIVE",
        )).all()
        result.append({
            "id": str(membership.id), "user_id": str(membership.user_id), "email": email,
            "status": membership.status,
            "roles": [{"id": str(role["id"]), "name": role["name"]} for role in roles],
            "branch_ids": [str(branch) for branch in branches],
        })
    return {"items": result}


@members_router.patch("/{membership_id}")
def update_member_status(membership_id: UUID, body: MemberStatusIn, request: Request,
                         ctx=Depends(require_active_workspace_permission("members.manage"))):
    db, actor_id, tenant_id, _session_id = ctx
    # Serialize owner removals per tenant so concurrent requests cannot each observe two owners and remove both.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('lexa:owner:' || :tenant_id))"), {"tenant_id": str(tenant_id)})
    target = db.scalar(select(TenantMembership).where(
        TenantMembership.id == membership_id, TenantMembership.tenant_id == tenant_id
    ).with_for_update())
    if not target:
        raise HTTPException(status_code=404, detail="Membership not found")
    if target.status == body.status:
        return {"id": str(target.id), "status": target.status, "changed": False}
    if body.status == "INACTIVE" and _target_is_owner(db, target.id) and _active_owner_count(db, tenant_id) <= 1:
        raise HTTPException(status_code=409, detail="The last active workspace owner cannot be deactivated")
    target.status = body.status
    if body.status == "INACTIVE":
        db.execute(text("UPDATE sessions SET revoked_at = now() WHERE tenant_id = :tenant_id AND user_id = :user_id AND revoked_at IS NULL"),
                   {"tenant_id": str(tenant_id), "user_id": str(target.user_id)})
    request_id = getattr(request.state, "request_id", None)
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="workspace.membership.status",
                target_type="tenant_membership", target_id=target.id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type="workspace.membership.status_changed", aggregate_type="tenant_membership",
               aggregate_id=target.id, actor_user_id=actor_id,
               payload={"membership_id": str(target.id), "status": body.status}, correlation_id=request_id)
    db.commit()
    return {"id": str(target.id), "status": target.status, "changed": True}


@members_router.get("/role-permissions")
def list_workspace_role_permissions(ctx=Depends(require_active_workspace_permission("members.manage"))):
    db, actor_id, tenant_id, _session_id = ctx
    if not _actor_is_owner(db, tenant_id=tenant_id, actor_id=actor_id):
        raise HTTPException(status_code=403, detail="Only a workspace owner may manage role permissions")
    roles = list(db.scalars(select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name)))
    permissions = list(db.scalars(select(Permission).order_by(Permission.code)))
    role_items = []
    for role in roles:
        permission_ids = db.scalars(select(RolePermission.permission_id).where(RolePermission.role_id == role.id)).all()
        role_items.append({"id": str(role.id), "tenant_id": str(role.tenant_id), "name": role.name,
                           "description": role.description, "permission_ids": [str(item) for item in permission_ids]})
    return {"roles": role_items,
            "permissions": [{"id": str(item.id), "code": item.code, "description": item.description} for item in permissions]}


@members_router.post("/roles", status_code=201)
def create_workspace_role(body: WorkspaceRoleCreateIn, request: Request,
                          ctx=Depends(require_active_workspace_permission("members.manage"))):
    db, actor_id, tenant_id, _session_id = ctx
    if not _actor_is_owner(db, tenant_id=tenant_id, actor_id=actor_id):
        raise HTTPException(status_code=403, detail="Only a workspace owner may create roles")
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="Role name is required")
    if db.scalar(select(Role.id).where(Role.tenant_id == tenant_id, func.lower(Role.name) == name.lower())):
        raise HTTPException(status_code=409, detail="A role with this name already exists")
    row = Role(tenant_id=tenant_id, name=name, description=body.description.strip() if body.description else None)
    db.add(row)
    try:
        db.flush()
        request_id = getattr(request.state, "request_id", None)
        write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="workspace.role.created",
                    target_type="role", target_id=row.id, correlation_id=request_id)
        emit_event(db, tenant_id=tenant_id, event_type="workspace.role.created", aggregate_type="role",
                   aggregate_id=row.id, actor_user_id=actor_id,
                   payload={"role_id": str(row.id), "name": row.name}, correlation_id=request_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A role with this name already exists") from exc
    return {"id": str(row.id), "tenant_id": str(tenant_id), "name": row.name, "description": row.description}


@members_router.put("/roles/{role_id}/permissions")
def replace_workspace_role_permissions(role_id: UUID, body: WorkspaceRolePermissionsIn, request: Request,
                                       ctx=Depends(require_active_workspace_permission("members.manage"))):
    db, actor_id, tenant_id, _session_id = ctx
    if not _actor_is_owner(db, tenant_id=tenant_id, actor_id=actor_id):
        raise HTTPException(status_code=403, detail="Only a workspace owner may manage role permissions")
    role = db.scalar(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id).with_for_update())
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.name.strip().lower() == "owner":
        raise HTTPException(status_code=409, detail="The built-in Owner role permission set is protected")
    permission_ids = list(dict.fromkeys(body.permission_ids))
    if permission_ids:
        valid = db.scalars(select(Permission.id).where(Permission.id.in_(permission_ids))).all()
        if {str(item) for item in valid} != {str(item) for item in permission_ids}:
            raise HTTPException(status_code=400, detail="Every permission must exist in the system permission catalog")
    old_ids = set(db.scalars(select(RolePermission.permission_id).where(RolePermission.role_id == role.id)).all())
    if old_ids == set(permission_ids):
        db.rollback()
        return {"role_id": str(role.id), "permission_ids": [str(item) for item in permission_ids], "changed": False}
    db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
    for permission_id in permission_ids:
        db.add(RolePermission(role_id=role.id, permission_id=permission_id))
    request_id = getattr(request.state, "request_id", None)
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="workspace.role.permissions_replaced",
                target_type="role", target_id=role.id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type="workspace.role.permissions_replaced", aggregate_type="role",
               aggregate_id=role.id, actor_user_id=actor_id,
               payload={"role_id": str(role.id), "permission_ids": [str(item) for item in permission_ids]}, correlation_id=request_id)
    db.commit()
    return {"role_id": str(role.id), "permission_ids": [str(item) for item in permission_ids], "changed": True}


@members_router.put("/{membership_id}/roles")
def replace_member_roles(membership_id: UUID, body: MemberRolesIn, request: Request,
                         ctx=Depends(require_active_workspace_permission("members.manage"))):
    """Replace a membership's workspace roles atomically with last-owner protection."""
    db, actor_id, tenant_id, _session_id = ctx
    # Share the same tenant lock with deactivation to prevent concurrent last-owner loss.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('lexa:owner:' || :tenant_id))"), {"tenant_id": str(tenant_id)})
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.id == membership_id, TenantMembership.tenant_id == tenant_id
    ).with_for_update())
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Reactivate the membership before changing roles")

    requested_ids = list(dict.fromkeys(body.role_ids))
    roles = list(db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.id.in_(requested_ids))))
    if {str(role.id) for role in roles} != {str(role_id) for role_id in requested_ids}:
        raise HTTPException(status_code=400, detail="Every assigned role must belong to the current workspace")
    requested_owner = any(role.name.strip().lower() == "owner" for role in roles)
    current_owner = _target_is_owner(db, membership.id)
    if requested_owner and not _actor_is_owner(db, tenant_id=tenant_id, actor_id=actor_id):
        raise HTTPException(status_code=403, detail="Only a current workspace owner may grant the Owner role")
    if current_owner and not requested_owner and _active_owner_count(db, tenant_id) <= 1:
        raise HTTPException(status_code=409, detail="The last active workspace owner cannot lose the Owner role")

    old_role_ids = db.scalars(select(MembershipRole.role_id).where(MembershipRole.membership_id == membership.id)).all()
    if set(old_role_ids) == set(requested_ids):
        db.rollback()
        return {"membership_id": str(membership.id), "roles": [{"id": str(role.id), "name": role.name} for role in sorted(roles, key=lambda r: r.name)], "changed": False}

    db.execute(delete(MembershipRole).where(MembershipRole.membership_id == membership.id))
    for role in roles:
        db.add(MembershipRole(membership_id=membership.id, role_id=role.id))
    request_id = getattr(request.state, "request_id", None)
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="workspace.membership.roles_replaced",
                target_type="tenant_membership", target_id=membership.id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type="workspace.membership.roles_replaced", aggregate_type="tenant_membership",
               aggregate_id=membership.id, actor_user_id=actor_id,
               payload={"membership_id": str(membership.id), "role_ids": [str(role.id) for role in roles]}, correlation_id=request_id)
    db.commit()
    return {"membership_id": str(membership.id), "roles": [{"id": str(role.id), "name": role.name} for role in sorted(roles, key=lambda r: r.name)], "changed": True}


@members_router.put("/{membership_id}/branches")
def replace_member_branches(membership_id: UUID, body: BranchAssignmentsIn, request: Request,
                            ctx=Depends(require_active_workspace_permission("members.manage"))):
    db, actor_id, tenant_id, _session_id = ctx
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.id == membership_id, TenantMembership.tenant_id == tenant_id
    ).with_for_update())
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Reactivate the membership before assigning branches")
    # Branch-only validation does not depend on a selected role.
    if body.branch_ids:
        valid = db.scalars(select(Branch.id).where(Branch.tenant_id == tenant_id, Branch.status == "ACTIVE", Branch.id.in_(body.branch_ids))).all()
        if {str(x) for x in valid} != {str(x) for x in body.branch_ids}:
            raise HTTPException(status_code=400, detail="Every assigned branch must be active and belong to the current workspace")
    branch_ids = list(dict.fromkeys(body.branch_ids))
    db.execute(delete(MembershipBranchAssignment).where(
        MembershipBranchAssignment.tenant_id == tenant_id,
        MembershipBranchAssignment.membership_id == membership.id,
    ))
    for branch_id in branch_ids:
        db.add(MembershipBranchAssignment(membership_id=membership.id, branch_id=branch_id,
                                          tenant_id=tenant_id, assigned_by_user_id=actor_id))
    request_id = getattr(request.state, "request_id", None)
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="workspace.membership.branches",
                target_type="tenant_membership", target_id=membership.id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type="workspace.membership.branches_replaced", aggregate_type="tenant_membership",
               aggregate_id=membership.id, actor_user_id=actor_id,
               payload={"membership_id": str(membership.id), "branch_ids": [str(item) for item in branch_ids]}, correlation_id=request_id)
    db.commit()
    return {"membership_id": str(membership.id), "branch_ids": [str(item) for item in branch_ids], "status": "updated"}


@invitations_router.get("")
def list_invitations(ctx=Depends(require_active_workspace_permission("members.read"))):
    db, _actor_id, tenant_id, _session_id = ctx
    rows = db.scalars(select(WorkspaceInvitation).where(WorkspaceInvitation.tenant_id == tenant_id)
                      .order_by(WorkspaceInvitation.created_at.desc()).limit(500)).all()
    return {"items": [_invitation_summary(row) for row in rows]}


@invitations_router.post("", status_code=201)
def create_invitation(body: InvitationCreateIn, request: Request,
                      idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                      ctx=Depends(require_active_workspace_permission("members.manage"))):
    db, actor_id, tenant_id, _session_id = ctx
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        idem, replay = begin_idempotency(db, tenant_id=tenant_id, operation_type="members.invitation.create",
            key=idempotency_key, payload={"email": str(body.email).lower(), "role_id": str(body.role_id),
            "branch_ids": [str(x) for x in body.branch_ids], "expires_in_days": body.expires_in_days})
    except CatalogValidation as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if replay:
        response_body = replay[1]
        replay_id = response_body.get("id")
        replay_row = None
        if replay_id:
            replay_row = db.scalar(select(WorkspaceInvitation).where(
                WorkspaceInvitation.id == UUID(str(replay_id)), WorkspaceInvitation.tenant_id == tenant_id
            ))
        replay_summary = _invitation_summary(replay_row) if replay_row else None
        db.rollback()
        if not replay_summary:
            raise HTTPException(status_code=409, detail="The original invitation record is no longer available")
        # The bearer token is never stored for idempotent replay. Status reflects the live record.
        return {"id": replay_summary["id"], "status": replay_summary["status"],
                "invite_url": None, "replayed": True,
                "message": "This invitation was already created. Resend it to issue a fresh one-time link."}
    request_id = getattr(request.state, "request_id", None)
    try:
        row, token = _create_invitation(db, tenant_id=tenant_id, actor_id=actor_id, email=str(body.email),
            role_id=body.role_id, branch_ids=body.branch_ids, expires_in_days=body.expires_in_days, request_id=request_id)
        stored_response = {"id": str(row.id), "status": row.status}
        finish_idempotency(db, idem, status_code=201, response_body=stored_response,
                           resource_type="workspace_invitation", resource_id=row.id)
        db.commit()
        return {**stored_response, "email": row.email, "expires_at": row.expires_at.isoformat(),
                "invite_url": "/invite#token=" + quote(token), "replayed": False}
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invitation conflicts with an existing pending invitation") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Workspace invitation could not be saved") from exc


@invitations_router.post("/{invitation_id}/revoke")
def revoke_invitation(invitation_id: UUID, request: Request, ctx=Depends(require_active_workspace_permission("members.manage"))):
    db, actor_id, tenant_id, _session_id = ctx
    row = db.scalar(select(WorkspaceInvitation).where(
        WorkspaceInvitation.id == invitation_id, WorkspaceInvitation.tenant_id == tenant_id
    ).with_for_update())
    if not row:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if row.status != "PENDING":
        return {"id": str(row.id), "status": row.status, "changed": False}
    row.status = "REVOKED"
    row.revoked_at = datetime.now(timezone.utc)
    request_id = getattr(request.state, "request_id", None)
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="workspace.invitation.revoke",
                target_type="workspace_invitation", target_id=row.id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type="workspace.invitation.revoked", aggregate_type="workspace_invitation",
               aggregate_id=row.id, actor_user_id=actor_id,
               payload={"invitation_id": str(row.id)}, correlation_id=request_id)
    db.commit()
    return {"id": str(row.id), "status": row.status, "changed": True}


@invitations_router.post("/{invitation_id}/resend", status_code=201)
def resend_invitation(invitation_id: UUID, request: Request,
                      idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                      ctx=Depends(require_active_workspace_permission("members.manage"))):
    db, actor_id, tenant_id, _session_id = ctx
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        idem, replay = begin_idempotency(db, tenant_id=tenant_id, operation_type="members.invitation.resend",
            key=idempotency_key, payload={"invitation_id": str(invitation_id)})
    except CatalogValidation as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if replay:
        stored = replay[1]
        replay_id = stored.get("id")
        replay_row = None
        if replay_id:
            replay_row = db.scalar(select(WorkspaceInvitation).where(
                WorkspaceInvitation.id == UUID(str(replay_id)), WorkspaceInvitation.tenant_id == tenant_id
            ))
        replay_summary = _invitation_summary(replay_row) if replay_row else None
        db.rollback()
        if not replay_summary:
            raise HTTPException(status_code=409, detail="The resent invitation record is no longer available")
        return {"id": replay_summary["id"], "status": replay_summary["status"],
                "invite_url": None, "replayed": True,
                "message": "This resend already completed. Use a new key to issue another one-time link."}
    row = db.scalar(select(WorkspaceInvitation).where(
        WorkspaceInvitation.id == invitation_id, WorkspaceInvitation.tenant_id == tenant_id
    ).with_for_update())
    if not row:
        db.rollback()
        raise HTTPException(status_code=404, detail="Invitation not found")
    if row.status not in ("PENDING", "EXPIRED"):
        db.rollback()
        raise HTTPException(status_code=409, detail="Only a pending or expired invitation can be resent")
    original = row
    if not original.role_id:
        db.rollback()
        raise HTTPException(status_code=409, detail="This invitation has no role assigned. Create a new invitation with an explicit role.")
    now = datetime.now(timezone.utc)
    if row.status == "EXPIRED" or invitation_is_expired(row.expires_at, now):
        original.status = "EXPIRED"
    else:
        original.status = "REVOKED"
        original.revoked_at = now
    request_id = getattr(request.state, "request_id", None)
    try:
        replacement, token = _create_invitation(db, tenant_id=tenant_id, actor_id=actor_id, email=original.email,
            role_id=original.role_id, branch_ids=[UUID(str(x)) for x in (original.branch_ids or [])],
            expires_in_days=7, request_id=request_id)
        write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="workspace.invitation.resend",
                    target_type="workspace_invitation", target_id=replacement.id, correlation_id=request_id)
        emit_event(db, tenant_id=tenant_id, event_type="workspace.invitation.resent", aggregate_type="workspace_invitation",
                   aggregate_id=replacement.id, actor_user_id=actor_id,
                   payload={"invitation_id": str(replacement.id), "replaces_invitation_id": str(original.id)}, correlation_id=request_id)
        finish_idempotency(db, idem, status_code=201, response_body={"id": str(replacement.id), "status": "PENDING"},
                           resource_type="workspace_invitation", resource_id=replacement.id)
        db.commit()
        return {"id": str(replacement.id), "email": replacement.email, "status": replacement.status,
                "expires_at": replacement.expires_at.isoformat(), "invite_url": "/invite#token=" + quote(token), "replayed": False}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invitation could not be reissued") from exc


@invitations_router.post("/preview")
def invitation_preview(body: InvitationPreviewIn, db: Session = Depends(get_db)):
    token = body.token.strip()
    if len(token) < 32 or len(token) > 512:
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    lookup = db.execute(text("SELECT invitation_id, tenant_id FROM public.lexa_find_workspace_invitation(:token_hash)"),
                        {"token_hash": invitation_token_digest(token)}).mappings().first()
    if not lookup:
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    tenant_id = UUID(str(lookup["tenant_id"]))
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "ACTIVE"))
    row = db.scalar(select(WorkspaceInvitation).where(
        WorkspaceInvitation.id == UUID(str(lookup["invitation_id"])), WorkspaceInvitation.tenant_id == tenant_id,
        WorkspaceInvitation.status == "PENDING",
    ))
    if not row or not tenant or invitation_is_expired(row.expires_at):
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    return {"email": row.email, "workspace_name": tenant.name, "expires_at": row.expires_at.isoformat()}


@invitations_router.post("/accept")
def accept_invitation(body: InvitationAcceptIn, response: Response, request: Request, db: Session = Depends(get_db)):
    token_hash = invitation_token_digest(body.token.strip())
    lookup = db.execute(text("SELECT invitation_id, tenant_id FROM public.lexa_find_workspace_invitation(:token_hash)"),
                        {"token_hash": token_hash}).mappings().first()
    if not lookup:
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    tenant_id = UUID(str(lookup["tenant_id"]))
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "ACTIVE"))
    if not tenant:
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    invitation = db.scalar(select(WorkspaceInvitation).where(
        WorkspaceInvitation.id == UUID(str(lookup["invitation_id"])),
        WorkspaceInvitation.tenant_id == tenant_id,
        WorkspaceInvitation.token_hash == token_hash,
        WorkspaceInvitation.status == "PENDING",
    ).with_for_update())
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    if invitation_is_expired(invitation.expires_at):
        invitation.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=410, detail="Invitation has expired. Ask the administrator to resend it.")

    user = db.scalar(select(User).where(func.lower(User.email) == invitation.email).with_for_update())
    if user and (not user.is_active or not verify_password(body.password, user.password_hash)):
        raise HTTPException(status_code=401, detail="Could not verify the account for this invitation")
    if not user:
        user = User(email=invitation.email, password_hash=hash_password(body.password), is_active=True)
        db.add(user)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="An account with this email was created concurrently. Sign in and accept the invitation again.") from exc

    existing_membership = db.scalar(select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user.id
    ).with_for_update())
    if existing_membership:
        raise HTTPException(status_code=409, detail="This account already has a membership in the invited workspace. Sign in or contact an administrator.")
    role = db.scalar(select(Role).where(Role.id == invitation.role_id, Role.tenant_id == tenant_id))
    if not role:
        raise HTTPException(status_code=409, detail="The invited role is no longer available")
    membership = TenantMembership(tenant_id=tenant_id, user_id=user.id, status="ACTIVE")
    db.add(membership)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="The workspace membership already exists or changed concurrently") from exc
    db.add(MembershipRole(membership_id=membership.id, role_id=role.id))
    branch_ids = normalize_branch_ids([str(x) for x in (invitation.branch_ids or [])])
    if branch_ids:
        valid = db.scalars(select(Branch.id).where(Branch.tenant_id == tenant_id, Branch.status == "ACTIVE", Branch.id.in_(branch_ids))).all()
        if {str(x) for x in valid} != set(branch_ids):
            raise HTTPException(status_code=409, detail="One or more invited branches are no longer active. Ask the administrator to issue a new invitation.")
        for branch_id in valid:
            db.add(MembershipBranchAssignment(membership_id=membership.id, branch_id=branch_id,
                                              tenant_id=tenant_id, assigned_by_user_id=invitation.invited_by_user_id))
    now = datetime.now(timezone.utc)
    invitation.status = "ACCEPTED"
    invitation.accepted_by_user_id = user.id
    invitation.accepted_at = now
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"),
               {"tenant_id": str(tenant_id), "user_id": str(user.id)})
    refresh = new_refresh_token()
    auth_session = AuthSession(tenant_id=tenant_id, user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh),
        expires_at=now + timedelta(days=settings.refresh_token_days))
    db.add(auth_session)
    request_id = getattr(request.state, "request_id", None)
    write_audit(db, tenant_id=tenant_id, actor_user_id=user.id, action="workspace.invitation.accept",
                target_type="workspace_invitation", target_id=invitation.id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type="workspace.invitation.accepted", aggregate_type="workspace_invitation",
               aggregate_id=invitation.id, actor_user_id=user.id,
               payload={"invitation_id": str(invitation.id), "membership_id": str(membership.id), "user_id": str(user.id)},
               correlation_id=request_id)
    try:
        # Load the workspace name before commit while the tenant RLS context is set.
        tenant_name = tenant.name
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="The invitation was already accepted or the membership already exists") from exc
    _set_refresh_cookie(response, refresh)
    return {
        "access_token": create_access_token(user.id, tenant_id, auth_session.id), "token_type": "bearer",
        "session_id": str(auth_session.id), "tenant_id": str(tenant_id),
        "tenant_name": tenant_name, "user_id": str(user.id),
    }
