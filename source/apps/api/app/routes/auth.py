from datetime import datetime, timedelta, timezone
import logging
import secrets
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
import redis

from ..auth import create_access_token, hash_password, verify_password, new_refresh_token, hash_refresh_token, _set_refresh_cookie
from ..catalog_rules import request_hash
from ..dependencies import get_db, current_context
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
    country_code: str = Field(default="UG", pattern=r"^[A-Z]{2}$")
    currency_code: str = Field(default="UGX", pattern=r"^[A-Z]{3}$")
    branch_name: str = Field(default="Main branch", min_length=2, max_length=200)
    warehouse_name: str = Field(default="Main warehouse", min_length=2, max_length=200)
    location_name: str = Field(default="Main location", min_length=2, max_length=200)

    @field_validator("tenant_name", "branch_name", "warehouse_name", "location_name")
    @classmethod
    def normalize_workspace_names(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Enter at least two characters.")
        return normalized

    @field_validator("country_code", "currency_code", mode="before")
    @classmethod
    def normalize_country_and_currency(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: UUID | None = None
    device_key: str | None = None
    device_name: str | None = None
    platform: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = None



def _enforce_registration_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"lexa:registration:{ip}"
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, 3600)
    except Exception as exc:
        logger.exception("registration_rate_limit_unavailable", extra={"request_id": getattr(request.state, "request_id", "untracked")})
        raise HTTPException(503, "Workspace service is temporarily unavailable. Please try again shortly.") from exc
    if count > 10:
        raise HTTPException(429, "Too many workspace creation attempts. Please try again later.")


def _login_rate_key(request: Request, email: str) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"lexa:login:{ip}:{email}"


def _enforce_login_rate_limit(request: Request, email: str) -> None:
    key = _login_rate_key(request, email)
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, 300)
    except Exception as exc:
        logger.exception("login_rate_limit_unavailable", extra={"request_id": getattr(request.state, "request_id", "untracked")})
        raise HTTPException(503, "Sign-in protection is temporarily unavailable. Please try again shortly.") from exc
    if count > 10:
        raise HTTPException(429, "Too many sign-in attempts. Please wait a few minutes and try again.")


def _clear_login_rate_limit(request: Request, email: str) -> None:
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.delete(_login_rate_key(request, email))
    except Exception:
        logger.warning("login_rate_limit_clear_failed", extra={"request_id": getattr(request.state, "request_id", "untracked")})


def _set_registration_rls_context(db: Session, *, email: str, registration_key: str) -> None:
    """Scope pre-tenant registration access to this email and one idempotency key.

    The Phase 3 forced-RLS policy requires all three transaction-local settings
    before registration_requests or the new user row can be read/written.
    """
    db.execute(
        text("SELECT set_config('app.pre_tenant_access', 'registration', true), "
             "set_config('app.pre_tenant_email', :email, true), "
             "set_config('app.registration_key', :registration_key, true)"),
        {"email": email, "registration_key": registration_key},
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie("lexa_refresh_token", path="/")


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
        "country_code": body.country_code,
        "currency_code": body.currency_code,
        "branch_name": body.branch_name.strip(),
        "warehouse_name": body.warehouse_name.strip(),
        "location_name": body.location_name.strip(),
    })



