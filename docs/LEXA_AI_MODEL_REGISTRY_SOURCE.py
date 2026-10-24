"""LEXA's model-level registry. This module never calls external services.

The registry is intentionally conservative:
- provider keys stay server-side;
- up to 20 model entries may be registered;
- at most four paid models may be allowlisted at one time;
- free/trial/unknown models are restricted to synthetic public input;
- provider/model IDs are matched against server-side registry entries, never used
  to construct an endpoint URL supplied by a request.

LEXA_AI_MODEL_REGISTRY_JSON accepts an optional JSON array of model records. The
records are administrator-controlled environment configuration, not user input.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from .contracts import DataSensitivity, ProviderId, TaskType

MAX_MODEL_ENTRIES = 20
MAX_ALLOWED_PAID_MODELS = 4
MAX_REGISTRY_JSON_CHARS = 64_000
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


class ModelCostClass(StrEnum):
    FREE_QUOTA = "free_quota"
    TRIAL_CREDIT = "trial_credit"
    PAID = "paid"
    UNKNOWN = "unknown"


EXTERNAL_TASKS = frozenset({
    TaskType.CLASSIFY,
    TaskType.EXTRACT,
    TaskType.EXPLAIN,
    TaskType.SUMMARIZE,
    TaskType.ANALYZE,
    TaskType.RECONCILE,
    TaskType.DAILY_BRIEF,
})
SYNTHETIC_ONLY_COST_CLASSES = frozenset({
    ModelCostClass.FREE_QUOTA,
    ModelCostClass.TRIAL_CREDIT,
    ModelCostClass.UNKNOWN,
})


@dataclass(frozen=True, slots=True)
class ModelSpec:
    provider_id: ProviderId
    model_id: str
    cost_class: ModelCostClass
    supported_tasks: frozenset[TaskType] = EXTERNAL_TASKS
    enabled: bool = True
    aggregate_data_approved: bool = False
    confidential_data_approved: bool = False
    dynamic_alias: bool = False
    pricing_verified: bool = False

    @property
    def registry_id(self) -> str:
        return f"{self.provider_id.value}:{self.model_id}"

    @property
    def is_paid(self) -> bool:
        """Treat every non-verified-free entry as potentially billable."""
        return self.cost_class != ModelCostClass.FREE_QUOTA


def _setting(settings: Any | None, env: dict[str, str], env_name: str, attr: str, default: str = "") -> str:
    if env_name in env:
        return str(env[env_name] or "").strip()
    if settings is not None:
        value = getattr(settings, attr, default)
        return str(value if value is not None else default).strip()
    return default


def _provider_key_available(provider: ProviderId, settings: Any | None, env: dict[str, str]) -> bool:
    key_name, attr = {
        ProviderId.GEMINI: ("GEMINI_API_KEY", "gemini_api_key"),
        ProviderId.GROQ: ("GROQ_API_KEY", "groq_api_key"),
        ProviderId.CEREBRAS: ("CEREBRAS_API_KEY", "cerebras_api_key"),
        ProviderId.OPENROUTER: ("OPENROUTER_API_KEY", "openrouter_api_key"),
        ProviderId.HUGGINGFACE: ("HUGGINGFACE_API_KEY", "huggingface_api_key"),
        ProviderId.OPENAI: ("OPENAI_API_KEY", "openai_api_key"),
    }[provider]
    return bool(_setting(settings, env, key_name, attr))


def _base_models(settings: Any | None, env: dict[str, str]) -> list[ModelSpec]:
    """Known adapter defaults. Cost class stays conservative and is not inferred
    from the existence of an API key or from an account's remaining free credit.
    """
    definitions = (
        (ProviderId.GEMINI, "GEMINI_MODEL", "gemini_model", "gemini-3.8-flash", ModelCostClass.UNKNOWN, False),
        # Groq documents token prices for the configured GPT-OSS model.
        (ProviderId.GROQ, "GROQ_MODEL", "groq_model", "openai/gpt-oss-20b", ModelCostClass.PAID, False),
        # Credit balance is an account property, so the model itself is not assumed free.
        (ProviderId.CEREBRAS, "CEREBRAS_MODEL", "cerebras_model", "zai-glm-4.7", ModelCostClass.UNKNOWN, False),
        # This alias selects a changing model; it is restricted to synthetic input.
        (ProviderId.OPENROUTER, "OPENROUTER_MODEL", "openrouter_model", "openrouter/free", ModelCostClass.FREE_QUOTA, True),
        (ProviderId.HUGGINGFACE, "HUGGINGFACE_MODEL", "huggingface_model", "Qwen/Qwen3-32B", ModelCostClass.PAID, False),
        # The operator's selected model must still be verified in the OpenAI account.
        (ProviderId.OPENAI, "OPENAI_MODEL", "openai_model", "gpt-6-astra", ModelCostClass.PAID, False),
    )
    result: list[ModelSpec] = []
    for provider, env_name, attr, default, cost, dynamic in definitions:
        model_id = _setting(settings, env, env_name, attr, default) or default
        if not _MODEL_ID_RE.fullmatch(model_id):
            raise ValueError(f"Invalid model ID configured for provider {provider.value}.")
        result.append(ModelSpec(
            provider_id=provider,
            model_id=model_id,
            cost_class=cost,
            dynamic_alias=dynamic,
            pricing_verified=(cost == ModelCostClass.PAID or dynamic),
        ))
    return result


def _parse_custom_models(raw: str) -> list[ModelSpec]:
    if not raw:
        return []
    if len(raw) > MAX_REGISTRY_JSON_CHARS:
        raise ValueError("LEXA_AI_MODEL_REGISTRY_JSON exceeds the 64 KB configuration limit.")
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("LEXA_AI_MODEL_REGISTRY_JSON must be valid JSON.") from exc
    if not isinstance(payload, list):
        raise ValueError("LEXA_AI_MODEL_REGISTRY_JSON must be a JSON array.")
    models: list[ModelSpec] = []
    allowed_fields = {
        "provider_id", "model_id", "cost_class", "supported_tasks", "enabled",
        "aggregate_data_approved", "confidential_data_approved", "dynamic_alias",
        "pricing_verified",
    }
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or set(item) - allowed_fields:
            raise ValueError(f"Model registry entry {index} has an invalid shape.")
        required = {"provider_id", "model_id", "cost_class"}
        if not required.issubset(item):
            raise ValueError(f"Model registry entry {index} is missing required fields.")
        try:
            provider = ProviderId(str(item["provider_id"]).strip().lower())
            cost = ModelCostClass(str(item["cost_class"]).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Model registry entry {index} has an unknown provider or cost class.") from exc
        model_id = str(item["model_id"]).strip()
        if not _MODEL_ID_RE.fullmatch(model_id):
            raise ValueError(f"Model registry entry {index} has an invalid model ID.")
        raw_tasks = item.get("supported_tasks", [task.value for task in sorted(EXTERNAL_TASKS, key=lambda t: t.value)])
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise ValueError(f"Model registry entry {index} must list supported tasks.")
        try:
            tasks = frozenset(TaskType(str(value)) for value in raw_tasks)
        except ValueError as exc:
            raise ValueError(f"Model registry entry {index} contains an unknown task.") from exc
        if not tasks.issubset(EXTERNAL_TASKS):
            raise ValueError(f"Model registry entry {index} includes a task that cannot use an external model.")
        pricing_verified = item.get("pricing_verified", False)
        if not isinstance(pricing_verified, bool):
            raise ValueError(f"Model registry entry {index} pricing_verified must be boolean.")
        if cost == ModelCostClass.FREE_QUOTA and not pricing_verified:
            raise ValueError(f"Model registry entry {index} must verify zero-priced model access before using free_quota.")
        bool_fields = ("enabled", "aggregate_data_approved", "confidential_data_approved", "dynamic_alias")
        if any(name in item and not isinstance(item[name], bool) for name in bool_fields):
            raise ValueError(f"Model registry entry {index} has a non-boolean policy setting.")
        dynamic_alias = item.get("dynamic_alias", False)
        if dynamic_alias and cost != ModelCostClass.FREE_QUOTA:
            raise ValueError(f"Model registry entry {index}: dynamic aliases may only be free_quota and synthetic-data-only.")
        if provider == ProviderId.OPENROUTER and model_id == "openrouter/free":
            if cost != ModelCostClass.FREE_QUOTA or not dynamic_alias or not pricing_verified:
                raise ValueError("OpenRouter's openrouter/free alias must remain verified free_quota and synthetic-data-only.")
        models.append(ModelSpec(
            provider_id=provider,
            model_id=model_id,
            cost_class=cost,
            supported_tasks=tasks,
            enabled=item.get("enabled", False),
            aggregate_data_approved=item.get("aggregate_data_approved", False),
            confidential_data_approved=item.get("confidential_data_approved", False),
            dynamic_alias=dynamic_alias,
            pricing_verified=pricing_verified,
        ))
    return models


def load_model_registry(settings: Any | None = None, env: dict[str, str] | None = None) -> tuple[ModelSpec, ...]:
    """Load at most 20 entries and reject ambiguous duplicate model IDs.

    A custom entry replaces the matching built-in provider/model pair so an
    administrator can document the exact pricing/data-use approval for that model.
    New entries are disabled unless explicitly enabled in server-side JSON and are
    still subject to the separate LEXA_AI_ALLOWED_MODELS allowlist.
    """
    process_env = dict(os.environ if env is None else env)
    base = _base_models(settings, process_env)
    raw_custom = _setting(settings, process_env, "LEXA_AI_MODEL_REGISTRY_JSON", "lexa_ai_model_registry_json")
    custom = _parse_custom_models(raw_custom)
    by_id = {model.registry_id: model for model in base}
    seen_custom: set[str] = set()
    for model in custom:
        if model.registry_id in seen_custom:
            raise ValueError(f"LEXA model registry repeats model ID {model.registry_id!r}.")
        seen_custom.add(model.registry_id)
        # A custom record may explicitly document a built-in model's billing/data
        # status, but the same custom ID may appear only once in the configuration.
        by_id[model.registry_id] = model
    if len(by_id) > MAX_MODEL_ENTRIES:
        raise ValueError(f"LEXA model registry supports no more than {MAX_MODEL_ENTRIES} models.")
    if len(by_id) != len(set(by_id)):
        raise ValueError("LEXA model registry contains duplicate model IDs.")
    return tuple(by_id.values())


def allowed_model_ids(settings: Any | None = None, env: dict[str, str] | None = None) -> frozenset[str]:
    process_env = dict(os.environ if env is None else env)
    raw = _setting(settings, process_env, "LEXA_AI_ALLOWED_MODELS", "lexa_ai_allowed_models")
    if not raw:
        return frozenset()
    # Registry identifiers include the provider prefix to avoid cross-provider ambiguity.
    result = frozenset(value.strip() for value in raw.split(",") if value.strip())
    if any(len(value) > 200 or not re.fullmatch(r"[a-z_]+:[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}", value) for value in result):
        raise ValueError("LEXA_AI_ALLOWED_MODELS contains an invalid registry identifier.")
    return result


def resolve_model(provider_id: ProviderId | str, model_id: str, registry: Iterable[ModelSpec]) -> ModelSpec | None:
    try:
        provider = provider_id if isinstance(provider_id, ProviderId) else ProviderId(str(provider_id).strip().lower())
    except ValueError:
        return None
    wanted = str(model_id).strip()
    return next((model for model in registry if model.provider_id == provider and model.model_id == wanted), None)


def model_registry_status(settings: Any | None = None, env: dict[str, str] | None = None) -> list[dict[str, object]]:
    """Client-safe status only; never returns keys or raw registry JSON."""
    registry = load_model_registry(settings=settings, env=env)
    allowlist = allowed_model_ids(settings=settings, env=env)
    output: list[dict[str, object]] = []
    for model in registry:
        output.append({
            "id": model.registry_id,
            "provider": model.provider_id.value,
            "model": model.model_id,
            "cost_class": model.cost_class.value,
            "configured": _provider_key_available(model.provider_id, settings, dict(os.environ if env is None else env)),
            "enabled": model.enabled and model.registry_id in allowlist,
            "supported_tasks": sorted(task.value for task in model.supported_tasks),
            "synthetic_data_only": model.cost_class in SYNTHETIC_ONLY_COST_CLASSES or model.dynamic_alias,
        })
    return output
