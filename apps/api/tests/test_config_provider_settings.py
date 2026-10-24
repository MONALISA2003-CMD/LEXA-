"""Regression checks for provider settings fields and the default-deny AI policy."""

from app.config import Settings


def test_provider_settings_are_loaded_from_dotenv_without_enabling_external_ai(tmp_path, monkeypatch):
    # Process variables take precedence over .env; clear relevant names so this
    # test proves the dotenv path itself works in CI as well as locally.
    names = (
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "LEXA_AI_EXTERNAL_PROVIDERS_ENABLED",
        "LEXA_AI_ALLOWED_PROVIDERS",
        "LEXA_AI_PAID_PROVIDERS_ENABLED",
        "LEXA_AI_AGGREGATES_EXTERNAL_ENABLED",
        "LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "APP_ENV=development",
                "DATABASE_URL=postgresql+psycopg://lexa:lexa@localhost:5432/lexa",
                "REDIS_URL=redis://localhost:6379/0",
                "JWT_SECRET=local-ci-only-secret-at-least-32-characters-long",
                "GROQ_API_KEY=dotenv-groq-secret",
                "GROQ_MODEL=dotenv-groq-model",
                "LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=false",
                "LEXA_AI_ALLOWED_PROVIDERS=",
                "LEXA_AI_PAID_PROVIDERS_ENABLED=false",
                "LEXA_AI_AGGREGATES_EXTERNAL_ENABLED=false",
                "LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED=false",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)
    assert settings.groq_api_key == "dotenv-groq-secret"
    assert settings.groq_model == "dotenv-groq-model"
    assert settings.lexa_ai_external_providers_enabled is False
    assert settings.lexa_ai_allowed_providers == ""
    assert settings.lexa_ai_paid_providers_enabled is False
    assert settings.lexa_ai_aggregates_external_enabled is False
    assert settings.lexa_ai_confidential_external_enabled is False
