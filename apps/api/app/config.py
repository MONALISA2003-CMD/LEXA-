from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_issuer: str = "lexa"
    jwt_audience: str = "lexa-web"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    cors_origins: str = "http://localhost:3000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
