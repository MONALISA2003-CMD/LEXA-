"""Fail-closed branch authorization helpers for Phase 3 business endpoints."""
from __future__ import annotations
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Branch, Location, MembershipRole, Role, TenantMembership, Warehouse
from .workspace_models import MembershipBranchAssignment


def assigned_branch_ids(db: Session, *, tenant_id: UUID, user_id: UUID) -> set[UUID]:
    membership_id = db.scalar(select(TenantMembership.id).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.user_id == user_id,
        TenantMembership.status == "ACTIVE",
    ))
    if not membership_id:
        raise HTTPException(status_code=403, detail="Active workspace membership required")
    # Owners and administrators manage the whole workspace. PostgreSQL's
    # lexa_can_access_branch() already grants these roles full branch scope; keep
    # Python guards aligned so the same user is not rejected by a stricter helper.
    roles = set(db.scalars(
        select(Role.name)
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .where(MembershipRole.membership_id == membership_id, Role.tenant_id == tenant_id)
    ).all())
    if roles.intersection({"Owner", "Administrator", "Admin"}):
        return set(db.scalars(select(Branch.id).where(
            Branch.tenant_id == tenant_id, Branch.status == "ACTIVE"
        )).all())
    return set(db.scalars(
        select(MembershipBranchAssignment.branch_id)
        .join(Branch, (Branch.id == MembershipBranchAssignment.branch_id) & (Branch.tenant_id == MembershipBranchAssignment.tenant_id))
        .where(
            MembershipBranchAssignment.tenant_id == tenant_id,
            MembershipBranchAssignment.membership_id == membership_id,
            MembershipBranchAssignment.status == "ACTIVE",
            Branch.status == "ACTIVE",
        )
    ).all())


def ensure_branch_access(db: Session, *, tenant_id: UUID, user_id: UUID, branch_id: UUID) -> UUID:
    branch = db.scalar(select(Branch.id).where(
        Branch.id == branch_id, Branch.tenant_id == tenant_id, Branch.status == "ACTIVE"
    ))
    if not branch:
        raise HTTPException(status_code=400, detail="Branch does not belong to this workspace or is inactive")
    if branch_id not in assigned_branch_ids(db, tenant_id=tenant_id, user_id=user_id):
        raise HTTPException(status_code=403, detail="Access to this branch has not been assigned to your membership")
    return branch_id


def ensure_location_access(db: Session, *, tenant_id: UUID, user_id: UUID, location_id: UUID) -> UUID:
    row = db.execute(
        select(Location.id, Warehouse.branch_id)
        .join(Warehouse, (Warehouse.id == Location.warehouse_id) & (Warehouse.tenant_id == Location.tenant_id))
        .where(
            Location.id == location_id, Location.tenant_id == tenant_id, Location.status == "ACTIVE",
            Warehouse.status == "ACTIVE",
        )
    ).first()
    if not row:
        raise HTTPException(status_code=400, detail="Stock location does not belong to this workspace or is inactive")
    branch_id = row.branch_id
    if branch_id is None:
        raise HTTPException(status_code=403, detail="Stock location must be linked to an active branch before branch-scoped operations")
    ensure_branch_access(db, tenant_id=tenant_id, user_id=user_id, branch_id=branch_id)
    return branch_id


def accessible_location_ids(db: Session, *, tenant_id: UUID, user_id: UUID) -> list[UUID]:
    branches = assigned_branch_ids(db, tenant_id=tenant_id, user_id=user_id)
    if not branches:
        return []
    return list(db.scalars(
        select(Location.id)
        .join(Warehouse, (Warehouse.id == Location.warehouse_id) & (Warehouse.tenant_id == Location.tenant_id))
        .where(
            Location.tenant_id == tenant_id, Location.status == "ACTIVE",
            Warehouse.status == "ACTIVE", Warehouse.branch_id.in_(branches),
        )
    ).all())


def require_full_branch_scope(db: Session, *, tenant_id: UUID, user_id: UUID) -> None:
    """Guard tenant-wide aggregates/mutations that cannot yet be split by branch."""
    active_branches = set(db.scalars(select(Branch.id).where(
        Branch.tenant_id == tenant_id, Branch.status == "ACTIVE"
    )).all())
    assigned = assigned_branch_ids(db, tenant_id=tenant_id, user_id=user_id)
    if not active_branches:
        raise HTTPException(status_code=409, detail={
            "code": "WORKSPACE_SETUP_REQUIRED",
            "message": "Finish setting up your business locations before opening this view.",
        })
    if not active_branches.issubset(assigned):
        raise HTTPException(status_code=403, detail={
            "code": "BRANCH_ACCESS_REQUIRED",
            "message": "Your access needs to include every branch shown in this report. Ask your workspace owner to review it.",
        })
    # Tenant-wide rollups/rebuilds would otherwise touch legacy locations that bypass
    # branch scope through a NULL or inactive branch link.
    unscoped_location = db.scalar(select(Location.id)
        .join(Warehouse, (Warehouse.id == Location.warehouse_id) & (Warehouse.tenant_id == Location.tenant_id))
        .outerjoin(Branch, (Branch.id == Warehouse.branch_id) & (Branch.tenant_id == Warehouse.tenant_id))
        .where(Location.tenant_id == tenant_id, Location.status == "ACTIVE", Warehouse.status == "ACTIVE",
               or_(Warehouse.branch_id.is_(None), Branch.id.is_(None), Branch.status != "ACTIVE"))
        .limit(1))
    if unscoped_location:
        raise HTTPException(status_code=409, detail="Active stock locations must be linked to active branches before workspace-wide operations")
