from datetime import datetime, timedelta, timezone
import logging
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password, verify_password, new_refresh_token, hash_refresh_token
from ..catalog_rules import request_hash
from ..dependencies import get_db
from ..models import (
    Tenant, TenantMembership, User, Session as AuthSession, Device,
    Role, MembershipRole, Permission, RolePermission, BusinessProfile,
    RegistrationRequest, Branch, Warehouse, Location, Category, Brand, Unit, Product, ProductVariant, PriceList, ProductPrice,
)
from ..catalog import emit_event, write_audit
from ..health import check_database
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("lexa.auth")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    tenant_name: str = Field(min_length=2, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: UUID | None = None
    device_key: str | None = None
    device_name: str | None = None
    platform: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


def _registration_key(value: str | None) -> str:
    if value is None or not value.strip():
        return secrets.token_urlsafe(24)
    value = value.strip()
    if len(value) > 200:
        raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")
    return value


def _registration_hash(body: RegisterRequest) -> str:
    return request_hash({
        "email": body.email.lower(),
        "password": body.password,
        "tenant_name": body.tenant_name.strip(),
    })



@router.post("/dev-session")
def dev_session(request: Request, db: Session = Depends(get_db)):
    """Create or restore a safe development workspace session.

    This route is intentionally unavailable in production and is only used while
    LEXA is being built. It still issues a normal session token, so tenant-scoped
    APIs and RLS continue to exercise their real authorization paths.
    """
    if settings.app_env.strip().lower() == "production" or not settings.lexa_open_dev_mode:
        raise HTTPException(404, "Not found")

    database_ready, database_error = check_database()
    if not database_ready:
        raise HTTPException(503, f"LEXA database is not ready: {database_error}")

    email = settings.lexa_open_dev_email.lower().strip()
    workspace_name = settings.lexa_open_dev_workspace_name.strip() or "LEXA Workspace"
    request_id = getattr(request.state, "request_id", None) or "untracked"

    try:
        user = db.scalar(select(User).where(User.email == email))
        tenant = None
        membership = None
        owner = None
        if user:
            membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == user.id, TenantMembership.status == "ACTIVE"))
            if membership:
                tenant = db.scalar(select(Tenant).where(Tenant.id == membership.tenant_id, Tenant.status == "ACTIVE"))

        if not user or not tenant or not membership:
            if not user:
                user = User(email=email, password_hash=hash_password(secrets.token_urlsafe(32)), is_active=True)
                db.add(user)
                db.flush()
            tenant = Tenant(name=workspace_name, status="ACTIVE")
            db.add(tenant)
            db.flush()
            db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant.id)})
            profile = BusinessProfile(tenant_id=tenant.id, legal_name=workspace_name, display_name=workspace_name, country_code="UG", currency_code="UGX")
            membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, status="ACTIVE")
            db.add_all([profile, membership])
            db.flush()
            owner = Role(tenant_id=tenant.id, name="Owner", description="Preview workspace owner")
            db.add(owner)
            db.flush()
            db.add(MembershipRole(membership_id=membership.id, role_id=owner.id))
            permissions = db.scalars(select(Permission)).all()
            if permissions:
                db.add_all([RolePermission(role_id=owner.id, permission_id=p.id) for p in permissions])
            db.flush()
        else:
            db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant.id)})

        # Keep one short-lived development session per preview user.
        now = datetime.now(timezone.utc)
        db.query(AuthSession).filter(
            AuthSession.user_id == user.id,
            AuthSession.tenant_id == tenant.id,
            AuthSession.revoked_at.is_(None),
        ).update({"revoked_at": now}, synchronize_session=False)
        refresh = new_refresh_token()
        session = AuthSession(
            tenant_id=tenant.id,
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(refresh),
            expires_at=now + timedelta(days=7),
        )
        db.add(session)
        db.flush()

        # Seed a small, reusable workspace only once. These are ordinary catalog
        # records and are visible through the same tenant/RLS paths as real data.
        if not db.scalar(select(Category.id).where(Category.tenant_id == tenant.id, Category.code == "PREVIEW")):
            category = Category(tenant_id=tenant.id, name="Everyday Products", code="PREVIEW", description="Sample catalog category")
            brand = Brand(tenant_id=tenant.id, name="LEXA Sample", code="LEXA")
            db.add_all([category, brand])
            db.flush()
            unit = db.scalar(select(Unit).where(Unit.tenant_id.is_(None), Unit.code == "PCS"))
            if not unit:
                raise HTTPException(503, "Workspace unit setup is unavailable")
            products = [
                ("Everyday Essentials", "Sample item for catalog review", "SKU-PREVIEW-001"),
                ("Premium Pack", "Sample variant for pricing and catalog review", "SKU-PREVIEW-002"),
                ("Starter Bundle", "Sample multi-item product", "SKU-PREVIEW-003"),
                ("Office Supply Set", "Sample business supply item", "SKU-PREVIEW-004"),
                ("Household Kit", "Sample household item", "SKU-PREVIEW-005"),
            ]
            for name, description, sku in products:
                product = Product(tenant_id=tenant.id, category_id=category.id, brand_id=brand.id, name=name, description=description, product_type="STOCKED", status="ACTIVE", has_variants=True, product_metadata={"preview": True})
                db.add(product)
                db.flush()
                variant = ProductVariant(tenant_id=tenant.id, product_id=product.id, name="Standard", sku=sku, base_unit_id=unit.id, track_inventory=True, allow_fractional_quantity=False, status="ACTIVE", costing_method="WEIGHTED_AVERAGE", variant_metadata={"preview": True})
                db.add(variant)
                db.flush()
                if sku.endswith("001"):
                    price_list = db.scalar(select(PriceList).where(PriceList.tenant_id == tenant.id, PriceList.name == "Retail"))
                    if not price_list:
                        price_list = PriceList(tenant_id=tenant.id, name="Retail", currency="UGX", price_type="RETAIL", status="ACTIVE", effective_from=now)
                        db.add(price_list)
                        db.flush()
                    db.add(ProductPrice(tenant_id=tenant.id, price_list_id=price_list.id, variant_id=variant.id, unit_price=Decimal("15000"), minimum_quantity=Decimal("1"), effective_from=now))

            branch = Branch(tenant_id=tenant.id, name="Main Branch", code="MAIN", status="ACTIVE")
            db.add(branch)
            db.flush()
            warehouse = Warehouse(tenant_id=tenant.id, branch_id=branch.id, name="Main Warehouse", code="MAIN-WH", status="ACTIVE")
            db.add(warehouse)
            db.flush()
            db.add(Location(tenant_id=tenant.id, warehouse_id=warehouse.id, name="Main Shelf", code="SHELF-01", status="ACTIVE"))

        write_audit(db, tenant_id=tenant.id, actor_user_id=user.id, action="workspace.dev_session", target_type="tenant", target_id=tenant.id, outcome="SUCCESS", correlation_id=request_id)
        db.commit()
        return {
            "access_token": create_access_token(user.id, tenant.id, session.id),
            "refresh_token": refresh,
            "token_type": "bearer",
            "session_id": session.id,
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
        }
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("development_session_database_failure", extra={"request_id": request_id})
        raise HTTPException(503, "LEXA could not prepare the workspace right now") from exc