@router.post("/register")
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    email = body.email.lower().strip()
    _enforce_registration_rate_limit(request)
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
        # Establish the exact pre-tenant scope before the first RLS-protected write.
        # The idempotency key keeps this permission limited to this registration row.
        _set_registration_rls_context(db, email=email, registration_key=key)

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

        # Bind subsequent work to the newly created user and workspace. Keep the
        # narrow registration-key context until the registration result is committed.
        db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true), "
                 "set_config('app.user_id', :user_id, true)"),
            {"tenant_id": str(tenant.id), "user_id": str(user.id)},
        )

        profile = BusinessProfile(
            tenant_id=tenant.id,
            legal_name=tenant_name,
            display_name=tenant_name,
            country_code=body.country_code,
            currency_code=body.currency_code,
        )
        membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, status="ACTIVE")
        db.add_all([profile, membership])
        db.flush()

        # First-run defaults are created in the same transaction as the workspace.
        # A retry therefore cannot leave a tenant half-onboarded with no stock location.
        branch = Branch(tenant_id=tenant.id, name=body.branch_name, code="MAIN")
        db.add(branch)
        db.flush()
        warehouse = Warehouse(tenant_id=tenant.id, branch_id=branch.id, name=body.warehouse_name, code="MAIN")
        db.add(warehouse)
        db.flush()
        location = Location(tenant_id=tenant.id, warehouse_id=warehouse.id, name=body.location_name, code="MAIN")
        db.add(location)
        db.flush()

        owner = Role(tenant_id=tenant.id, name="Owner", description="Initial tenant owner")
        db.add(owner)
        db.flush()
        db.add(MembershipRole(membership_id=membership.id, role_id=owner.id))

        permissions = db.scalars(select(Permission)).all()
        if permissions:
            db.add_all([RolePermission(role_id=owner.id, permission_id=p.id) for p in permissions])
        db.flush()
        db.execute(text("SELECT lexa_seed_business_engine(:tenant_id)"), {"tenant_id": str(tenant.id)})

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
            payload={"tenant_id": str(tenant.id), "user_id": str(user.id), "business_name": tenant_name, "branch_id": str(branch.id), "warehouse_id": str(warehouse.id), "location_id": str(location.id)},
            actor_user_id=user.id,
            correlation_id=correlation_id,
        )

        response = {"user_id": str(user.id), "tenant_id": str(tenant.id), "branch_id": str(branch.id), "warehouse_id": str(warehouse.id), "location_id": str(location.id)}
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
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    _enforce_login_rate_limit(request, email)
    # Forced row-level security hides users before authentication unless the
    # pre-tenant login context is explicit. Scope that read to this normalized
    # email rather than attempting an unrestricted account lookup.
    db.execute(
        text("SELECT set_config('app.pre_tenant_access', 'login', true), set_config('app.pre_tenant_email', :email, true)"),
        {"email": email},
    )
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    # The workspace lookup is SECURITY DEFINER but still validates the
    # transaction-local user context. Establish that context before asking for
    # memberships; otherwise a valid active user is incorrectly returned zero
    # workspaces and the frontend reports a false credential failure.
    db.execute(
        text("SELECT set_config('app.user_id', :user_id, true), set_config('app.pre_tenant_access', '', true), set_config('app.pre_tenant_email', '', true)"),
        {"user_id": str(user.id)},
    )

    tenant_id = body.tenant_id
    if tenant_id is None:
        rows = db.execute(
            text("SELECT tenant_id, tenant_name, membership_id FROM public.lexa_list_active_user_workspaces(:user_id)"),
            {"user_id": str(user.id)},
        ).mappings().all()
        if len(rows) == 0:
            raise HTTPException(
                403,
                detail={
                    "code": "NO_ACTIVE_WORKSPACE",
                    "message": "This account has no active workspace. Ask your workspace administrator for access.",
                },
            )
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
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"),
        {"tenant_id": str(tenant_id), "user_id": str(user.id)},
    )
    membership = db.scalar(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "ACTIVE",
        )
    )
    active_tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "ACTIVE"))
    if not membership or not active_tenant:
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
    _clear_login_rate_limit(request, email)
    logger.info("workspace_login_success", extra={"request_id": request_id, "tenant_id": str(tenant_id)})
    tenant = db.get(Tenant, tenant_id)
    _set_refresh_cookie(response, refresh)
    return {
        "access_token": create_access_token(user.id, tenant_id, session.id),
        "token_type": "bearer",
        "session_id": session.id,
        "tenant_id": str(tenant_id),
        "tenant_name": tenant.name if tenant else "Your workspace",
    }


