from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ..auth import create_access_token, hash_password, verify_password, new_refresh_token, hash_refresh_token
from ..dependencies import get_db
from ..models import Tenant, TenantMembership, User, Session as AuthSession, Device, Role, MembershipRole, Permission, RolePermission
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: UUID
    device_key: str | None = None
    device_name: str | None = None
    platform: str | None = None

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if len(body.password) < 12:
        raise HTTPException(400, "Password must be at least 12 characters")
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "User already exists")
    tenant = Tenant(name=body.tenant_name.strip())
    user = User(email=email, password_hash=hash_password(body.password))
    db.add_all([tenant, user]); db.flush()
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant.id)})
    membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, status="ACTIVE")
    db.add(membership); db.flush()
    owner = Role(tenant_id=tenant.id, name="Owner", description="Initial tenant owner")
    db.add(owner); db.flush()
    db.add(MembershipRole(membership_id=membership.id, role_id=owner.id))
    # Owner starts with all currently defined permissions. Future permissions are
    # intentionally added through migrations rather than silently changing roles.
    permissions = db.scalars(select(Permission)).all()
    db.add_all([RolePermission(role_id=owner.id, permission_id=p.id) for p in permissions])
    db.commit()
    return {"user_id": user.id, "tenant_id": tenant.id}

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(body.tenant_id)})
    membership = None if not user else db.scalar(select(TenantMembership).where(TenantMembership.user_id == user.id, TenantMembership.tenant_id == body.tenant_id, TenantMembership.status == "ACTIVE"))
    if not user or not membership or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    device = None
    if body.device_key:
        device = db.scalar(select(Device).where(Device.tenant_id == body.tenant_id, Device.device_key == body.device_key))
        if not device:
            device = Device(tenant_id=body.tenant_id, user_id=user.id, device_key=body.device_key, name=body.device_name, platform=body.platform)
            db.add(device); db.flush()
    refresh = new_refresh_token()
    session = AuthSession(tenant_id=body.tenant_id, user_id=user.id, device_id=device.id if device else None, refresh_token_hash=hash_refresh_token(refresh), expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days))
    db.add(session); db.commit()
    return {"access_token": create_access_token(user.id, body.tenant_id, session.id), "refresh_token": refresh, "token_type": "bearer", "session_id": session.id}

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