@router.post("/register")
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    email = body.email.lower().strip()
    tenant_name = body.tenant_name.strip()
    if not tenant_name:
        raise HTTPException(400, "Business name is required")

    key = _registration_key(idempotency_key)
    digest = _registration_hash(body)

    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or "untracked"

    database_ready, database_error = check_database()
    if not database_ready:
        raise HTTPException(503, f"LEXA database is not ready: {database_error}")

    try:
        # Registration is pre-tenant, so its idempotency record intentionally lives
        # outside tenant RLS. The unique key makes retries and concurrent submits safe.
        stmt = insert(RegistrationRequest).values(
            idempotency_key=key,
            email=email,
            request_hash=digest,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ).on_conflict_do_nothing(index_elements=["idempotency_key"])
        db.execute(stmt)
        registration = db.scalar(
            select(RegistrationRequest)
            .where(RegistrationRequest.idempotency_key == key)
            .with_for_update()
        )
        if not registration:
            raise HTTPException(500, "Unable to establish registration request")
        if registration.request_hash != digest:
            raise HTTPException(409, "Idempotency-Key was already used with a different request")
        if registration.response_status is not None:
            return registration.response_body or {}

        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            raise HTTPException(409, "User already exists")

        tenant = Tenant(name=tenant_name)
        user = User(email=email, password_hash=hash_password(body.password))
        db.add_all([tenant, user])
        db.flush()

        # Set tenant context before any RLS-protected tenant-owned insert.
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant.id)})

        profile = BusinessProfile(
            tenant_id=tenant.id,
            legal_name=tenant_name,
            display_name=tenant_name,
            country_code="UG",
            currency_code="UGX",
        )
        membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, status="ACTIVE")
        db.add_all([profile, membership])
        db.flush()

        owner = Role(tenant_id=tenant.id, name="Owner", description="Initial tenant owner")
        db.add(owner)
        db.flush()
        db.add(MembershipRole(membership_id=membership.id, role_id=owner.id))

        permissions = db.scalars(select(Permission)).all()
        if permissions:
            db.add_all([RolePermission(role_id=owner.id, permission_id=p.id) for p in permissions])

        correlation_id = request_id
        write_audit(
            db,
            tenant_id=tenant.id,
            actor_user_id=user.id,
            action="workspace.create",
            target_type="tenant",
            target_id=tenant.id,
            outcome="SUCCESS",
            correlation_id=correlation_id,
        )
        emit_event(
            db,
            tenant_id=tenant.id,
            event_type="workspace.created",
            aggregate_type="tenant",
            aggregate_id=tenant.id,
            payload={"tenant_id": str(tenant.id), "user_id": str(user.id), "business_name": tenant_name},
            actor_user_id=user.id,
            correlation_id=correlation_id,
        )

        response = {"user_id": str(user.id), "tenant_id": str(tenant.id)}
        registration.response_status = 201
        registration.response_body = response
        registration.user_id = user.id
        registration.tenant_id = tenant.id
        db.commit()
        return response

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        # A concurrent registration for the same email is a client conflict, not a 500.
        if "users_email_key" in str(exc.orig) or "email" in str(exc.orig).lower():
            raise HTTPException(409, "User already exists") from exc
        raise HTTPException(409, "Workspace could not be created because of a data conflict") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("workspace_registration_database_failure", extra={"request_id": request_id, "email": email})
        raise HTTPException(503, detail={
            "code": "WORKSPACE_DATABASE_FAILURE",
            "message": "Workspace service could not complete the database transaction",
            "request_id": request_id,
        }) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("workspace_registration_unexpected_failure", extra={"request_id": request_id, "email": email})
        raise HTTPException(500, detail={
            "code": "WORKSPACE_REGISTRATION_FAILURE",
            "message": "Workspace creation failed. Please try again.",
            "request_id": request_id,
        }) from exc


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    tenant_id = body.tenant_id
    if tenant_id is None:
        rows = db.execute(
            text("SELECT tenant_id, tenant_name, membership_id FROM public.lexa_list_user_workspaces(:user_id)"),
            {"user_id": str(user.id)},
        ).mappings().all()
        if len(rows) == 0:
            raise HTTPException(401, "Invalid credentials")
        if len(rows) > 1:
            raise HTTPException(409, detail={
                "code": "WORKSPACE_SELECTION_REQUIRED",
                "message": "Choose a workspace to continue",
                "workspaces": [
                    {"tenant_id": str(row["tenant_id"]), "tenant_name": row["tenant_name"]}
                    for row in rows
                ],
            })
        tenant_id = UUID(str(rows[0]["tenant_id"]))

    request_id = getattr(request.state, "request_id", None) or "untracked"
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
    membership = db.scalar(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "ACTIVE",
        )
    )
    if not membership:
        raise HTTPException(401, "Invalid credentials")

    device = None
    if body.device_key:
        device = db.scalar(select(Device).where(Device.tenant_id == tenant_id, Device.device_key == body.device_key))
        if not device:
            device = Device(tenant_id=tenant_id, user_id=user.id, device_key=body.device_key, name=body.device_name, platform=body.platform)
            db.add(device)
            db.flush()
    refresh = new_refresh_token()
    session = AuthSession(
        tenant_id=tenant_id,
        user_id=user.id,
        device_id=device.id if device else None,
        refresh_token_hash=hash_refresh_token(refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
    )
    db.add(session)
    db.commit()
    logger.info("workspace_login_success", extra={"request_id": request_id, "tenant_id": str(tenant_id)})
    tenant = db.get(Tenant, tenant_id)
    return {
        "access_token": create_access_token(user.id, tenant_id, session.id),
        "refresh_token": refresh,
        "token_type": "bearer",
        "session_id": session.id,
        "tenant_id": str(tenant_id),
        "tenant_name": tenant.name if tenant else "Your workspace",
    }


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == token_hash, AuthSession.revoked_at.is_(None)))
    now = datetime.now(timezone.utc)
    if not session or session.expires_at <= now:
        raise HTTPException(401, "Invalid or expired refresh token")
    user = db.get(User, session.user_id)
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == session.user_id, TenantMembership.tenant_id == session.tenant_id, TenantMembership.status == "ACTIVE"))
    if not user or not user.is_active or not membership:
        raise HTTPException(401, "Session is no longer active")
    session.last_used_at = now
    new_refresh = new_refresh_token()
    session.refresh_token_hash = hash_refresh_token(new_refresh)
    db.commit()
    return {"access_token": create_access_token(user.id, session.tenant_id, session.id), "refresh_token": new_refresh, "token_type": "bearer", "session_id": session.id}


@router.post("/logout")
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == hash_refresh_token(body.refresh_token), AuthSession.revoked_at.is_(None)))
    if session:
        session.revoked_at = datetime.now(timezone.utc); db.commit()
    return {"status": "logged_out"}
