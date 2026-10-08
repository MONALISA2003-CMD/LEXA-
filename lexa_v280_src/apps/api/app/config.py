from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    database_app_role: str = ""
    redis_url: str
    jwt_secret: str
    jwt_issuer: str = "lexa"
    jwt_audience: str = "lexa-web"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
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


def validate_production_settings(*, app_env: str, database_app_role: str, jwt_secret: str, cors_origins: list[str], database_url: str | None = None) -> bool:
    if app_env.strip().lower() != "production":
        return True
    if database_app_role != "lexa_app":
        raise ValueError("DATABASE_APP_ROLE must be lexa_app in production")
    if len(jwt_secret) < 32:
        raise ValueError("JWT_SECRET must be at least 32 characters in production")
    if not cors_origins or any("localhost" in origin.lower() or origin == "*" for origin in cors_origins):
        raise ValueError("CORS_ORIGINS must contain only explicit production origins")
    if database_url is not None and "-pooler" not in database_url:
        raise ValueError("DATABASE_URL must use the Neon pooled endpoint in production")
    return True


settings = Settings()
validate_production_settings(
    app_env=settings.app_env,
    database_app_role=settings.database_app_role,
    jwt_secret=settings.jwt_secret,
    cors_origins=settings.cors_origin_list,
    database_url=settings.database_url,
)
