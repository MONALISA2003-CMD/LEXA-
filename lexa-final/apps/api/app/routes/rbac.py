from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from ..dependencies import require_permission
from ..models import Role, Permission, MembershipRole, TenantMembership

router = APIRouter(prefix="/rbac", tags=["rbac"])
class RoleIn(BaseModel): name: str; description: str | None = None
class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; tenant_id: UUID; name: str; description: str | None
class AssignRoleIn(BaseModel): membership_id: UUID; role_id: UUID

@router.get("/permissions")
def permissions(ctx=Depends(require_permission("roles.read"))):
    db, *_ = ctx
    return [{"id": str(p.id), "code": p.code, "description": p.description} for p in db.scalars(select(Permission).order_by(Permission.code))]

@router.get("/roles", response_model=list[RoleOut])
def roles(ctx=Depends(require_permission("roles.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name)))

@router.post("/roles", response_model=RoleOut)
def create_role(body: RoleIn, ctx=Depends(require_permission("roles.manage"))):
    db, _, tenant_id, _ = ctx
    role = Role(tenant_id=tenant_id, name=body.name.strip(), description=body.description); db.add(role)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "Role name already exists")
    db.refresh(role); return role

@router.post("/role-assignments")
def assign_role(body: AssignRoleIn, ctx=Depends(require_permission("roles.manage"))):
    db, _, tenant_id, _ = ctx
    membership = db.scalar(select(TenantMembership).where(TenantMembership.id == body.membership_id, TenantMembership.tenant_id == tenant_id))
    role = db.scalar(select(Role).where(Role.id == body.role_id, Role.tenant_id == tenant_id))
    if not membership or not role: raise HTTPException(400, "Membership and role must belong to tenant")
    if not db.scalar(select(MembershipRole).where(MembershipRole.membership_id == membership.id, MembershipRole.role_id == role.id)):
        db.add(MembershipRole(membership_id=membership.id, role_id=role.id)); db.commit()
    return {"membership_id": membership.id, "role_id": role.id, "status": "assigned"}
