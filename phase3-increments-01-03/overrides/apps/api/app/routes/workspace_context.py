"""Workspace selection, authorization-backed context, and resumable setup."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select, text, func, or_
from sqlalchemy.orm import Session

from ..auth import create_access_token, new_refresh_token, hash_refresh_token, _set_refresh_cookie
from ..catalog import emit_event, write_audit
from ..dependencies import current_context, get_db, tenant_db
from ..models import (
    Branch, BusinessProfile, Location, Session as AuthSession, Tenant, TenantMembership,
    User, Warehouse,
)
from ..workspace_domain import setup_progress
from ..config import settings
from ..workspace_models import MembershipBranchAssignment

router = APIRouter(prefix="/workspace", tags=["workspace"])


class SelectWorkspaceIn(BaseModel):
    tenant_id: UUID


def require_active_workspace(ctx=Depends(tenant_db)):
    db, _user_id, tenant_id, _session_id = ctx
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "ACTIVE"))
    if not tenant:
        raise HTTPException(status_code=403, detail="This workspace is not active")
    return ctx


def _workspace_rows(db: Session, user_id: UUID):
    # This is the same narrow SECURITY DEFINER list contract used by /auth/login.
    rows = db.execute(
        text("SELECT tenant_id, tenant_name, membership_id FROM public.lexa_list_active_user_workspaces(:user_id)"),
        {"user_id": str(user_id)},
    ).mappings().all()
    return [
        {"tenant_id": str(row["tenant_id"]), "tenant_name": str(row["tenant_name"]), "membership_id": str(row["membership_id"])}
        for row in rows
    ]


def _require_live_user_session(db: Session, user_id: UUID, old_tenant_id: UUID, session_id: UUID):
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"),
        {"tenant_id": str(old_tenant_id), "user_id": str(user_id)},
    )
    session = db.scalar(select(AuthSession).where(
        AuthSession.id == session_id,
        AuthSession.tenant_id == old_tenant_id,
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    ).with_for_update())
    user = db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if not session or session.expires_at <= datetime.now(timezone.utc) or not user:
        raise HTTPException(status_code=401, detail="Your session is no longer active")
    return session, user


@router.get("/options")
def workspace_options(context=Depends(current_context), db: Session = Depends(get_db)):
    user_id, current_tenant_id, session_id = context
    _require_live_user_session(db, user_id, current_tenant_id, session_id)
    rows = _workspace_rows(db, user_id)
    return {"items": [dict(row, current=row["tenant_id"] == str(current_tenant_id)) for row in rows]}


@router.post("/select")
def select_workspace(body: SelectWorkspaceIn, response: Response, request: Request, context=Depends(current_context), db: Session = Depends(get_db)):
    user_id, current_tenant_id, session_id = context
    old_session, user = _require_live_user_session(db, user_id, current_tenant_id, session_id)
    choices = _workspace_rows(db, user_id)
    selected = next((row for row in choices if row["tenant_id"] == str(body.tenant_id)), None)
    if selected is None:
        db.rollback()
        raise HTTPException(status_code=403, detail="You do not have an active membership in that workspace")

    # Tenant and membership IDs from the browser are selectors only: the list function above
    # is the authority. Set the new transaction-local context only after that check.
    now = datetime.now(timezone.utc)
    # Revoke the old tenant-scoped session while the old tenant GUC is still active;
    # otherwise an RLS policy could hide the update after switching app.tenant_id.
    old_session.revoked_at = now
    db.flush()
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"), {
        "tenant_id": selected["tenant_id"], "user_id": str(user_id),
    })
    active_tenant = db.scalar(select(Tenant).where(Tenant.id == body.tenant_id, Tenant.status == "ACTIVE"))
    if not active_tenant:
        db.rollback()
        raise HTTPException(status_code=403, detail="That workspace is not active")
    refresh = new_refresh_token()
    new_session = AuthSession(
        tenant_id=body.tenant_id,
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh),
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    db.add(new_session)
    db.flush()
    request_id = getattr(request.state, "request_id", None)
    write_audit(db, tenant_id=body.tenant_id, actor_user_id=user_id, action="workspace.switch", target_type="tenant",
                target_id=body.tenant_id, correlation_id=request_id)
    emit_event(db, tenant_id=body.tenant_id, event_type="workspace.switched", aggregate_type="tenant", aggregate_id=body.tenant_id,
               actor_user_id=user_id, payload={"tenant_id": str(body.tenant_id), "previous_tenant_id": str(current_tenant_id)},
               correlation_id=request_id)
    db.commit()
    _set_refresh_cookie(response, refresh)
    return {
        "access_token": create_access_token(user.id, body.tenant_id, new_session.id),
        "token_type": "bearer",
        "session_id": str(new_session.id),
        "tenant_id": selected["tenant_id"],
        "tenant_name": selected["tenant_name"],
    }


@router.get("/context")
def workspace_context(ctx=Depends(require_active_workspace)):
    db, user_id, tenant_id, session_id = ctx
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user_id, TenantMembership.status == "ACTIVE"
    ))
    if not tenant or tenant.status != "ACTIVE" or not membership:
        raise HTTPException(status_code=403, detail="Active workspace membership required")
    branch_ids = db.scalars(select(MembershipBranchAssignment.branch_id).where(
        MembershipBranchAssignment.tenant_id == tenant_id,
        MembershipBranchAssignment.membership_id == membership.id,
        MembershipBranchAssignment.status == "ACTIVE",
    ).order_by(MembershipBranchAssignment.branch_id)).all()
    branches = db.scalars(select(Branch).where(Branch.tenant_id == tenant_id, Branch.status == "ACTIVE").order_by(Branch.name)).all()
    return {
        "workspace": {"id": str(tenant.id), "name": tenant.name, "status": tenant.status},
        "membership": {"id": str(membership.id), "status": membership.status},
        "branches": [{"id": str(branch.id), "name": branch.name, "code": branch.code, "assigned": str(branch.id) in {str(item) for item in branch_ids}} for branch in branches],
        "session_id": str(session_id),
    }


def _setup_progress_for_tenant(db: Session, tenant_id: UUID) -> dict:
    """Derive progress from active, tenant-consistent persisted setup records."""
    profile = db.scalar(select(BusinessProfile.id).where(BusinessProfile.tenant_id == tenant_id))
    active_branch_ids = list(db.scalars(select(Branch.id).where(
        Branch.tenant_id == tenant_id, Branch.status == "ACTIVE"
    )).all())
    active_warehouse_ids = list(db.scalars(select(Warehouse.id).where(
        Warehouse.tenant_id == tenant_id,
        Warehouse.status == "ACTIVE",
        or_(Warehouse.branch_id.is_(None), Warehouse.branch_id.in_(active_branch_ids)),
    )).all())
    location_count = 0
    if active_warehouse_ids:
        location_count = db.scalar(
            select(func.count()).select_from(Location).join(Warehouse, Location.warehouse_id == Warehouse.id).where(
                Location.tenant_id == tenant_id,
                Location.status == "ACTIVE",
                Warehouse.tenant_id == tenant_id,
                Warehouse.status == "ACTIVE",
                Warehouse.id.in_(active_warehouse_ids),
            )
        ) or 0
    return setup_progress(
        profile_exists=profile is not None,
        branch_count=len(active_branch_ids),
        warehouse_count=len(active_warehouse_ids),
        location_count=int(location_count),
    )


@router.get("/setup/progress")
def get_setup_progress(ctx=Depends(require_active_workspace)):
    db, _user_id, tenant_id, _session_id = ctx
    return _setup_progress_for_tenant(db, tenant_id)

@router.post("/setup/complete")
def complete_setup(ctx=Depends(require_active_workspace)):
    db, _user_id, tenant_id, _session_id = ctx
    progress = _setup_progress_for_tenant(db, tenant_id)
    if not progress["complete"]:
        raise HTTPException(status_code=409, detail={"code": "SETUP_INCOMPLETE", "message": "Complete the required setup steps first.", "progress": progress})
    # Completion is derived from real persisted configuration instead of a shadow flag
    # that can become stale when branches, warehouses, or locations are removed.
    return {"status": "COMPLETE", "complete": True, "workspace_id": str(tenant_id)}
