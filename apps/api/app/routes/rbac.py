from datetime import datetime, timedelta, timezone
import hashlib, secrets
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ..dependencies import require_permission
from ..models import Role, Permission, MembershipRole, TenantMembership, MembershipBranchAssignment, TenantInvitation, User, Branch

router = APIRouter(prefix="/rbac", tags=["rbac"])

class RoleIn(BaseModel): name: str; description: str | None = None
class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; tenant_id: UUID; name: str; description: str | None
class AssignRoleIn(BaseModel): membership_id: UUID; role_id: UUID
class MemberStatusIn(BaseModel): status: str = Field(pattern="^(ACTIVE|SUSPENDED|REMOVED)$")
class BranchAssignmentIn(BaseModel): membership_id: UUID; branch_id: UUID
class InvitationIn(BaseModel):
    email: EmailStr
    role_id: UUID | None = None

@router.get("/permissions")
def permissions(ctx=Depends(require_permission("roles.read"))):
    db, *_ = ctx
    return [{"id": str(p.id), "code": p.code, "description": p.description} for p in db.scalars(select(Permission).order_by(Permission.code))]

@router.get("/roles", response_model=list[RoleOut])
def roles(ctx=Depends(require_permission("roles.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name)))

@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(body: RoleIn, ctx=Depends(require_permission("roles.manage"))):
    db, _, tenant_id, _ = ctx
    name = body.name.strip()
    if not name: raise HTTPException(400, "Role name is required")
    role = Role(tenant_id=tenant_id, name=name, description=body.description); db.add(role)
    try: db.commit()
    except Exception as exc: db.rollback(); raise HTTPException(409, "Role name already exists") from exc
    db.refresh(role); return role

@router.post("/role-assignments")
def assign_role(body: AssignRoleIn, ctx=Depends(require_permission("roles.manage"))):
    db, _, tenant_id, _ = ctx
    membership = db.scalar(select(TenantMembership).where(TenantMembership.id == body.membership_id, TenantMembership.tenant_id == tenant_id))
    role = db.scalar(select(Role).where(Role.id == body.role_id, Role.tenant_id == tenant_id))
    if not membership or not role: raise HTTPException(400, "Membership and role must belong to tenant")
    if not db.scalar(select(MembershipRole).where(MembershipRole.membership_id == membership.id, MembershipRole.role_id == role.id)):
        db.add(MembershipRole(membership_id=membership.id, role_id=role.id)); db.commit()
    return {"membership_id": str(membership.id), "role_id": str(role.id), "status": "assigned"}

@router.get("/members")
def members(ctx=Depends(require_permission("users.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.execute(text("""
      SELECT tm.id AS membership_id,u.id AS user_id,u.email,u.display_name,tm.status,
             COALESCE(array_agg(DISTINCT r.name) FILTER (WHERE r.id IS NOT NULL), ARRAY[]::varchar[]) AS roles,
             COALESCE(array_agg(DISTINCT b.id) FILTER (WHERE b.id IS NOT NULL), ARRAY[]::uuid[]) AS branch_ids
      FROM tenant_memberships tm
      JOIN users u ON u.id=tm.user_id
      LEFT JOIN membership_roles mr ON mr.membership_id=tm.id
      LEFT JOIN roles r ON r.id=mr.role_id AND r.tenant_id=:tenant_id
      LEFT JOIN membership_branch_assignments mba ON mba.membership_id=tm.id AND mba.tenant_id=:tenant_id
      LEFT JOIN branches b ON b.id=mba.branch_id AND b.tenant_id=:tenant_id
      WHERE tm.tenant_id=:tenant_id
      GROUP BY tm.id,u.id,u.email,u.display_name,tm.status
      ORDER BY u.email
    """), {"tenant_id": str(tenant_id)}).mappings().all()
    return [{
      "membership_id": str(r["membership_id"]), "user_id": str(r["user_id"]), "email": r["email"],
      "display_name": r["display_name"], "status": r["status"], "roles": list(r["roles"] or []),
      "branch_ids": [str(x) for x in (r["branch_ids"] or [])]
    } for r in rows]

@router.patch("/members/{membership_id}")
def update_member(membership_id: UUID, body: MemberStatusIn, ctx=Depends(require_permission("users.manage"))):
    db, actor_user_id, tenant_id, _ = ctx
    membership = db.scalar(select(TenantMembership).where(TenantMembership.id == membership_id, TenantMembership.tenant_id == tenant_id))
    if not membership: raise HTTPException(404, "Membership not found")
    if body.status != "ACTIVE" and db.scalar(select(Role.id).join(MembershipRole, MembershipRole.role_id == Role.id).where(MembershipRole.membership_id == membership.id, Role.tenant_id == tenant_id, Role.name == "Owner")):
        active_owner_count = db.execute(text("""SELECT count(*) FROM tenant_memberships tm JOIN membership_roles mr ON mr.membership_id=tm.id JOIN roles r ON r.id=mr.role_id WHERE tm.tenant_id=:tenant_id AND tm.status='ACTIVE' AND r.tenant_id=:tenant_id AND r.name='Owner'"""), {"tenant_id": str(tenant_id)}).scalar_one()
        if active_owner_count <= 1:
            raise HTTPException(409, "The last active Owner cannot be suspended or removed")
    membership.status = body.status
    db.commit()
    return {"membership_id": str(membership.id), "status": membership.status, "actor_user_id": str(actor_user_id)}

@router.post("/branch-assignments")
def assign_branch(body: BranchAssignmentIn, ctx=Depends(require_permission("branches.assign"))):
    db, _, tenant_id, _ = ctx
    membership = db.scalar(select(TenantMembership).where(TenantMembership.id == body.membership_id, TenantMembership.tenant_id == tenant_id))
    branch = db.scalar(select(Branch.id).where(Branch.id == body.branch_id, Branch.tenant_id == tenant_id))
    if not membership or not branch: raise HTTPException(400, "Membership and branch must belong to tenant")
    existing = db.scalar(select(MembershipBranchAssignment).where(MembershipBranchAssignment.tenant_id == tenant_id, MembershipBranchAssignment.membership_id == membership.id, MembershipBranchAssignment.branch_id == body.branch_id))
    if not existing:
        db.add(MembershipBranchAssignment(tenant_id=tenant_id, membership_id=membership.id, branch_id=body.branch_id)); db.commit()
    return {"membership_id": str(membership.id), "branch_id": str(body.branch_id), "status": "assigned"}

@router.delete("/branch-assignments/{membership_id}/{branch_id}")
def unassign_branch(membership_id: UUID, branch_id: UUID, ctx=Depends(require_permission("branches.assign"))):
    db, _, tenant_id, _ = ctx
    row = db.scalar(select(MembershipBranchAssignment).where(MembershipBranchAssignment.tenant_id == tenant_id, MembershipBranchAssignment.membership_id == membership_id, MembershipBranchAssignment.branch_id == branch_id))
    if not row: raise HTTPException(404, "Branch assignment not found")
    db.delete(row); db.commit()
    return {"membership_id": str(membership_id), "branch_id": str(branch_id), "status": "unassigned"}

@router.post("/invitations")
def create_invitation(body: InvitationIn, ctx=Depends(require_permission("users.invite"))):
    db, actor_user_id, tenant_id, _ = ctx
    role = db.scalar(select(Role).where(Role.id == body.role_id, Role.tenant_id == tenant_id)) if body.role_id else db.scalar(select(Role).where(Role.tenant_id == tenant_id, Role.name == "Staff / Operator"))
    if not role: raise HTTPException(400, "A valid tenant role is required")
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    invite = TenantInvitation(
        tenant_id=tenant_id, email=body.email.lower().strip(), token_hash=token_hash, role_id=role.id,
        invited_by_user_id=actor_user_id, expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite); db.commit(); db.refresh(invite)
    return {
      "id": str(invite.id), "email": invite.email, "role_id": str(role.id), "role_name": role.name,
      "expires_at": invite.expires_at, "status": invite.status,
      "invitation_token": raw_token,
      "delivery": "manual_token_until_email_dispatch_is_enabled"
    }
