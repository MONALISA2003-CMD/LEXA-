import os


def make_settings(url: str):
    os.environ["DATABASE_URL"] = url
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["JWT_SECRET"] = "test-secret"
    from apps.api.app.config import Settings
    return Settings(database_url=url, redis_url="redis://localhost:6379/0", jwt_secret="test-secret")


def test_postgresql_url_is_normalized_to_psycopg():
    settings = make_settings("postgresql://user:pass@host/db?sslmode=require")
    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in settings.sqlalchemy_database_url


def test_postgres_url_is_normalized_to_psycopg():
    settings = make_settings("postgres://user:pass@host/db")
    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")


def test_psycopg2_url_is_migrated_to_psycopg3():
    settings = make_settings("postgresql+psycopg2://user:pass@host/db")
    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")
