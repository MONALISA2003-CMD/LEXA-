"""LEXA-owned AI policy router.

This module only decides whether a route is permitted. It does not perform network
calls, retry providers, inspect business tables, or execute transactions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .contracts import (
    DataSensitivity,
    EngineType,
    ProviderId,
    RouterDecision,
    RoutingRequest,
    TaskType,
)

POLICY_VERSION = "phase1-v1"

# Providers that must never be selected without a separate explicit paid-use opt-in.
PAID_PROVIDER_IDS = frozenset({ProviderId.OPENAI, ProviderId.OPENROUTER, ProviderId.CEREBRAS, ProviderId.HUGGINGFACE})
PROVIDER_KEY_ENV = {
    ProviderId.GEMINI: "GEMINI_API_KEY",
    ProviderId.GROQ: "GROQ_API_KEY",
    ProviderId.CEREBRAS: "CEREBRAS_API_KEY",
    ProviderId.OPENROUTER: "OPENROUTER_API_KEY",
    ProviderId.HUGGINGFACE: "HUGGINGFACE_API_KEY",
    ProviderId.OPENAI: "OPENAI_API_KEY",
}

# Ordered preferences are used only to choose a provider for a new request. They
# are NOT retry/fallback orders after a provider fails.
TASK_PROVIDER_PROFILES: dict[TaskType, tuple[ProviderId, ...]] = {
    TaskType.CLASSIFY: (ProviderId.GEMINI, ProviderId.GROQ),
    TaskType.EXTRACT: (ProviderId.GEMINI, ProviderId.GROQ),
    TaskType.EXPLAIN: (ProviderId.GEMINI, ProviderId.GROQ, ProviderId.OPENAI, ProviderId.CEREBRAS, ProviderId.OPENROUTER, ProviderId.HUGGINGFACE),
    TaskType.SUMMARIZE: (ProviderId.GEMINI, ProviderId.GROQ, ProviderId.OPENAI, ProviderId.CEREBRAS, ProviderId.OPENROUTER, ProviderId.HUGGINGFACE),
    TaskType.ANALYZE: (ProviderId.GROQ, ProviderId.GEMINI, ProviderId.OPENAI, ProviderId.CEREBRAS, ProviderId.OPENROUTER, ProviderId.HUGGINGFACE),
    TaskType.RECONCILE: (ProviderId.GEMINI, ProviderId.GROQ),
    TaskType.DAILY_BRIEF: (ProviderId.GEMINI, ProviderId.GROQ, ProviderId.OPENAI, ProviderId.CEREBRAS, ProviderId.OPENROUTER, ProviderId.HUGGINGFACE),
}
DETERMINISTIC_TASKS = frozenset({TaskType.BUSINESS_INSIGHT, TaskType.REPLENISHMENT})
# Forecasting is a local Python baseline. It does not require an external provider.
PYTHON_TASKS = frozenset({TaskType.FORECAST})
NOT_IMPLEMENTED_TASKS: frozenset[TaskType] = frozenset()


@dataclass(frozen=True, slots=True)
class RouterPolicy:
    external_providers_enabled: bool = False
    allowed_providers: frozenset[ProviderId] = frozenset()
    paid_providers_enabled: bool = False
    aggregate_external_enabled: bool = False
    confidential_external_enabled: bool = False
    policy_version: str = POLICY_VERSION


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _provider_ids(value: Any) -> frozenset[ProviderId]:
    if value is None:
        return frozenset()
    if isinstance(value, (list, tuple, set, frozenset)):
        raw_values = value
    else:
        raw_values = str(value).split(",")
    parsed: set[ProviderId] = set()
    for raw in raw_values:
        candidate = str(raw).strip().lower()
        if not candidate:
            continue
        try:
            parsed.add(ProviderId(candidate))
        except ValueError:
            # Unknown provider strings fail closed rather than expanding routing.
            continue
    return frozenset(parsed)


def policy_from_settings(settings: Any) -> RouterPolicy:
    """Build policy from explicit, server-side settings; defaults are fail-closed."""
    return RouterPolicy(
        external_providers_enabled=_as_bool(getattr(settings, "lexa_ai_external_providers_enabled", False)),
        allowed_providers=_provider_ids(getattr(settings, "lexa_ai_allowed_providers", "")),
        paid_providers_enabled=_as_bool(getattr(settings, "lexa_ai_paid_providers_enabled", False)),
        aggregate_external_enabled=_as_bool(getattr(settings, "lexa_ai_aggregates_external_enabled", False)),
        confidential_external_enabled=_as_bool(getattr(settings, "lexa_ai_confidential_external_enabled", False)),
    )


def configured_provider_ids(env: Any | None = None) -> frozenset[ProviderId]:
    """Return configured provider IDs without ever returning or logging key values."""
    if env is None:
        import os

        env = os.environ
    configured: set[ProviderId] = set()
    for provider, env_name in PROVIDER_KEY_ENV.items():
        if str(env.get(env_name, "")).strip():
            configured.add(provider)
    return frozenset(configured)


def _blocked(request: RoutingRequest, reason: str, policy: RouterPolicy) -> RouterDecision:
    return RouterDecision(
        policy_version=policy.policy_version,
        task=request.task,
        allowed=False,
        engine=EngineType.NONE,
        reason_code=reason,
        sensitivity=request.sensitivity,
        selected_provider=None,
        fallback_provider=None,
        automatic_fallbacks=False,
        external_data_transfer=False,
        is_executable=False,
    )


def plan_route(
    request: RoutingRequest,
    policy: RouterPolicy,
    configured_providers: Iterable[ProviderId] = (),
) -> RouterDecision:
    """Plan exactly one permitted route, default-denying external transfer.

    No provider is called here. A returned external route represents policy approval
    for one named provider and must still be executed through the server adapter.
    There is deliberately no automatic fallback provider.
    """
    if request.task in DETERMINISTIC_TASKS:
        return RouterDecision(
            policy_version=policy.policy_version,
            task=request.task,
            allowed=True,
            engine=EngineType.DETERMINISTIC,
            reason_code="DETERMINISTIC_PATH",
            sensitivity=request.sensitivity,
            selected_provider=None,
            fallback_provider=None,
            automatic_fallbacks=False,
            external_data_transfer=False,
            is_executable=True,
        )

    if request.task in PYTHON_TASKS:
        return RouterDecision(
            policy_version=policy.policy_version,
            task=request.task,
            allowed=True,
            engine=EngineType.PYTHON,
            reason_code="LOCAL_PYTHON_BASELINE",
            sensitivity=request.sensitivity,
            selected_provider=None,
            fallback_provider=None,
            automatic_fallbacks=False,
            external_data_transfer=False,
            is_executable=True,
        )

    if request.task in NOT_IMPLEMENTED_TASKS:
        return _blocked(request, "CAPABILITY_NOT_IMPLEMENTED", policy)

    if not policy.external_providers_enabled:
        return _blocked(request, "EXTERNAL_PROVIDERS_DISABLED", policy)

    # Personally identifiable and sensitive personal data are never routed to an
    # external model by this policy, even when a tenant/admin asks for it.
    if request.sensitivity in {DataSensitivity.PERSONAL_DATA, DataSensitivity.SENSITIVE_PERSONAL_DATA}:
        return _blocked(request, "PERSONAL_DATA_EXTERNAL_BLOCKED", policy)
    # Only a trusted server-side classifier/redaction stage may set this true. The
    # legacy free-text endpoint deliberately leaves it false in Phase 1.
    if not request.input_safety_checked:
        return _blocked(request, "INPUT_CLASSIFICATION_REQUIRED", policy)
    if request.sensitivity == DataSensitivity.AGGREGATED_BUSINESS and not policy.aggregate_external_enabled:
        return _blocked(request, "AGGREGATE_EXTERNAL_NOT_APPROVED", policy)
    if request.includes_business_summary and not policy.aggregate_external_enabled:
        return _blocked(request, "AGGREGATE_EXTERNAL_NOT_APPROVED", policy)
    if request.sensitivity == DataSensitivity.CONFIDENTIAL_BUSINESS and not policy.confidential_external_enabled:
        return _blocked(request, "CONFIDENTIAL_EXTERNAL_NOT_APPROVED", policy)

    profile = TASK_PROVIDER_PROFILES.get(request.task)
    if not profile:
        return _blocked(request, "NO_PROVIDER_PROFILE", policy)

    if request.provider_preference is not None:
        if request.provider_preference not in profile:
            return _blocked(request, "PROVIDER_NOT_SUPPORTED_FOR_TASK", policy)
        candidates = (request.provider_preference,)
    else:
        candidates = profile

    configured = frozenset(configured_providers)
    for candidate in candidates:
        if candidate not in policy.allowed_providers:
            if request.provider_preference is not None:
                return _blocked(request, "PROVIDER_NOT_ALLOWLISTED", policy)
            continue
        if candidate not in configured:
            if request.provider_preference is not None:
                return _blocked(request, "PROVIDER_NOT_CONFIGURED", policy)
            continue
        if candidate in PAID_PROVIDER_IDS and not policy.paid_providers_enabled:
            if request.provider_preference is not None:
                return _blocked(request, "PAID_PROVIDER_OPT_IN_REQUIRED", policy)
            continue
        return RouterDecision(
            policy_version=policy.policy_version,
            task=request.task,
            allowed=True,
            engine=EngineType.EXTERNAL_LLM,
            reason_code="POLICY_APPROVED_SINGLE_PROVIDER",
            sensitivity=request.sensitivity,
            selected_provider=candidate,
            fallback_provider=None,
            automatic_fallbacks=False,
            external_data_transfer=True,
            is_executable=True,
        )

    return _blocked(request, "NO_ELIGIBLE_CONFIGURED_PROVIDER", policy)