@router.get("/me")
def current_identity(context=Depends(current_context), db: Session = Depends(get_db)):
    user_id, tenant_id, session_id = context
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"),
        {"tenant_id": str(tenant_id), "user_id": str(user_id)},
    )
    session = db.scalar(select(AuthSession).where(
        AuthSession.id == session_id,
        AuthSession.tenant_id == tenant_id,
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    ))
    user = db.get(User, user_id)
    tenant = db.get(Tenant, tenant_id)
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.user_id == user_id,
        TenantMembership.status == "ACTIVE",
    ))
    now = datetime.now(timezone.utc)
    if not session or session.expires_at <= now or not user or not user.is_active or not tenant or tenant.status != "ACTIVE" or not membership:
        raise HTTPException(401, "Your session or workspace is no longer active")
    roles = db.execute(text("""
        SELECT DISTINCT r.name FROM membership_roles mr
        JOIN roles r ON r.id = mr.role_id AND r.tenant_id = :tenant_id
        WHERE mr.membership_id = :membership_id ORDER BY r.name
    """), {"tenant_id": str(tenant_id), "membership_id": str(membership.id)}).scalars().all()
    permissions = db.execute(text("""
        SELECT DISTINCT p.code FROM membership_roles mr
        JOIN roles r ON r.id = mr.role_id AND r.tenant_id = :tenant_id
        JOIN role_permissions rp ON rp.role_id = r.id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE mr.membership_id = :membership_id ORDER BY p.code
    """), {"tenant_id": str(tenant_id), "membership_id": str(membership.id)}).scalars().all()
    return {
        "user": {"id": str(user.id), "email": user.email, "is_active": user.is_active},
        "workspace": {"id": str(tenant.id), "name": tenant.name, "status": tenant.status},
        "membership": {"id": str(membership.id), "status": membership.status},
        "roles": roles,
        "permissions": permissions,
    }


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db), body: RefreshRequest | None = None):
    refresh_token = request.cookies.get("lexa_refresh_token") or (body.refresh_token if body else None)
    if not refresh_token:
        raise HTTPException(401, "Authentication session expired")
    token_hash = hash_refresh_token(refresh_token)
    # sessions is RLS-protected by tenant_id, but the tenant is not known until
    # the opaque cookie is looked up. This SECURITY DEFINER function returns
    # only the minimal identifiers needed to establish tenant context.
    lookup = db.execute(
        text("SELECT session_id, tenant_id, user_id FROM public.lexa_find_session_by_refresh_hash(:token_hash)"),
        {"token_hash": token_hash},
    ).mappings().first()
    if not lookup:
        raise HTTPException(401, "Invalid or expired refresh token")
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"),
        {"tenant_id": str(lookup["tenant_id"]), "user_id": str(lookup["user_id"])},
    )
    session = db.scalar(select(AuthSession).where(
        AuthSession.id == lookup["session_id"],
        AuthSession.tenant_id == lookup["tenant_id"],
        AuthSession.user_id == lookup["user_id"],
        AuthSession.refresh_token_hash == token_hash,
        AuthSession.revoked_at.is_(None),
    ).with_for_update())
    now = datetime.now(timezone.utc)
    if not session or session.expires_at <= now:
        raise HTTPException(401, "Invalid or expired refresh token")
    user = db.get(User, session.user_id)
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == session.user_id, TenantMembership.tenant_id == session.tenant_id, TenantMembership.status == "ACTIVE"))
    tenant = db.get(Tenant, session.tenant_id)
    if not user or not user.is_active or not membership or not tenant or tenant.status != "ACTIVE":
        raise HTTPException(401, "Session is no longer active")
    session.last_used_at = now
    new_refresh = new_refresh_token()
    session.refresh_token_hash = hash_refresh_token(new_refresh)
    db.commit()
    _set_refresh_cookie(response, new_refresh)
    return {
        "access_token": create_access_token(user.id, session.tenant_id, session.id),
        "token_type": "bearer",
        "session_id": session.id,
        "tenant_id": str(session.tenant_id),
        "tenant_name": tenant.name if tenant else "Your workspace",
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db), body: RefreshRequest | None = None):
    refresh_token = request.cookies.get("lexa_refresh_token") or (body.refresh_token if body else None)
    if refresh_token:
        token_hash = hash_refresh_token(refresh_token)
        lookup = db.execute(
            text("SELECT session_id, tenant_id, user_id FROM public.lexa_find_session_by_refresh_hash(:token_hash)"),
            {"token_hash": token_hash},
        ).mappings().first()
        if lookup:
            db.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true), set_config('app.user_id', :user_id, true)"),
                {"tenant_id": str(lookup["tenant_id"]), "user_id": str(lookup["user_id"])},
            )
            session = db.scalar(select(AuthSession).where(
                AuthSession.id == lookup["session_id"],
                AuthSession.tenant_id == lookup["tenant_id"],
                AuthSession.user_id == lookup["user_id"],
                AuthSession.refresh_token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
            ).with_for_update())
            if session:
                session.revoked_at = datetime.now(timezone.utc)
                db.commit()
    _clear_refresh_cookie(response)
    return {"status": "logged_out"}
