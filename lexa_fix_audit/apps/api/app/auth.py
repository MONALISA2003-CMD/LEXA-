from datetime import datetime, timedelta, timezone
import hashlib, secrets
from uuid import UUID
import jwt
from pwdlib import PasswordHash
from .config import settings

password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)

def create_access_token(user_id: UUID, tenant_id: UUID, session_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "tenant_id": str(tenant_id), "sid": str(session_id), "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes), "iss": settings.jwt_issuer, "aud": settings.jwt_audience}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer, audience=settings.jwt_audience)

def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
