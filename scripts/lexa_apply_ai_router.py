#!/usr/bin/env python3
"""Apply the reviewed LEXA model-registry/router changes to a full main checkout.

Safe to run repeatedly. Without --apply it only previews the edits. This script
never reads, writes, or logs production secrets; it does not call model providers.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str, *, required: bool = True) -> tuple[str, int]:
    if new in text and (old not in text or old in new):
        return text, 0
    count = text.count(old)
    if not count:
        if required:
            raise RuntimeError(f"Could not find expected source marker for: {label}")
        return text, 0
    if count != 1:
        raise RuntimeError(f"Expected one source marker for {label}, found {count}")
    return text.replace(old, new, 1), 1


def patch(path: Path, replacements: list[tuple[str, str, str]], *, required: bool = True, write: bool = False) -> int:
    if not path.is_file():
        raise RuntimeError(f"Required LEXA source file is missing: {path}")
    before = path.read_text(encoding="utf-8")
    after = before
    changes = 0
    for old, new, label in replacements:
        after, n = replace_once(after, old, new, label, required=required)
        changes += n
    if after != before and write:
        path.write_text(after, encoding="utf-8", newline="\n")
    status = "UPDATED" if after != before and write else ("WOULD UPDATE" if after != before else "OK")
    print(f"{status} {path.name} ({changes} patch(es))")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes; otherwise validate expected source markers")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "apps/web/package.json").is_file() or not (root / "apps/api/app/main.py").is_file():
        print("ERROR: this is not a full LEXA source checkout.", file=sys.stderr)
        return 2

    # The ZIP extractor protects .github/workflows and should not create a half-applied
    # application commit. The registry and test are shipped as reviewed docs assets and
    # materialized into active paths only when this full-check workflow is run.
    install_assets = (
        (root / "docs/LEXA_AI_MODEL_REGISTRY_SOURCE.py", root / "apps/api/app/intelligence/model_registry.py"),
        (root / "docs/LEXA_AI_MODEL_REGISTRY_TESTS.py", root / "apps/api/tests/test_intelligence_model_registry.py"),
    )
    for asset_path, target_path in install_assets:
        if target_path.exists():
            continue
        if not asset_path.is_file():
            raise RuntimeError(f"Required reviewed source asset is missing: {asset_path}")
        if args.apply:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(asset_path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
            print(f"INSTALLED {target_path.relative_to(root)} from {asset_path.relative_to(root)}")
        else:
            print(f"WOULD INSTALL {target_path.relative_to(root)} from {asset_path.relative_to(root)}")

    # This script is packaged as a source overlay; when installed from ZIP, files
    # are extracted at repository root, while this script lives under scripts/.
    # Re-resolve source paths from the selected checkout root.
    total = 0

    contracts = root / "apps/api/app/intelligence/contracts.py"
    total += patch(contracts, [
        (
            '    selected_provider: ProviderId | None = None\n    fallback_provider: ProviderId | None = None',
            '    selected_provider: ProviderId | None = None\n    selected_model_id: str | None = None\n    fallback_provider: ProviderId | None = None',
            'RouterDecision model identifier field',
        ),
        (
            '        if self.engine == EngineType.EXTERNAL_LLM and self.allowed:\n            if self.selected_provider is None or not self.external_data_transfer:\n                raise ValueError("An approved external route must identify the provider and transfer boundary")',
            '        if self.engine == EngineType.EXTERNAL_LLM and self.allowed:\n            if self.selected_provider is None or not self.external_data_transfer:\n                raise ValueError("An approved external route must identify the provider and transfer boundary")\n            if self.selected_model_id is not None and not self.selected_model_id.strip():\n                raise ValueError("An approved model identifier cannot be blank")\n        if not self.allowed and self.selected_model_id is not None:\n            raise ValueError("A blocked route cannot select a model")',
            'RouterDecision model identifier validation',
        ),
    ], write=args.apply)

    init_path = root / "apps/api/app/intelligence/__init__.py"
    total += patch(init_path, [(
        'POLICY_VERSION = "phase1-v1"',
        'POLICY_VERSION = "phase2-model-registry-v1"',
        'bump central policy version for model registry',
    )], write=args.apply)

    policy_path = root / "apps/api/app/intelligence/policy.py"
    policy_replacements = [
        (
            'POLICY_VERSION = "phase1-v1"',
            'POLICY_VERSION = "phase2-model-registry-v1"',
            'bump model routing policy version',
        ),
        (
            'from typing import Any, Iterable\n\nfrom .contracts import (',
            'from typing import Any, Iterable, Sequence\n\nfrom .model_registry import (\n    MAX_ALLOWED_PAID_MODELS,\n    ModelCostClass,\n    ModelSpec,\n    SYNTHETIC_ONLY_COST_CLASSES,\n)\nfrom .contracts import (',
            'model registry imports',
        ),
        (
            'def configured_provider_ids(env: Any | None = None) -> frozenset[ProviderId]:\n    """Return configured provider IDs without ever returning or logging key values."""\n    if env is None:\n        import os\n\n        env = os.environ\n    configured: set[ProviderId] = set()\n    for provider, env_name in PROVIDER_KEY_ENV.items():\n        if str(env.get(env_name, "")).strip():\n            configured.add(provider)\n    return frozenset(configured)',
            'def configured_provider_ids(env: Any | None = None, settings: Any | None = None) -> frozenset[ProviderId]:\n    """Return configured provider IDs without returning or logging key values."""\n    if env is None:\n        import os\n        env = os.environ\n    setting_attrs = {\n        ProviderId.GEMINI: "gemini_api_key", ProviderId.GROQ: "groq_api_key",\n        ProviderId.CEREBRAS: "cerebras_api_key", ProviderId.OPENROUTER: "openrouter_api_key",\n        ProviderId.HUGGINGFACE: "huggingface_api_key", ProviderId.OPENAI: "openai_api_key",\n    }\n    configured: set[ProviderId] = set()\n    for provider, env_name in PROVIDER_KEY_ENV.items():\n        value = env.get(env_name, "")\n        if not str(value or "").strip() and settings is not None:\n            value = getattr(settings, setting_attrs[provider], "")\n        if str(value or "").strip():\n            configured.add(provider)\n    return frozenset(configured)',
            'settings-aware provider key detection',
        ),
        (
            '    configured_providers: Iterable[ProviderId] = (),\n) -> RouterDecision:',
            '    configured_providers: Iterable[ProviderId] = (),\n    *,\n    model_cost_class: ModelCostClass | None = None,\n) -> RouterDecision:',
            'model cost class input',
        ),
        (
            '        if candidate in PAID_PROVIDER_IDS and not policy.paid_providers_enabled:\n            if request.provider_preference is not None:\n                return _blocked(request, "PAID_PROVIDER_OPT_IN_REQUIRED", policy)\n            continue',
            '        # Model-level cost is authoritative when present. Generic provider-only\n        # callers remain conservative for providers historically treated as paid.\n        needs_paid_opt_in = (\n            candidate in PAID_PROVIDER_IDS if model_cost_class is None\n            else model_cost_class != ModelCostClass.FREE_QUOTA\n        )\n        if needs_paid_opt_in and not policy.paid_providers_enabled:\n            if request.provider_preference is not None:\n                return _blocked(request, "PAID_MODEL_OPT_IN_REQUIRED" if model_cost_class is not None else "PAID_PROVIDER_OPT_IN_REQUIRED", policy)\n            continue',
            'model-level paid-use guard',
        ),
    ]
    total += patch(policy_path, policy_replacements, write=args.apply)

    # Append the model-aware policy entry point. It is deliberately separate from
    # provider selection so no caller can treat a provider key as model approval.
    policy_text = policy_path.read_text(encoding="utf-8")
    policy_function_marker = 'def plan_model_route(\n'
    if policy_function_marker not in policy_text:
        function = '''\n\ndef plan_model_route(\n    request: RoutingRequest,\n    policy: RouterPolicy,\n    configured_providers: Iterable[ProviderId],\n    model: ModelSpec,\n    registry: Sequence[ModelSpec],\n    allowed_models: Iterable[str],\n) -> RouterDecision:\n    """Authorize one exact model. This function never makes a network request."""\n    allowed = frozenset(allowed_models)\n    configured = frozenset(configured_providers)\n\n    if request.provider_preference != model.provider_id:\n        return _blocked(request, "MODEL_PROVIDER_MISMATCH", policy)\n    if not model.enabled:\n        return _blocked(request, "MODEL_DISABLED", policy)\n    if model.registry_id not in allowed:\n        return _blocked(request, "MODEL_NOT_ALLOWLISTED", policy)\n    if model.provider_id not in configured:\n        return _blocked(request, "PROVIDER_NOT_CONFIGURED", policy)\n    if request.task not in model.supported_tasks:\n        return _blocked(request, "MODEL_TASK_UNSUPPORTED", policy)\n\n    # Enforce a hard cap on the number of potentially billable model IDs\n    # (paid, trial-credit, or unknown-cost) administrators can allowlist at once.\n    # A configuration mistake blocks paid routing; it never changes the cost class.\n    allowed_paid = {\n        candidate.registry_id for candidate in registry\n        if candidate.enabled and candidate.cost_class != ModelCostClass.FREE_QUOTA and candidate.registry_id in allowed\n    }\n    if len(allowed_paid) > MAX_ALLOWED_PAID_MODELS and model.cost_class != ModelCostClass.FREE_QUOTA:\n        return _blocked(request, "PAID_MODEL_LIMIT_EXCEEDED", policy)\n\n    if model.cost_class in SYNTHETIC_ONLY_COST_CLASSES or model.dynamic_alias:\n        if request.sensitivity != DataSensitivity.PUBLIC_SYNTHETIC or request.includes_business_summary:\n            return _blocked(request, "MODEL_RESTRICTED_TO_SYNTHETIC_DATA", policy)\n    if (request.sensitivity == DataSensitivity.AGGREGATED_BUSINESS or request.includes_business_summary) and not model.aggregate_data_approved:\n        return _blocked(request, "MODEL_AGGREGATE_DATA_NOT_APPROVED", policy)\n    if request.sensitivity == DataSensitivity.CONFIDENTIAL_BUSINESS and not model.confidential_data_approved:\n        return _blocked(request, "MODEL_CONFIDENTIAL_DATA_NOT_APPROVED", policy)\n\n    decision = plan_route(\n        request, policy, configured_providers=configured, model_cost_class=model.cost_class\n    )\n    if decision.allowed:\n        return decision.model_copy(update={"selected_model_id": model.model_id})\n    return decision\n'''
        if args.apply:
            policy_path.write_text(policy_text.rstrip() + function + "\n", encoding="utf-8", newline="\n")
            print("UPDATED apps/api/app/intelligence/policy.py (model-level route planner)")
        else:
            print("WOULD UPDATE apps/api/app/intelligence/policy.py (model-level route planner)")
        total += 1
    else:
        print("OK apps/api/app/intelligence/policy.py (model-level route planner already present)")

    config_path = root / "apps/api/app/config.py"
    total += patch(config_path, [(
        '    lexa_ai_allowed_providers: str = ""\n    lexa_ai_paid_providers_enabled: bool = False',
        '    lexa_ai_allowed_providers: str = ""\n    lexa_ai_allowed_models: str = ""\n    lexa_ai_model_registry_json: str = ""\n    lexa_ai_paid_providers_enabled: bool = False',
        'model allowlist and registry settings',
    )], write=args.apply)

    env_example_path = root / ".env.example"
    total += patch(env_example_path, [(
        'LEXA_AI_REQUESTS_PER_MINUTE=10\nLEXA_AI_MAX_INPUT_CHARS=8000\nLEXA_AI_MAX_OUTPUT_TOKENS=500\n',
        'LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=false\nLEXA_AI_ALLOWED_PROVIDERS=\nLEXA_AI_ALLOWED_MODELS=\nLEXA_AI_PAID_PROVIDERS_ENABLED=false\nLEXA_AI_AGGREGATES_EXTERNAL_ENABLED=false\nLEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED=false\nLEXA_AI_MODEL_REGISTRY_JSON=\nLEXA_AI_REQUESTS_PER_MINUTE=10\nLEXA_AI_MAX_INPUT_CHARS=8000\nLEXA_AI_MAX_OUTPUT_TOKENS=500\n',
        'safe-default AI router environment examples',
    )], write=args.apply)

    compose_path = root / "docker-compose.yml"
    total += patch(compose_path, [(
        '    LEXA_AI_REQUESTS_PER_MINUTE: ${LEXA_AI_REQUESTS_PER_MINUTE:-10}\n',
        '    LEXA_AI_EXTERNAL_PROVIDERS_ENABLED: ${LEXA_AI_EXTERNAL_PROVIDERS_ENABLED:-false}\n    LEXA_AI_ALLOWED_PROVIDERS: ${LEXA_AI_ALLOWED_PROVIDERS:-}\n    LEXA_AI_ALLOWED_MODELS: ${LEXA_AI_ALLOWED_MODELS:-}\n    LEXA_AI_PAID_PROVIDERS_ENABLED: ${LEXA_AI_PAID_PROVIDERS_ENABLED:-false}\n    LEXA_AI_AGGREGATES_EXTERNAL_ENABLED: ${LEXA_AI_AGGREGATES_EXTERNAL_ENABLED:-false}\n    LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED: ${LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED:-false}\n    LEXA_AI_MODEL_REGISTRY_JSON: ${LEXA_AI_MODEL_REGISTRY_JSON:-}\n    LEXA_AI_REQUESTS_PER_MINUTE: ${LEXA_AI_REQUESTS_PER_MINUTE:-10}\n',
        'model router environment variables in local compose',
    )], write=args.apply)

    assistant_path = root / "apps/api/app/routes/ai_assistant.py"
    assistant_replacements = [
        (
            'from ..dependencies import require_permission\n',
            'from ..dependencies import require_permission\nfrom ..intelligence.contracts import DataSensitivity, ProviderId as RouterProviderId, RoutingRequest, TaskType\nfrom ..intelligence.model_registry import MAX_ALLOWED_PAID_MODELS, MAX_MODEL_ENTRIES, ModelCostClass, allowed_model_ids, load_model_registry, model_registry_status, resolve_model\nfrom ..intelligence.policy import configured_provider_ids, plan_model_route, policy_from_settings\n',
            'central router imports',
        ),
        (
            '@router.get("/providers")\ndef list_ai_providers(ctx=Depends(require_permission("analytics.read"))):\n    configured = any(item["configured"] for item in provider_status())\n    return {"enabled": configured, "providers": provider_status(), "maximum_prompt_characters": 8_000}',
            '@router.get("/providers")\ndef list_ai_providers(ctx=Depends(require_permission("analytics.read"))):\n    try:\n        registry = load_model_registry(settings=settings)\n        allowlisted = allowed_model_ids(settings=settings)\n        policy = policy_from_settings(settings)\n        configured = configured_provider_ids(settings=settings)\n        eligible = policy.external_providers_enabled and any(\n            model.enabled\n            and model.registry_id in allowlisted\n            and model.provider_id in policy.allowed_providers\n            and model.provider_id in configured\n            and (model.cost_class == ModelCostClass.FREE_QUOTA or policy.paid_providers_enabled)\n            for model in registry\n        )\n        registry_valid = True\n        models_status = model_registry_status(settings=settings)\n    except ValueError:\n        eligible = False\n        registry_valid = False\n        models_status = []\n        registry = ()\n    return {\n        "enabled": eligible,\n        "execution_available": False,\n        "registry_valid": registry_valid,\n        "model_count": len(registry),\n        "maximum_model_count": MAX_MODEL_ENTRIES,\n        "maximum_billable_model_count": MAX_ALLOWED_PAID_MODELS,\n        "models": models_status,\n        "providers": provider_status(),\n        "maximum_prompt_characters": 8_000,\n    }',
            'safe model-level provider status endpoint',
        ),
        (
            '    ProviderSpec("groq", "Groq", "Free/developer quota; provider limits apply", "GROQ_API_KEY", "GROQ_MODEL", "openai/gpt-oss-20b", "https://api.groq.com/openai/v1", "openai-compatible"),',
            '    ProviderSpec("groq", "Groq", "Model-based token pricing; account limits apply", "GROQ_API_KEY", "GROQ_MODEL", "openai/gpt-oss-20b", "https://api.groq.com/openai/v1", "openai-compatible"),',
            'correct Groq model pricing label',
        ),
        (
            '    prompt: str = Field(min_length=1, max_length=8_000)\n    include_business_summary: bool = False',
            '    prompt: str = Field(min_length=1, max_length=8_000)\n    model_id: str | None = Field(default=None, min_length=1, max_length=160)\n    include_business_summary: bool = False',
            'optional exact registered model ID',
        ),
        (
            'async def _generate(provider_id: ProviderId, prompt: str, system_instruction: str) -> tuple[str, str]:\n',
            'async def _generate(provider_id: ProviderId, prompt: str, system_instruction: str, *, model_override: str | None = None) -> tuple[str, str]:\n',
            'model override in provider adapter',
        ),
        (
            '    model = _model_for(spec)\n    headers = {"Content-Type": "application/json"}',
            '    model = (model_override or _model_for(spec)).strip() or _model_for(spec)\n    headers = {"Content-Type": "application/json"}',
            'exact model passed to adapter',
        ),
        (
            '    if not _api_key_for(spec):\n        raise HTTPException(status_code=503, detail={"code": "AI_PROVIDER_NOT_CONFIGURED", "message": f"{spec.label} is not configured on the LEXA API server."})\n\n    question = body.prompt.strip()',
            '    question = body.prompt.strip()',
            'remove provider-key-only authorization before central policy',
        ),
        (
            '    await _enforce_rate_limit(tenant_id, user_id)\n    full_prompt = f"Business area: {body.area}\\nUser question (untrusted input):\\n{question}"',
            '    # Registry, provider allowlist, model allowlist, data sensitivity, and paid-use\n    # policy all have to agree before any external adapter is called. There is no\n    # trusted input-classification/redaction stage wired into this endpoint yet, so\n    # this first router build deliberately fails closed for user free text. The main\n    # middleware adds a second fail-closed gate for the public legacy endpoint.\n    try:\n        registry = load_model_registry(settings=settings)\n        selected_model_id = (body.model_id or _model_for(spec)).strip()\n        model = resolve_model(body.provider, selected_model_id, registry)\n        if model is None:\n            raise HTTPException(status_code=503, detail={"code": "AI_MODEL_NOT_REGISTERED", "message": "This assistant model is not available. Your question was not sent to an external AI service."})\n        routing_request = RoutingRequest(\n            task=TaskType.EXPLAIN,\n            sensitivity=DataSensitivity.CONFIDENTIAL_BUSINESS,\n            provider_preference=RouterProviderId(body.provider),\n            includes_business_summary=body.include_business_summary,\n            input_safety_checked=False,\n            purpose_code="business_assistant",\n        )\n        decision = plan_model_route(\n            routing_request,\n            policy_from_settings(settings),\n            configured_provider_ids(settings=settings),\n            model,\n            registry,\n            allowed_model_ids(settings=settings),\n        )\n    except ValueError as exc:\n        logger.warning("ai_model_registry_invalid exception_type=%s", type(exc).__name__)\n        raise HTTPException(status_code=503, detail={"code": "AI_MODEL_REGISTRY_UNAVAILABLE", "message": "The assistant is not available right now. Your question was not sent to an external AI service."}) from exc\n    if not decision.allowed:\n        logger.info("ai_route_blocked reason=%s provider=%s", decision.reason_code, body.provider)\n        raise HTTPException(status_code=503, detail={"code": "AI_POLICY_BLOCKED", "message": "The assistant is not available for this request. Your question was not sent to an external AI service."})\n\n    await _enforce_rate_limit(tenant_id, user_id)\n    full_prompt = f"Business area: {body.area}\\nUser question (untrusted input):\\n{question}"',
            'model registry + policy decision before rate limit, DB summary or provider execution',
        ),
        (
            '    model, answer = await _generate(body.provider, full_prompt, _system_instruction(body.area))',
            '    model, answer = await _generate(body.provider, full_prompt, _system_instruction(body.area), model_override=selected_model_id)',
            'adapter receives only centrally approved model',
        ),
    ]
    total += patch(assistant_path, assistant_replacements, write=args.apply)

    # Fix only stale CI assertions; the UI copy itself is not changed in this build.
    web_fixes = {
        "apps/web/tests/phase1-ux-contract.test.mjs": [
            ('/Business settings/', '/Business details/'),
        ],
        "apps/web/tests/phase3-document-intelligence.test.mjs": [
            ('/Guidance that fits your business/', '/Guidance for your business./'),
            ('/AI responses are temporarily paused/', '/The assistant isn’t available right now/'),
            ('/Your question will not be sent to a provider/', '/will not generate or pretend to generate an answer while the assistant is unavailable/'),
            ('/executionAvailable &&/', '/will not generate or pretend to generate an answer while the assistant is unavailable/'),
            ('/Information that needs a refresh/', '/Information to check or update/'),
            ('/Missing data is never presented as zero/', '/Missing information is never treated as zero/'),
        ],
        "apps/web/tests/phase4-demand-forecast.test.mjs": [
            ('/\\["\\/demand-forecast", "Demand forecast", "chart"\\]/', '/\\["\\/demand-forecast", "Sales forecast", "chart"\\]/'),
            ('/Product demand forecast/', '/Expected demand and sales forecast/'),
        ],
        "apps/web/tests/phase8-foundation-polish.test.mjs": [
            ('"Finance"', '"Money & records"'),
        ],
        "apps/web/tests/visible-product-contract.test.mjs": [
            ('/Business settings/', '/Business details/'),
        ],
    }
    for rel, pairs in web_fixes.items():
        path = root / rel
        if not path.is_file():
            raise RuntimeError(f"Required CI contract test is missing: {rel}")
        text = path.read_text(encoding="utf-8")
        updated = text
        n_total = 0
        for old, new in pairs:
            if old == new:
                continue
            count = updated.count(old)
            if count:
                updated = updated.replace(old, new)
                n_total += count
        if updated != text:
            if args.apply:
                path.write_text(updated, encoding="utf-8", newline="\n")
                print(f"UPDATED {rel} ({n_total} stale assertion(s))")
            else:
                print(f"WOULD UPDATE {rel} ({n_total} stale assertion(s))")
            total += 1
        else:
            print(f"OK {rel} (no listed stale assertion remained)")

    api_test_path = root / "apps/api/tests/test_intelligence_phase3.py"
    old_assertions = '    assert "executionAvailable &&" in ai_ui\n    assert "Your question will not be sent to a provider" in ai_ui'
    new_assertions = '    assert "The assistant isn’t available right now." in ai_ui\n    assert "will not generate or pretend to generate an answer while the assistant is unavailable" in ai_ui\n    assert "fetch(" not in ai_ui\n    assert "<textarea" not in ai_ui'
    total += patch(api_test_path, [(old_assertions, new_assertions, 'disabled assistant API/UI contract expectations')], write=args.apply)

    if not args.apply:
        print(f"\nPreview complete: {total} patch group(s) available. Re-run with --apply to write them.")
        return 0
    print(f"\nApplied {total} patch group(s). Run typecheck, all frontend tests/build, and the complete API suite before committing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
