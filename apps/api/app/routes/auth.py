from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from decimal import Decimal
from uuid import UUID
from urllib.parse import urlsplit
from ipaddress import ip_address

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
import redis

from ..auth import create_access_token, hash_password, verify_password, new_refresh_token, hash_refresh_token, _set_refresh_cookie
from ..catalog_rules import request_hash
from ..dependencies import get_db, current_context, tenant_db
from ..db import SessionLocal
from ..models import (
    Tenant, TenantMembership, User, Session as AuthSession, Device,
    Role, MembershipRole, Permission, RolePermission, BusinessProfile,
    RegistrationRequest, Branch, Warehouse, Location, Category, Brand, Unit, Product, ProductVariant, PriceList, ProductPrice,
)
from ..catalog import emit_event, write_audit
from ..health import check_database
from ..config import settings
from ..email_delivery import send_password_reset_email

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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=256)

    @field_validator("token")
    @classmethod
    def normalize_token(cls, value: str) -> str:
        token = value.strip()
        if not token or any(ch.isspace() for ch in token):
            raise ValueError("Invalid reset token")
        return token



def _trusted_client_ip(request: Request) -> str:
    """Use the original client IP only from the authenticated same-origin proxy.

    Vercel supplies x-real-ip at its edge; the browser cannot authenticate the
    proxy-only header pair to Render without the server-side shared secret.
    Direct API clients fall back to the transport peer address.
    """
    expected = settings.lexa_proxy_shared_secret.strip()
    supplied = request.headers.get("x-lexa-proxy-secret", "")
    forwarded = request.headers.get("x-lexa-client-ip", "")
    if expected and supplied and forwarded and secrets.compare_digest(supplied, expected):
        try:
            return str(ip_address(forwarded.strip()))
        except ValueError:
            # An invalid value from the trusted proxy should not poison rate-limit keys.
            pass
    return request.client.host if request.client else "unknown"


def _enforce_registration_rate_limit(request: Request) -> None:
    ip = _trusted_client_ip(request)
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
    ip = _trusted_client_ip(request)
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
    client = None
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        client.delete(_login_rate_key(request, email))
    except Exception:
        logger.warning("login_rate_limit_clear_failed", extra={"request_id": getattr(request.state, "request_id", "untracked")})
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _increment_rate_limit(key: str, *, limit: int, window_seconds: int, message: str) -> None:
    client = None
    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window_seconds)
    except Exception as exc:
        logger.exception("auth_rate_limit_unavailable")
        raise HTTPException(503, "Account security is temporarily unavailable. Please try again shortly.") from exc
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    if count > limit:
        raise HTTPException(429, message)


def _enforce_password_reset_request_limit(request: Request, email: str) -> None:
    ip = _trusted_client_ip(request)
    # Keep email addresses out of Redis keys; hash the normalized address instead.
    email_digest = hashlib.sha256(email.lower().strip().encode("utf-8")).hexdigest()
    _increment_rate_limit(f"lexa:password-reset:ip:{ip}", limit=15, window_seconds=3600,
                          message="Too many password reset requests. Please try again later.")
    _increment_rate_limit(f"lexa:password-reset:email:{email_digest}", limit=4, window_seconds=3600,
                          message="Too many password reset requests. Please try again later.")


def _enforce_password_reset_completion_limit(request: Request) -> None:
    ip = _trusted_client_ip(request)
    _increment_rate_limit(f"lexa:password-reset-complete:ip:{ip}", limit=12, window_seconds=900,
                          message="Too many password reset attempts. Please request a new link later.")


