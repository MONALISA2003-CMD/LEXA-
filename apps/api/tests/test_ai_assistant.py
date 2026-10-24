import asyncio
import json

import app.routes.ai_assistant as ai_module
from app.routes.ai_assistant import (
    _bounded_int,
    _extract_compatible_response,
    _extract_gemini_response,
    _extract_openai_response,
    provider_status,
)


def test_provider_status_never_returns_secret_values(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "never-return-this-secret")
    status = provider_status()
    gemini = next(item for item in status if item["id"] == "gemini")
    assert gemini["configured"] is True
    assert gemini["model"] == "gemini-3.8-flash"
    assert "never-return-this-secret" not in json.dumps(status)


def test_provider_status_marks_unconfigured_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    item = next(item for item in provider_status() if item["id"] == "openai")
    assert item["configured"] is False
    # Must match the current supported server default, not the removed placeholder model.
    assert item["model"] == "gpt-5-mini"


def test_openai_responses_api_text_extraction():
    assert _extract_openai_response({"output_text": "  hello  "}) == "hello"
    payload = {"output": [{"content": [{"type": "output_text", "text": "first"}, {"type": "output_text", "text": "second"}]}]}
    assert _extract_openai_response(payload) == "first\nsecond"


def test_openai_compatible_response_text_extraction():
    assert _extract_compatible_response({"choices": [{"message": {"content": "hello"}}]}) == "hello"
    assert _extract_compatible_response({"choices": [{"message": {"content": [{"text": "one"}, {"text": "two"}]}}]}) == "one\ntwo"
    assert _extract_compatible_response({}) == ""


def test_gemini_response_text_extraction():
    payload = {"candidates": [{"content": {"parts": [{"text": "one"}, {"text": "two"}]}}]}
    assert _extract_gemini_response(payload) == "one\ntwo"
    assert _extract_gemini_response({}) == ""


def test_output_token_setting_is_bounded(monkeypatch):
    monkeypatch.setenv("LEXA_AI_MAX_OUTPUT_TOKENS", "1")
    assert _bounded_int("LEXA_AI_MAX_OUTPUT_TOKENS", 500, 64, 1200) == 64
    monkeypatch.setenv("LEXA_AI_MAX_OUTPUT_TOKENS", "50000")
    assert _bounded_int("LEXA_AI_MAX_OUTPUT_TOKENS", 500, 64, 1200) == 1200
    monkeypatch.setenv("LEXA_AI_MAX_OUTPUT_TOKENS", "invalid")
    assert _bounded_int("LEXA_AI_MAX_OUTPUT_TOKENS", 500, 64, 1200) == 500


def test_openai_provider_uses_responses_api_with_storage_disabled(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-secret")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")
    seen = {}

    async def fake_post_json(provider_id, url, headers, payload):
        seen.update(provider_id=provider_id, url=url, headers=headers, payload=payload)
        return {"output_text": "safe advisory answer"}

    monkeypatch.setattr(ai_module, "_post_json", fake_post_json)
    model, answer = asyncio.run(ai_module._generate("openai", "question", "read-only instruction"))
    assert model == "gpt-6-luna"
    assert answer == "safe advisory answer"
    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert seen["headers"]["Authorization"] == "Bearer unit-test-secret"
    assert seen["payload"]["store"] is False
    assert seen["payload"]["max_output_tokens"] <= 1200


def test_cerebras_uses_documented_completion_token_parameter(monkeypatch):
    monkeypatch.setenv("CEREBRAS_API_KEY", "unit-test-secret")
    seen = {}

    async def fake_post_json(provider_id, url, headers, payload):
        seen.update(provider_id=provider_id, url=url, payload=payload)
        return {"choices": [{"message": {"content": "answer"}}]}

    monkeypatch.setattr(ai_module, "_post_json", fake_post_json)
    model, answer = asyncio.run(ai_module._generate("cerebras", "question", "read-only instruction"))
    assert model == "zai-glm-4.7"
    assert answer == "answer"
    assert seen["url"] == "https://api.cerebras.ai/v1/chat/completions"
    assert seen["payload"]["max_completion_tokens"] <= 1200
    assert "max_tokens" not in seen["payload"]
    assert seen["payload"]["reasoning_effort"] == "none"


def test_provider_settings_are_used_when_values_are_loaded_from_dotenv(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.setattr(ai_module.settings, "groq_api_key", "settings-loaded-secret", raising=False)
    monkeypatch.setattr(ai_module.settings, "groq_model", "settings-loaded-model", raising=False)
    item = next(item for item in provider_status() if item["id"] == "groq")
    assert item["configured"] is True
    assert item["model"] == "settings-loaded-model"
    assert "settings-loaded-secret" not in json.dumps(provider_status())
