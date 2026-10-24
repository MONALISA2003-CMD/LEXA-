"""Offline tests for the LEXA model catalogue and execution policy."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.intelligence.contracts import DataSensitivity, ProviderId, RoutingRequest, TaskType
from app.intelligence.model_registry import (
    MAX_ALLOWED_PAID_MODELS,
    MAX_MODEL_ENTRIES,
    ModelCostClass,
    ModelSpec,
    allowed_model_ids,
    load_model_registry,
    resolve_model,
)
from app.intelligence.policy import RouterPolicy, plan_model_route


def make_request(*, sensitivity=DataSensitivity.PUBLIC_SYNTHETIC, task=TaskType.EXPLAIN, provider=ProviderId.OPENROUTER, safe=True, summary=False):
    return RoutingRequest(
        task=task,
        sensitivity=sensitivity,
        provider_preference=provider,
        includes_business_summary=summary,
        input_safety_checked=safe,
        purpose_code="synthetic_model_registry_test",
    )


def make_policy(*, provider=ProviderId.OPENROUTER, paid=False, aggregate=False, confidential=False):
    return RouterPolicy(
        external_providers_enabled=True,
        allowed_providers=frozenset({provider}),
        paid_providers_enabled=paid,
        aggregate_external_enabled=aggregate,
        confidential_external_enabled=confidential,
    )


def test_registry_starts_with_current_adapter_defaults_and_no_model_allowlist(monkeypatch):
    monkeypatch.delenv("LEXA_AI_MODEL_REGISTRY_JSON", raising=False)
    monkeypatch.delenv("LEXA_AI_ALLOWED_MODELS", raising=False)
    models = load_model_registry(settings=SimpleNamespace())
    assert 1 <= len(models) <= MAX_MODEL_ENTRIES
    assert resolve_model(ProviderId.GEMINI, "gemini-3.8-flash", models) is not None
    assert resolve_model(ProviderId.OPENROUTER, "openrouter/free", models).cost_class == ModelCostClass.FREE_QUOTA
    assert allowed_model_ids(settings=SimpleNamespace()) == frozenset()


def test_free_model_requires_explicit_allowlist_and_public_synthetic_input():
    model = ModelSpec(
        provider_id=ProviderId.OPENROUTER,
        model_id="vendor/example:free",
        cost_class=ModelCostClass.FREE_QUOTA,
        pricing_verified=True,
    )
    registry = (model,)
    allowed = {model.registry_id}
    decision = plan_model_route(
        make_request(provider=ProviderId.OPENROUTER),
        make_policy(),
        {ProviderId.OPENROUTER}, model, registry, allowed,
    )
    assert decision.allowed is True
    assert decision.selected_provider == ProviderId.OPENROUTER
    assert decision.selected_model_id == "vendor/example:free"
    assert decision.external_data_transfer is True
    assert decision.automatic_fallbacks is False

    missing_allowlist = plan_model_route(
        make_request(provider=ProviderId.OPENROUTER),
        make_policy(),
        {ProviderId.OPENROUTER}, model, registry, set(),
    )
    assert missing_allowlist.allowed is False
    assert missing_allowlist.reason_code == "MODEL_NOT_ALLOWLISTED"


def test_free_trial_and_unknown_models_cannot_receive_real_business_data():
    for cost_class in (ModelCostClass.FREE_QUOTA, ModelCostClass.TRIAL_CREDIT, ModelCostClass.UNKNOWN):
        model = ModelSpec(ProviderId.OPENROUTER, f"vendor/model-{cost_class.value}", cost_class, pricing_verified=cost_class == ModelCostClass.FREE_QUOTA)
        decision = plan_model_route(
            make_request(sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS, provider=ProviderId.OPENROUTER),
            make_policy(confidential=True, paid=True),
            {ProviderId.OPENROUTER}, model, (model,), {model.registry_id},
        )
        assert decision.allowed is False
        assert decision.external_data_transfer is False
        assert decision.reason_code == "MODEL_RESTRICTED_TO_SYNTHETIC_DATA"


def test_personal_data_remains_blocked_even_for_paid_and_approved_models():
    model = ModelSpec(
        provider_id=ProviderId.OPENAI,
        model_id="account-approved-paid-model",
        cost_class=ModelCostClass.PAID,
        confidential_data_approved=True,
        aggregate_data_approved=True,
    )
    policy = make_policy(provider=ProviderId.OPENAI, paid=True, aggregate=True, confidential=True)
    for sensitivity in (DataSensitivity.PERSONAL_DATA, DataSensitivity.SENSITIVE_PERSONAL_DATA):
        decision = plan_model_route(
            make_request(sensitivity=sensitivity, provider=ProviderId.OPENAI),
            policy,
            {ProviderId.OPENAI}, model, (model,), {model.registry_id},
        )
        assert decision.allowed is False
        assert decision.reason_code == "PERSONAL_DATA_EXTERNAL_BLOCKED"
        assert decision.external_data_transfer is False


def test_paid_model_requires_both_paid_opt_in_and_provider_allowlist():
    model = ModelSpec(provider_id=ProviderId.OPENAI, model_id="approved-paid-model", cost_class=ModelCostClass.PAID)
    decision = plan_model_route(
        make_request(provider=ProviderId.OPENAI),
        make_policy(provider=ProviderId.OPENAI, paid=False),
        {ProviderId.OPENAI}, model, (model,), {model.registry_id},
    )
    assert decision.allowed is False
    assert decision.reason_code == "PAID_MODEL_OPT_IN_REQUIRED"


def test_included_business_summary_needs_model_level_aggregate_approval():
    model = ModelSpec(
        provider_id=ProviderId.OPENAI,
        model_id="paid-model-without-aggregate-approval",
        cost_class=ModelCostClass.PAID,
        confidential_data_approved=True,
        aggregate_data_approved=False,
    )
    decision = plan_model_route(
        make_request(sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS, provider=ProviderId.OPENAI, summary=True),
        make_policy(provider=ProviderId.OPENAI, paid=True, aggregate=True, confidential=True),
        {ProviderId.OPENAI}, model, (model,), {model.registry_id},
    )
    assert decision.allowed is False
    assert decision.reason_code == "MODEL_AGGREGATE_DATA_NOT_APPROVED"


def test_confidential_paid_model_needs_model_and_global_data_approval():
    model = ModelSpec(provider_id=ProviderId.OPENAI, model_id="approved-paid-model", cost_class=ModelCostClass.PAID, confidential_data_approved=True)
    allowed = {model.registry_id}
    request = make_request(sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS, provider=ProviderId.OPENAI)
    policy = make_policy(provider=ProviderId.OPENAI, paid=True, confidential=False)
    decision = plan_model_route(request, policy, {ProviderId.OPENAI}, model, (model,), allowed)
    assert decision.allowed is False
    assert decision.reason_code == "CONFIDENTIAL_EXTERNAL_NOT_APPROVED"

    policy = make_policy(provider=ProviderId.OPENAI, paid=True, confidential=True)
    decision = plan_model_route(request, policy, {ProviderId.OPENAI}, model, (model,), allowed)
    assert decision.allowed is True
    assert decision.selected_model_id == model.model_id


def test_model_task_allowlist_keeps_forecasting_on_local_python():
    model = ModelSpec(provider_id=ProviderId.GROQ, model_id="paid-model", cost_class=ModelCostClass.PAID)
    decision = plan_model_route(
        make_request(task=TaskType.FORECAST, provider=ProviderId.GROQ),
        make_policy(provider=ProviderId.GROQ, paid=True),
        {ProviderId.GROQ}, model, (model,), {model.registry_id},
    )
    assert decision.allowed is False
    assert decision.reason_code == "MODEL_TASK_UNSUPPORTED"


def test_dynamic_alias_is_restricted_to_synthetic_public_data():
    model = ModelSpec(ProviderId.OPENROUTER, "openrouter/free", ModelCostClass.FREE_QUOTA, dynamic_alias=True, pricing_verified=True)
    decision = plan_model_route(
        make_request(sensitivity=DataSensitivity.AGGREGATED_BUSINESS, provider=ProviderId.OPENROUTER),
        make_policy(provider=ProviderId.OPENROUTER, aggregate=True),
        {ProviderId.OPENROUTER}, model, (model,), {model.registry_id},
    )
    assert decision.allowed is False
    assert decision.reason_code == "MODEL_RESTRICTED_TO_SYNTHETIC_DATA"


@pytest.mark.parametrize("cost_class", [ModelCostClass.PAID, ModelCostClass.TRIAL_CREDIT, ModelCostClass.UNKNOWN])
def test_potentially_billable_model_allowlist_is_capped_at_four_entries(cost_class):
    provider_models = tuple(
        ModelSpec(ProviderId.OPENAI, f"model-{cost_class.value}-{index}", cost_class)
        for index in range(MAX_ALLOWED_PAID_MODELS + 1)
    )
    allowlist = {model.registry_id for model in provider_models}
    decision = plan_model_route(
        make_request(provider=ProviderId.OPENAI),
        make_policy(provider=ProviderId.OPENAI, paid=True),
        {ProviderId.OPENAI}, provider_models[0], provider_models, allowlist,
    )
    assert decision.allowed is False
    assert decision.reason_code == "PAID_MODEL_LIMIT_EXCEEDED"


def test_custom_registry_rejects_invalid_json_unverified_free_and_over_capacity():
    with pytest.raises(ValueError, match="valid JSON"):
        load_model_registry(settings=SimpleNamespace(lexa_ai_model_registry_json="not json"))
    with pytest.raises(ValueError, match="64 KB"):
        load_model_registry(settings=SimpleNamespace(lexa_ai_model_registry_json=" " * 64_001))

    unsafe_free = json.dumps([{"provider_id": "openrouter", "model_id": "vendor/test:free", "cost_class": "free_quota"}])
    with pytest.raises(ValueError, match="verify zero-priced"):
        load_model_registry(settings=SimpleNamespace(lexa_ai_model_registry_json=unsafe_free))

    alias_downgrade = json.dumps([{"provider_id": "openrouter", "model_id": "openrouter/free", "cost_class": "paid", "enabled": True}])
    with pytest.raises(ValueError, match="must remain verified free_quota"):
        load_model_registry(settings=SimpleNamespace(lexa_ai_model_registry_json=alias_downgrade))

    duplicate = json.dumps([
        {"provider_id": "groq", "model_id": "vendor/same", "cost_class": "unknown"},
        {"provider_id": "groq", "model_id": "vendor/same", "cost_class": "paid"},
    ])
    with pytest.raises(ValueError, match="repeats model ID"):
        load_model_registry(settings=SimpleNamespace(lexa_ai_model_registry_json=duplicate))

    too_many = [{"provider_id": "groq", "model_id": f"vendor/test-{index}", "cost_class": "unknown"} for index in range(MAX_MODEL_ENTRIES + 1)]
    with pytest.raises(ValueError, match="no more than 20"):
        load_model_registry(settings=SimpleNamespace(lexa_ai_model_registry_json=json.dumps(too_many)))


def test_free_model_registry_status_never_exposes_provider_secrets(monkeypatch):
    from app.intelligence.model_registry import model_registry_status
    monkeypatch.setenv("OPENROUTER_API_KEY", "never-return-this-key")
    monkeypatch.setenv("LEXA_AI_ALLOWED_MODELS", "openrouter:openrouter/free")
    status = model_registry_status(settings=SimpleNamespace())
    assert any(item["id"] == "openrouter:openrouter/free" for item in status)
    assert "never-return-this-key" not in json.dumps(status)


def test_assistant_route_is_policy_gated_before_any_adapter_call(monkeypatch):
    import app.routes.ai_assistant as ai_module
    from app.routes.ai_assistant import AssistRequest

    async def should_not_call(*args, **kwargs):
        raise AssertionError("provider adapter must never run for a blocked request")

    monkeypatch.delenv("LEXA_AI_ALLOWED_MODELS", raising=False)
    monkeypatch.delenv("LEXA_AI_ALLOWED_PROVIDERS", raising=False)
    monkeypatch.setenv("LEXA_AI_EXTERNAL_PROVIDERS_ENABLED", "false")
    monkeypatch.setattr(ai_module, "_generate", should_not_call)
    body = AssistRequest(provider="gemini", prompt="synthetic test question")
    with pytest.raises(HTTPException) as raised:
        asyncio.run(ai_module.assist(body, (None, uuid4(), uuid4(), None)))
    assert raised.value.status_code == 503
    assert raised.value.detail["code"] == "AI_POLICY_BLOCKED"


def test_registered_model_override_is_sent_to_mock_adapter_only(monkeypatch):
    import app.routes.ai_assistant as ai_module

    monkeypatch.setenv("OPENAI_API_KEY", "mock-only-secret")
    seen = {}

    async def fake_post_json(provider_id, url, headers, payload):
        seen.update(provider_id=provider_id, url=url, headers=headers, payload=payload)
        return {"output_text": "synthetic answer"}

    monkeypatch.setattr(ai_module, "_post_json", fake_post_json)
    model_id = "approved-model-id-from-registry"
    model, answer = asyncio.run(ai_module._generate("openai", "synthetic question", "read-only system message", model_override=model_id))
    assert model == model_id
    assert answer == "synthetic answer"
    assert seen["payload"]["model"] == model_id
    assert seen["payload"]["store"] is False
    assert seen["headers"]["Authorization"] == "Bearer mock-only-secret"
