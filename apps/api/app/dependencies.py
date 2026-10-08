from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .auth import decode_access_token
from .db import SessionLocal
from .models import TenantMembership, Session as AuthSession

bearer = HTTPBearer(auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def current_context(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
        return UUID(payload["sub"]), UUID(payload["tenant_id"]), UUID(payload["sid"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc

def tenant_db(db: Session = Depends(get_db), context=Depends(current_context)):
    user_id, tenant_id, session_id = context
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.tenant_id == tenant_id, AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)))
    if not session:
        raise HTTPException(status_code=401, detail="Session is revoked or invalid")
    membership = db.scalar(select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.user_id == user_id,
        TenantMembership.status == "ACTIVE",
    ))
    if not membership:
        raise HTTPException(status_code=403, detail="Active tenant membership required")
    return db, user_id, tenant_id, session_id

def require_permission(permission_code: str):
    def dependency(ctx=Depends(tenant_db)):
        db, user_id, tenant_id, session_id = ctx
        row = db.execute(text("""
          SELECT 1 FROM membership_roles mr
          JOIN roles r ON r.id = mr.role_id AND r.tenant_id = :tenant_id
          JOIN role_permissions rp ON rp.role_id = r.id
          JOIN permissions p ON p.id = rp.permission_id AND p.code = :code
          JOIN tenant_memberships tm ON tm.id = mr.membership_id
          WHERE tm.user_id = :user_id AND tm.tenant_id = :tenant_id
            AND tm.status = 'ACTIVE'
          LIMIT 1
        """), {"code": permission_code, "user_id": str(user_id), "tenant_id": str(tenant_id)}).first()
        if not row:
            raise HTTPException(status_code=403, detail=f"Permission required: {permission_code}")
        return ctx
    return dependency