def _password_reset_email_is_configured() -> bool:
    if not (settings.resend_api_key.strip() and settings.email_from.strip() and settings.public_app_url.strip()):
        return False
    # The browser reaches this endpoint through the Vercel same-origin proxy. In
    # production, require the shared secret so account reset throttling can use a
    # platform-derived client IP instead of grouping users by proxy egress IP.
    if settings.app_env.strip().lower() == "production" and len(settings.lexa_proxy_shared_secret.strip()) < 32:
        return False
    parsed = urlsplit(settings.public_app_url.strip())
    schemes = {"https"} if settings.app_env.strip().lower() == "production" else {"http", "https"}
    if (parsed.scheme.lower() not in schemes or not parsed.hostname or parsed.path not in {"", "/"}
            or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
        return False
    try:
        _ = parsed.port
    except ValueError:
        return False
    return True


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
    # Match the attributes used when issuing the cookie so sign-out/reset clears
    # the same secure, HttpOnly browser cookie in production.
    response.delete_cookie(
        "lexa_refresh_token", path="/",
        secure=settings.app_env.strip().lower() == "production",
        httponly=True, samesite="lax",
    )


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



def _deliver_password_reset_and_revoke_on_failure(email: str, reset_url: str, token_hash: str, request_id: str) -> None:
    """Deliver recovery mail after the HTTP response; revoke a token if delivery fails.

    Sending after the same generic HTTP response avoids making account existence
    observable through the response latency. The delivery function never logs the URL.
    """
    try:
        send_password_reset_email(email, reset_url)
    except Exception as exc:
        db = SessionLocal()
        try:
            db.execute(text("SELECT public.lexa_revoke_password_reset(:token_hash)"), {"token_hash": token_hash})
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("password_reset_cleanup_failed", extra={"request_id": request_id})
        finally:
            db.close()
        logger.error("password_reset_delivery_failed", extra={"request_id": request_id, "exception_type": type(exc).__name__})


@router.post("/forgot-password", status_code=202)
def forgot_password(body: ForgotPasswordRequest, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Issue a one-time reset link without disclosing whether an account exists.

    Password reset is deliberately unavailable until the outbound email provider is
    configured. That check happens before any account lookup, so it cannot enumerate users.
    """
    if not _password_reset_email_is_configured():
        raise HTTPException(503, "Password reset email is not configured yet. Please contact support.")

    email = body.email.lower().strip()
    _enforce_password_reset_request_limit(request, email)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_refresh_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_minutes)
    request_id = getattr(request.state, "request_id", None) or "untracked"

    try:
        issued = db.execute(
            text("SELECT user_id, email FROM public.lexa_issue_password_reset(:email, :token_hash, :expires_at)"),
            {"email": email, "token_hash": token_hash, "expires_at": expires_at},
        ).mappings().first()
        # Commit before delivery so the token is usable as soon as the email lands.
        db.commit()
        if issued:
            reset_url = f"{settings.public_app_url.rstrip('/')}/reset-password#token={raw_token}"
            background_tasks.add_task(_deliver_password_reset_and_revoke_on_failure, str(issued["email"]), reset_url, token_hash, request_id)
        return {"message": "If an active account matches that email, password reset instructions will be sent."}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("password_reset_request_failed", extra={"request_id": request_id, "exception_type": type(exc).__name__})
        # Keep the public response independent of account existence and database details.
        raise HTTPException(503, "Password reset is temporarily unavailable. Please try again shortly.") from exc


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Consume a single-use reset token, update the password and revoke all sessions."""
    _enforce_password_reset_completion_limit(request)
    password_digest = hash_password(body.new_password)
    token_hash = hash_refresh_token(body.token)
    try:
        consumed = bool(db.execute(
            text("SELECT public.lexa_consume_password_reset(:token_hash, :password_hash)"),
            {"token_hash": token_hash, "password_hash": password_digest},
        ).scalar_one())
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("password_reset_completion_failed", extra={"request_id": getattr(request.state, "request_id", "untracked"), "exception_type": type(exc).__name__})
        raise HTTPException(503, "Password reset is temporarily unavailable. Please request a new link later.") from exc
    if not consumed:
        raise HTTPException(400, "This reset link is invalid or expired. Request a new one.")
    _clear_refresh_cookie(response)
    return {"status": "password_updated", "message": "Your password has been updated. Sign in again on your devices."}


@router.get("/sessions")
def list_my_sessions(ctx=Depends(tenant_db)):
    """List active sessions for the signed-in user in the current workspace only."""
    db, user_id, tenant_id, current_session_id = ctx
    rows = db.execute(text("""
        SELECT s.id::text AS id, s.created_at, s.last_used_at, s.expires_at,
               COALESCE(d.name, 'Unknown device') AS device_name, d.platform,
               (s.id = :current_session_id) AS is_current
        FROM public.sessions s
        LEFT JOIN public.devices d ON d.id=s.device_id AND d.tenant_id=s.tenant_id AND d.user_id=s.user_id
        WHERE s.tenant_id=:tenant_id AND s.user_id=:user_id
          AND s.revoked_at IS NULL AND s.expires_at>now()
        ORDER BY (s.id=:current_session_id) DESC, COALESCE(s.last_used_at,s.created_at) DESC
        LIMIT 100
    """), {"tenant_id": str(tenant_id), "user_id": str(user_id), "current_session_id": str(current_session_id)}).mappings().all()
    return {"items": [dict(row) for row in rows]}


@router.post("/sessions/{session_id}/revoke")
def revoke_my_session(session_id: UUID, ctx=Depends(tenant_db)):
    """Revoke one of the caller's sessions in the current workspace."""
    db, user_id, tenant_id, current_session_id = ctx
    if session_id == current_session_id:
        raise HTTPException(409, "Use Sign out to end your current session.")
    result = db.execute(text("""
        UPDATE public.sessions SET revoked_at=now()
        WHERE id=:session_id AND tenant_id=:tenant_id AND user_id=:user_id
          AND revoked_at IS NULL AND expires_at>now()
        RETURNING id
    """), {"session_id": str(session_id), "tenant_id": str(tenant_id), "user_id": str(user_id)}).first()
    if not result:
        db.rollback()
        raise HTTPException(404, "Active session not found.")
    db.commit()
    return {"status": "revoked", "session_id": str(session_id)}


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
    db.info["lexa_tenant_id"] = str(tenant_id)
    db.info["lexa_user_id"] = str(user.id)
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
