"""Synthetic, no-network tests for LEXA Phase 1 intelligence contracts and routing."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.intelligence.contracts import (
    DataSensitivity,
    EngineType,
    EventType,
    IntelligenceEvent,
    InsightAvailability,
    InsightContract,
    ProviderId,
    RecommendedAction,
    RoutingRequest,
    TaskType,
)
from app.intelligence.policy import RouterPolicy, plan_route, policy_from_settings


def routing_request(
    *,
    task=TaskType.EXPLAIN,
    sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS,
    provider=ProviderId.GEMINI,
    includes_business_summary=False,
    input_safety_checked=True,
):
    return RoutingRequest(
        task=task,
        sensitivity=sensitivity,
        provider_preference=provider,
        includes_business_summary=includes_business_summary,
        input_safety_checked=input_safety_checked,
        purpose_code="synthetic_test",
    )


def fully_enabled_policy(**overrides):
    values = {
        "external_providers_enabled": True,
        "allowed_providers": frozenset({ProviderId.GEMINI, ProviderId.GROQ, ProviderId.OPENAI}),
        "paid_providers_enabled": False,
        "aggregate_external_enabled": False,
        "confidential_external_enabled": True,
    }
    values.update(overrides)
    return RouterPolicy(**values)


def test_policy_defaults_are_fail_closed():
    policy = RouterPolicy()
    decision = plan_route(
        routing_request(sensitivity=DataSensitivity.PUBLIC_SYNTHETIC),
        policy,
        configured_providers={ProviderId.GEMINI},
    )
    assert decision.allowed is False
    assert decision.reason_code == "EXTERNAL_PROVIDERS_DISABLED"
    assert decision.selected_provider is None
    assert decision.external_data_transfer is False
    assert decision.automatic_fallbacks is False


def test_settings_default_to_no_external_providers_and_empty_allowlist():
    settings = SimpleNamespace(
        lexa_ai_external_providers_enabled=False,
        lexa_ai_allowed_providers="",
        lexa_ai_paid_providers_enabled=False,
        lexa_ai_aggregates_external_enabled=False,
        lexa_ai_confidential_external_enabled=False,
    )
    policy = policy_from_settings(settings)
    assert policy.external_providers_enabled is False
    assert policy.allowed_providers == frozenset()
    assert policy.paid_providers_enabled is False
    assert policy.confidential_external_enabled is False


def test_allowlist_is_required_even_when_global_switch_is_on():
    decision = plan_route(
        routing_request(sensitivity=DataSensitivity.PUBLIC_SYNTHETIC),
        fully_enabled_policy(allowed_providers=frozenset({ProviderId.GROQ})),
        configured_providers={ProviderId.GEMINI, ProviderId.GROQ},
    )
    assert decision.allowed is False
    assert decision.reason_code == "PROVIDER_NOT_ALLOWLISTED"


def test_unclassified_free_text_is_blocked_even_when_provider_settings_are_enabled():
    decision = plan_route(
        routing_request(
            sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS,
            input_safety_checked=False,
        ),
        fully_enabled_policy(confidential_external_enabled=True),
        configured_providers={ProviderId.GEMINI},
    )
    assert decision.allowed is False
    assert decision.reason_code == "INPUT_CLASSIFICATION_REQUIRED"
    assert decision.external_data_transfer is False


def test_confidential_data_is_blocked_without_explicit_approval():
    decision = plan_route(
        routing_request(sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS),
        fully_enabled_policy(confidential_external_enabled=False),
        configured_providers={ProviderId.GEMINI},
    )
    assert decision.allowed is False
    assert decision.reason_code == "CONFIDENTIAL_EXTERNAL_NOT_APPROVED"


@pytest.mark.parametrize("sensitivity", [DataSensitivity.PERSONAL_DATA, DataSensitivity.SENSITIVE_PERSONAL_DATA])
def test_personal_data_is_never_sent_to_an_external_provider(sensitivity):
    policy = fully_enabled_policy(
        aggregate_external_enabled=True,
        confidential_external_enabled=True,
        paid_providers_enabled=True,
    )
    decision = plan_route(
        routing_request(sensitivity=sensitivity),
        policy,
        configured_providers={ProviderId.GEMINI},
    )
    assert decision.allowed is False
    assert decision.reason_code == "PERSONAL_DATA_EXTERNAL_BLOCKED"
    assert decision.external_data_transfer is False


def test_aggregate_summary_requires_its_own_opt_in_even_if_confidential_data_is_approved():
    decision = plan_route(
        routing_request(
            sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS,
            includes_business_summary=True,
        ),
        fully_enabled_policy(confidential_external_enabled=True, aggregate_external_enabled=False),
        configured_providers={ProviderId.GEMINI},
    )
    assert decision.allowed is False
    assert decision.reason_code == "AGGREGATE_EXTERNAL_NOT_APPROVED"


def test_paid_provider_requires_separate_paid_opt_in():
    decision = plan_route(
        routing_request(sensitivity=DataSensitivity.PUBLIC_SYNTHETIC, provider=ProviderId.OPENAI),
        fully_enabled_policy(),
        configured_providers={ProviderId.OPENAI},
    )
    assert decision.allowed is False
    assert decision.reason_code == "PAID_PROVIDER_OPT_IN_REQUIRED"


def test_provider_failure_has_no_automatic_fallback_in_route_contract():
    decision = plan_route(
        routing_request(sensitivity=DataSensitivity.PUBLIC_SYNTHETIC, provider=ProviderId.GEMINI),
        fully_enabled_policy(),
        configured_providers={ProviderId.GEMINI, ProviderId.GROQ},
    )
    assert decision.allowed is True
    assert decision.engine == EngineType.EXTERNAL_LLM
    assert decision.selected_provider == ProviderId.GEMINI
    assert decision.fallback_provider is None
    assert decision.automatic_fallbacks is False


def test_unknown_provider_preference_never_silently_switches_provider():
    decision = plan_route(
        routing_request(sensitivity=DataSensitivity.PUBLIC_SYNTHETIC, provider=ProviderId.GEMINI),
        fully_enabled_policy(allowed_providers=frozenset({ProviderId.GROQ})),
        configured_providers={ProviderId.GEMINI, ProviderId.GROQ},
    )
    assert decision.allowed is False
    assert decision.reason_code == "PROVIDER_NOT_ALLOWLISTED"
    assert decision.selected_provider is None


def test_deterministic_replenishment_does_not_need_external_ai():
    request = routing_request(task=TaskType.REPLENISHMENT, sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS)
    decision = plan_route(request, RouterPolicy(), configured_providers=set())
    assert decision.allowed is True
    assert decision.engine == EngineType.DETERMINISTIC
    assert decision.external_data_transfer is False
    assert decision.is_executable is True


def test_forecast_routes_to_local_python_without_needing_or_using_an_external_provider():
    decision = plan_route(
        routing_request(task=TaskType.FORECAST, sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS),
        RouterPolicy(),
        configured_providers=set(),
    )
    assert decision.allowed is True
    assert decision.engine == EngineType.PYTHON
    assert decision.reason_code == "LOCAL_PYTHON_BASELINE"
    assert decision.selected_provider is None
    assert decision.external_data_transfer is False
    assert decision.automatic_fallbacks is False
    assert decision.is_executable is True


def test_event_contract_accepts_versioned_non_free_text_envelope():
    event = IntelligenceEvent(
        event_id=uuid4(),
        event_type=EventType.SALE_COMPLETED,
        tenant_id=uuid4(),
        aggregate_type="sale",
        aggregate_id=uuid4(),
        occurred_at=datetime.now(timezone.utc),
        metadata={"business_date": "2026-10-24", "currency_code": "UGX", "record_count": 3},
    )
    assert event.schema_version == 1
    assert event.metadata.currency_code == "UGX"
    assert "metadata" in event.model_dump(mode="json")


def test_event_contract_rejects_pii_and_unbounded_free_text_fields():
    with pytest.raises(ValidationError):
        IntelligenceEvent(
            event_id=uuid4(),
            event_type=EventType.SALE_COMPLETED,
            tenant_id=uuid4(),
            aggregate_type="sale",
            aggregate_id=uuid4(),
            occurred_at=datetime.now(timezone.utc),
            metadata={"customer_email": "person@example.test"},
        )


def test_event_contract_requires_timezone_aware_timestamp():
    with pytest.raises(ValidationError):
        IntelligenceEvent(
            event_id=uuid4(),
            event_type=EventType.SALE_COMPLETED,
            tenant_id=uuid4(),
            aggregate_type="sale",
            aggregate_id=uuid4(),
            occurred_at=datetime(2026, 10, 24, 10, 0, 0),
        )


def test_available_insight_must_have_evidence_and_unavailable_insight_has_no_metric():
    common = {
        "insight_id": uuid4(),
        "tenant_id": uuid4(),
        "insight_type": "inventory.stock_risk",
        "availability": InsightAvailability.AVAILABLE,
        "title": "Stock risk",
        "summary": "Synthetic test insight.",
        "methodology": "Calculated from a synthetic test fixture.",
        "source_version": "test-v1",
    }
    with pytest.raises(ValidationError):
        InsightContract(**common)

    unavailable = dict(common)
    unavailable.update(availability=InsightAvailability.UNAVAILABLE, metrics=[{"label": "Items", "value": "2", "unit": "count"}])
    with pytest.raises(ValidationError):
        InsightContract(**unavailable)


def test_phase_one_action_contract_cannot_be_made_executable():
    with pytest.raises(ValidationError):
        RecommendedAction(
            action_code="purchase_order.create",
            label="Create purchase order",
            description="This should never execute in phase 1.",
            requires_human_approval=False,
            executable_in_phase1=True,
        )


def test_migration_contract_matches_python_task_and_engine_enums():
    repo_root = Path(__file__).resolve().parents[3]
    migration = (repo_root / "migrations/045_intelligence_foundation.sql").read_text(encoding="utf-8")
    for task in TaskType:
        assert f"'{task.value}'" in migration
    for engine in EngineType:
        assert f"'{engine.value}'" in migration
    assert "GRANT SELECT, INSERT ON TABLE public.intelligence_runs TO lexa_app;" in migration
    assert "intelligence_runs_provider_engine_ck" in migration
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.intelligence_jobs TO lexa_app;" in migration
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.intelligence_runs TO lexa_app;" not in migration


def test_migration_job_payload_is_field_allowlisted_and_bounded():
    repo_root = Path(__file__).resolve().parents[3]
    migration = (repo_root / "migrations/045_intelligence_foundation.sql").read_text(encoding="utf-8")
    assert "pg_column_size(payload_ref) <= 4096" in migration
    assert "payload_ref - ARRAY['business_date', 'currency_code', 'request_fingerprint', 'profile_code']" in migration
    assert "raw prompts" in migration
    assert "provider secrets" in migration
