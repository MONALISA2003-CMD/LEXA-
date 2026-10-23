"""Workspace selection, authorization-backed context, and resumable setup."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select, text, func, or_
from sqlalchemy.orm import Session

from ..auth import create_access_token, new_refresh_token, hash_refresh_token, _set_refresh_cookie
from ..catalog import emit_event, write_audit
from ..dependencies import current_context, get_db, require_permission, tenant_db
from ..models import (
    Branch, BusinessProfile, Location, MembershipRole, Role, Session as AuthSession, Tenant, TenantMembership,
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
    # This lookup is bound to the authenticated transaction-local app.user_id.
    # Login uses a separate pre-auth lookup because no authenticated user context exists yet.
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
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id))
    profile_details_complete = bool(
        profile
        and (profile.legal_name or "").strip()
        and (profile.display_name or "").strip()
        and len((profile.country_code or "").strip()) == 2
        and (profile.country_code or "").strip().isascii()
        and (profile.country_code or "").strip().isalpha()
    )
    currency_code = (profile.currency_code or "").strip().upper() if profile else ""
    currency_configured = bool(len(currency_code) == 3 and currency_code.isascii() and currency_code.isalpha())
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
    # Payment setup is only ready when at least one active channel can be used
    # in this business's configured currency. A foreign-currency channel is not
    # an acceptable substitute for a local cash/payment option.
    payment_method_count = 0
    if currency_configured:
        payment_method_count = db.scalar(text(
            "SELECT count(*) FROM public.payment_channels WHERE tenant_id=:tenant_id AND active=true AND upper(currency_code)=:currency"
        ), {"tenant_id": str(tenant_id), "currency": currency_code}) or 0
    accounting_account_count = db.scalar(text(
        "SELECT count(*) FROM public.accounting_accounts WHERE tenant_id=:tenant_id AND status='ACTIVE'"
    ), {"tenant_id": str(tenant_id)}) or 0
    accounting_mapping_count = db.scalar(text(
        "SELECT count(*) FROM public.accounting_mappings WHERE tenant_id=:tenant_id"
    ), {"tenant_id": str(tenant_id)}) or 0
    tax_configuration_ready = bool(db.scalar(text("""
        SELECT EXISTS (
          SELECT 1
          FROM public.tax_configurations tc
          JOIN public.tax_rates tr
            ON tr.tenant_id=tc.tenant_id AND tr.id=tc.tax_rate_id
          WHERE tc.tenant_id=:tenant_id
            AND tc.status='ACTIVE' AND tr.status='ACTIVE'
            AND tc.scope_type='DEFAULT'
            AND CURRENT_DATE BETWEEN tc.effective_from AND COALESCE(tc.effective_to, DATE '9999-12-31')
            AND CURRENT_DATE BETWEEN tr.effective_from AND COALESCE(tr.effective_to, DATE '9999-12-31')
        )
    """), {"tenant_id": str(tenant_id)}))
    team_access_ready = bool(db.scalar(text("""
        SELECT EXISTS (
          SELECT 1
          FROM public.tenant_memberships tm
          JOIN public.users u ON u.id=tm.user_id AND u.is_active=true
          JOIN public.membership_roles mr ON mr.membership_id=tm.id
          JOIN public.roles r ON r.id=mr.role_id AND r.tenant_id=tm.tenant_id
          WHERE tm.tenant_id=:tenant_id AND tm.status='ACTIVE'
        )
    """), {"tenant_id": str(tenant_id)}))
    return setup_progress(
        profile_exists=profile_details_complete,
        currency_configured=currency_configured,
        branch_count=len(active_branch_ids),
        warehouse_count=len(active_warehouse_ids),
        location_count=int(location_count),
        payment_method_count=int(payment_method_count),
        accounting_account_count=int(accounting_account_count),
        accounting_mapping_count=int(accounting_mapping_count),
        tax_configuration_ready=tax_configuration_ready,
        team_access_ready=team_access_ready,
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


@router.post("/setup/initialize")
def initialize_workspace_setup(request: Request, ctx=Depends(require_permission("organization.manage"))):
    """Fill only missing first-run defaults for the active workspace.

    This is deliberately idempotent: it never renames, deletes, or replaces any
    existing branch, warehouse, stock location, payment method, or account.
    """
    db, actor_id, tenant_id, _session_id = ctx
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "ACTIVE").with_for_update())
    if not tenant:
        raise HTTPException(status_code=403, detail="This business is not active.")

    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id))
    if not profile:
        raise HTTPException(status_code=409, detail={
            "code": "BUSINESS_PROFILE_REQUIRED",
            "message": "Save your business name and currency before completing setup.",
        })
    currency = (profile.currency_code or "").strip().upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise HTTPException(status_code=409, detail={
            "code": "BUSINESS_CURRENCY_REQUIRED",
            "message": "Save a valid three-letter business currency before completing setup. LEXA will not guess a currency for your financial records.",
        })

    created: list[str] = []

    def next_code(model, base: str) -> str:
        existing = set(db.scalars(select(model.code).where(model.tenant_id == tenant_id)).all())
        if base not in existing:
            return base
        suffix = 2
        while f"{base}-{suffix:02d}" in existing:
            suffix += 1
        return f"{base}-{suffix:02d}"

    branches = list(db.scalars(select(Branch).where(
        Branch.tenant_id == tenant_id, Branch.status == "ACTIVE"
    ).order_by(Branch.created_at, Branch.id)).all())
    if not branches:
        branch = Branch(tenant_id=tenant_id, name="Main branch", code=next_code(Branch, "MAIN"), status="ACTIVE")
        db.add(branch)
        db.flush()
        branches = [branch]
        created.append("main_branch")

    # Workspaces created before the current onboarding flow can have a branch but
    # no warehouse. Repair only the missing pieces; don't touch business data.
    branch_ids = [branch.id for branch in branches]
    warehouses = list(db.scalars(select(Warehouse).where(
        Warehouse.tenant_id == tenant_id,
        Warehouse.status == "ACTIVE",
        Warehouse.branch_id.in_(branch_ids),
    ).order_by(Warehouse.created_at, Warehouse.id)).all()) if branch_ids else []
    if not warehouses:
        warehouse = Warehouse(
            tenant_id=tenant_id, branch_id=branches[0].id,
            name="Main warehouse", code=next_code(Warehouse, "MAIN"), status="ACTIVE",
        )
        db.add(warehouse)
        db.flush()
        warehouses = [warehouse]
        created.append("main_warehouse")

    # A legacy unassigned warehouse is safe to attach automatically only where
    # there's exactly one active branch. Multiple branches need an owner decision.
    if len(branches) == 1:
        unassigned_warehouse = db.scalar(select(Warehouse).where(
            Warehouse.tenant_id == tenant_id, Warehouse.status == "ACTIVE",
            Warehouse.branch_id.is_(None),
        ).order_by(Warehouse.created_at).limit(1).with_for_update())
        if unassigned_warehouse:
            unassigned_warehouse.branch_id = branches[0].id
            db.flush()
            if all(item.id != unassigned_warehouse.id for item in warehouses):
                warehouses.insert(0, unassigned_warehouse)

    warehouse_ids = [warehouse.id for warehouse in warehouses]
    locations = list(db.scalars(select(Location).where(
        Location.tenant_id == tenant_id, Location.status == "ACTIVE",
        Location.warehouse_id.in_(warehouse_ids),
    ).order_by(Location.created_at, Location.id)).all()) if warehouse_ids else []
    if not locations:
        location = Location(
            tenant_id=tenant_id, warehouse_id=warehouses[0].id,
            name="Main location", code=next_code(Location, "MAIN"), status="ACTIVE",
        )
        db.add(location)
        db.flush()
        created.append("main_stock_location")

    # Ensure Owner/Administrator records remain usable after historic branch
    # creation. The helper grants these roles workspace-wide scope; assignments
    # are added as transparent, auditable metadata, not used as a hidden bypass.
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.user_id == actor_id,
        TenantMembership.status == "ACTIVE",
    ))
    if membership:
        actor_roles = set(db.scalars(
            select(Role.name)
            .join(MembershipRole, MembershipRole.role_id == Role.id)
            .where(MembershipRole.membership_id == membership.id, Role.tenant_id == tenant_id)
        ).all())
        if actor_roles.intersection({"Owner", "Administrator", "Admin"}):
            existing_assignments = set(db.scalars(select(MembershipBranchAssignment.branch_id).where(
                MembershipBranchAssignment.tenant_id == tenant_id,
                MembershipBranchAssignment.membership_id == membership.id,
                MembershipBranchAssignment.status == "ACTIVE",
            )).all())
            for branch in branches:
                if branch.id not in existing_assignments:
                    db.add(MembershipBranchAssignment(
                        tenant_id=tenant_id, membership_id=membership.id, branch_id=branch.id,
                        assigned_by_user_id=actor_id, status="ACTIVE",
                    ))
                    created.append(f"branch_access:{branch.code}")

    # Rebuild missing accounting defaults only when the existing migration has
    # installed the idempotent seed function. Tax rates remain owner-configured.
    seed_function_exists = bool(db.scalar(text(
        "SELECT to_regprocedure('public.seed_accounting_foundation(uuid)') IS NOT NULL"
    )))
    if seed_function_exists:
        db.execute(text("SELECT public.seed_accounting_foundation(:tenant_id)"), {"tenant_id": str(tenant_id)})

    # Cash is the default method for this business currency. A legacy cash row
    # in another currency (or an inactive row) must not make checkout appear ready.
    # Existing rows and payment history are retained; a distinct label avoids a
    # confusing duplicate name when a business changes currency.
    cash_ready = db.execute(text("""
        SELECT 1 FROM public.payment_channels
        WHERE tenant_id=:tenant_id AND active=true AND upper(currency_code)=:currency
          AND channel_type='CASH'
        LIMIT 1
    """), {"tenant_id": str(tenant_id), "currency": currency}).first()
    if not cash_ready:
        prior_cash = db.execute(text(
            "SELECT 1 FROM public.payment_channels WHERE tenant_id=:tenant_id AND lower(name) LIKE 'cash%' LIMIT 1"
        ), {"tenant_id": str(tenant_id)}).first()
        cash_name = f"Cash ({currency})" if prior_cash else "Cash"
        db.execute(text("""
            INSERT INTO public.payment_channels(tenant_id,name,channel_type,provider,currency_code,active)
            VALUES(:tenant_id,:name,'CASH',NULL,:currency,true)
        """), {"tenant_id": str(tenant_id), "name": cash_name, "currency": currency})
        created.append("cash_payment_method")

    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    if created:
        write_audit(
            db, tenant_id=tenant_id, actor_user_id=actor_id,
            action="workspace.setup.initialize", target_type="tenant", target_id=tenant_id,
            correlation_id=request_id,
        )
        emit_event(
            db, tenant_id=tenant_id, event_type="workspace.setup.initialized",
            aggregate_type="tenant", aggregate_id=tenant_id, actor_user_id=actor_id,
            payload={"created_defaults": created}, correlation_id=request_id,
        )
    # Derive progress before commit: commit clears transaction-local RLS settings,
    # so a query after commit would incorrectly see an empty workspace under lexa_app.
    progress = _setup_progress_for_tenant(db, tenant_id)
    db.commit()
    return {
        "status": "COMPLETE" if progress["complete"] else "IN_PROGRESS",
        "created_defaults": created,
        "message": "Your business setup is ready." if not created else "Missing setup items have been added. Your existing records were kept.",
        "progress": progress,
    }
