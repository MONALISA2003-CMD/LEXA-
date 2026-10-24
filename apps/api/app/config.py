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
    resend_api_key: str = ""
    email_from: str = ""
    lexa_proxy_shared_secret: str = ""
    public_app_url: str = "https://lexa-green.vercel.app"
    password_reset_minutes: int = Field(default=20, ge=5, le=60)
    email_timeout_seconds: int = Field(default=8, ge=2, le=20)
    database_pool_size: int = Field(default=5, ge=1, le=30)
    database_max_overflow: int = Field(default=5, ge=0, le=30)
    database_pool_timeout_seconds: int = Field(default=10, ge=1, le=60)
    database_pool_recycle_seconds: int = Field(default=900, ge=60, le=3600)
    cors_origins: str = "http://localhost:3000"
    lexa_neon_project_id: str = "wispy-mud-75323042"
    lexa_neon_branch_id: str = "br-soft-star-b1dj2m2w"

    # Provider credentials are server-side only. Empty keys never route.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    cerebras_api_key: str = ""
    cerebras_model: str = "zai-glm-4.7"
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/free"
    huggingface_api_key: str = ""
    huggingface_model: str = "Qwen/Qwen3-32B"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    # External answers are enabled for approved, question-only assistance by
    # default. The allowlist stays limited to Gemini/Groq; keys must be supplied
    # separately on the API service. Paid providers and business-data sharing stay off.
    lexa_ai_external_providers_enabled: bool = True
    lexa_ai_allowed_providers: str = "gemini,groq"
    lexa_ai_paid_providers_enabled: bool = False
    lexa_ai_aggregates_external_enabled: bool = False
    lexa_ai_confidential_external_enabled: bool = False
    lexa_ai_requests_per_minute: int = Field(default=10, ge=1, le=60)
    lexa_ai_max_output_tokens: int = Field(default=300, ge=64, le=500)
    lexa_ai_max_input_chars: int = Field(default=2400, ge=100, le=2400)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+psycopg://" + url[len("postgresql+psycopg2://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


def validate_production_settings(
    *, app_env: str, database_app_role: str, jwt_secret: str,
    cors_origins: list[str], database_url: str | None = None,
    database_login_role: str = "lexa_runtime_login_p3",
    public_app_url: str | None = None,
    lexa_proxy_shared_secret: str | None = None,
) -> bool:
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
    if len((lexa_proxy_shared_secret or "").strip()) < 32:
        raise ValueError("LEXA_PROXY_SHARED_SECRET must be set to the same random value (at least 32 characters) in Vercel and Render in production")
    if public_app_url is not None:
        public_url = urlsplit(public_app_url.strip())
        expected_schemes = {"https"} if app_env.strip().lower() == "production" else {"http", "https"}
        if (public_url.scheme.lower() not in expected_schemes or not public_url.hostname
                or public_url.path not in {"", "/"}
                or public_url.username is not None or public_url.password is not None
                or public_url.query or public_url.fragment):
            raise ValueError("PUBLIC_APP_URL must be a valid trusted origin/base URL; production requires HTTPS without credentials, query, or fragment")
        try:
            _ = public_url.port
        except ValueError as exc:
            raise ValueError("PUBLIC_APP_URL contains an invalid port") from exc
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
    public_app_url=settings.public_app_url,
    lexa_proxy_shared_secret=settings.lexa_proxy_shared_secret,
)
