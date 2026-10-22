import re
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    database_app_role: str = ""
    database_login_role: str = "lexa_runtime_login_p3"
    redis_url: str
    jwt_secret: str
    jwt_issuer: str = "lexa"
    jwt_audience: str = "lexa-web"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    # Per-process limits. The application uses Neon pooling, so these values
    # must be sized across all Render instances/workers, not per user account.
    database_pool_size: int = Field(default=5, ge=1, le=30)
    database_max_overflow: int = Field(default=5, ge=0, le=30)
    database_pool_timeout_seconds: int = Field(default=10, ge=1, le=60)
    database_pool_recycle_seconds: int = Field(default=900, ge=60, le=3600)
    cors_origins: str = "http://localhost:3000"
    lexa_neon_project_id: str = "wispy-mud-75323042"
    lexa_neon_branch_id: str = "br-soft-star-b1dj2m2w"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"): ]
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+psycopg://" + url[len("postgresql+psycopg2://"): ]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"): ]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


def validate_production_settings(*, app_env: str, database_app_role: str, jwt_secret: str, cors_origins: list[str], database_url: str | None = None, database_login_role: str = "lexa_runtime_login_p3") -> bool:
    if app_env.strip().lower() != "production":
        return True
    if database_app_role != "lexa_app":
        raise ValueError("DATABASE_APP_ROLE must be lexa_app in production")
    if len(jwt_secret) < 32:
        raise ValueError("JWT_SECRET must be at least 32 characters in production")
    if not cors_origins or any("localhost" in origin.lower() or origin == "*" for origin in cors_origins):
        raise ValueError("CORS_ORIGINS must contain only explicit production origins")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", database_login_role):
        raise ValueError("DATABASE_LOGIN_ROLE must be a simple PostgreSQL role identifier")
    if database_url is not None:
        parsed = urlsplit(database_url.strip())
        if "-pooler" not in (parsed.hostname or ""):
            raise ValueError("DATABASE_URL must use the Neon pooled endpoint in production")
        if unquote(parsed.username or "") != database_login_role:
            raise ValueError("DATABASE_URL username must match DATABASE_LOGIN_ROLE")
        sslmode = parse_qs(parsed.query).get("sslmode", [""])[0].lower()
        if sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("DATABASE_URL must require TLS in production")
    return True


settings = Settings()
validate_production_settings(
    app_env=settings.app_env,
    database_app_role=settings.database_app_role,
    jwt_secret=settings.jwt_secret,
    cors_origins=settings.cors_origin_list,
    database_url=settings.database_url,
    database_login_role=settings.database_login_role,
)
