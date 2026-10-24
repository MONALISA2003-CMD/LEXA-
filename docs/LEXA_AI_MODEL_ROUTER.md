# LEXA model registry and central AI policy

**Scope:** first router implementation for `MONALISA2003-CMD/LEXA-`, target `main`.

## What this build establishes

- One server-side model registry for the six provider adapters already present in LEXA.
- Optional administrator-defined model records through `LEXA_AI_MODEL_REGISTRY_JSON`, capped at 20 total records.
- Exact provider + model matching; requests cannot supply an endpoint URL or invent a model ID.
- A separate `LEXA_AI_ALLOWED_MODELS` model-ID allowlist in addition to the existing provider allowlist.
- A hard maximum of four allowlisted, enabled model entries that could incur a charge (`paid`, `trial_credit`, or `unknown`). Verified `free_quota` entries do not consume paid slots.
- Model-specific cost classes: `free_quota`, `trial_credit`, `paid`, `unknown`.
- A free-quota / trial-credit / unknown-cost policy that only permits public synthetic examples. Dynamic aliases are also synthetic-only.
- Personal and sensitive personal data remain blocked from every external model. Aggregate and confidential business data require model-level approval *and* the matching global LEXA policy approval.
- Paid usage requires `LEXA_AI_PAID_PROVIDERS_ENABLED=true`. A free quota exhausted or unavailable does not authorize a paid model fallback.
- Adapter execution is behind the model-aware policy check and uses a registered model ID. The legacy `/api/v1/ai/assist` endpoint remains closed by the main API middleware, and the route itself fails closed because trusted prompt screening/redaction is not wired yet.
- Mock-only tests; no real provider keys, credits or network requests are required in CI.
- Corrections to stale frontend/API contract assertions found in main CI run `40071295539`. These are test expectation changes only; this build does not rewrite the UI copy.

## Default model records

The registry seeds the adapter defaults already defined by LEXA's server settings. It does not claim every model ID is currently available in a vendor account. In particular, account credentials, per-account availability, provider pricing and trial-credit expiry must be confirmed by an operator before allowlisting a model.

| Provider | Default model from existing LEXA settings | Initial cost treatment |
|---|---|---|
| Gemini | `gemini-3.8-flash` | `unknown` until the exact project's billing tier is checked |
| Groq | `openai/gpt-oss-20b` | `paid` according to the current provider pricing page |
| Cerebras | `zai-glm-4.7` | `unknown`; trial credit is account-specific and may expire |
| OpenRouter | `openrouter/free` | `free_quota`, dynamic alias, synthetic examples only |
| Hugging Face | `Qwen/Qwen3-32B` | `paid`/usage-metered |
| OpenAI API | Existing `OPENAI_MODEL` value | `paid`; verify the chosen model ID is valid for the account |

The four-model billable limit is a maximum on the *enabled, allowlisted potentially billable model IDs*, not a promise that a given provider or account includes four free models. The registry can carry up to 20 entries; only models with a verified cost classification and explicit allowlist should be enabled.

## Custom registry JSON

Configure the server-only `LEXA_AI_MODEL_REGISTRY_JSON` setting as a JSON array. Example shape (demonstration only; do not copy a made-up model ID into production):

```json
[
  {
    "provider_id": "openrouter",
    "model_id": "vendor/example:free",
    "cost_class": "free_quota",
    "pricing_verified": true,
    "supported_tasks": ["classify", "explain", "summarize"],
    "enabled": true,
    "aggregate_data_approved": false,
    "confidential_data_approved": false,
    "dynamic_alias": false
  }
]
```

For `free_quota`, `pricing_verified: true` is required. Only exact, server-controlled IDs are accepted. `LEXA_AI_ALLOWED_MODELS` must separately list exact registry IDs, e.g. `openrouter:vendor/example:free`. `LEXA_AI_ALLOWED_PROVIDERS` must separately include `openrouter`. Paid-use, aggregate-data and confidential-data approvals are independent controls; none are enabled by default. Do not set confidential/aggregate approval for a provider or model before its data handling and contract terms have been assessed.

The existing `LEXA_AI_EXTERNAL_PROVIDERS_ENABLED` default remains `false`. The first router build deliberately does not activate external execution: a trusted classifier/redaction stage is still required before setting `input_safety_checked=True`, and the public assistant route is still blocked by the separate API middleware. Do not remove those gates as a deployment shortcut.

## Build and release sequence

1. Upload this ZIP to repository root on `main`, let LEXA ZIP Extractor process it, then create `.github/workflows/lexa-ai-router-build.yml` by copying `docs/LEXA_AI_ROUTER_WORKFLOW.yml` into that path.
2. Run **LEXA Model Registry and AI Router Build** on `main`.
3. The workflow applies the guarded changes and runs frontend typecheck, all frontend contract tests, Next.js production build, API compile/tests and Compose/HAProxy validation. It commits to `main` only if every check succeeds.
4. The standard `LEXA Main Build CI` must then pass on the resulting source commit. Confirm Vercel and Render deploy the exact intended commit before calling the work production-ready.
5. Keep provider execution disabled until privacy review, trusted input screening, and any account-specific provider terms have been verified.

No production database schema, stored business data, accounting logic, permission logic, provider secret, billing configuration or deployment setting is changed by this package.
