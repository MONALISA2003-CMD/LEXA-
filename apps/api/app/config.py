from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_issuer: str = "lexa"
    jwt_audience: str = "lexa-web"
    access_token_minutes: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
