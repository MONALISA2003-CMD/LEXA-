# LEXA AI and Docker main-build increment — 24 October 2026

## What this increment adds

- A permission-gated, read-only AI assistant at `/ai-assistant`.
- Server-side provider adapters for Gemini API, OpenAI Responses API, and OpenAI-compatible Groq, Cerebras, OpenRouter, and Hugging Face Inference Providers.
- Provider status returns only safe metadata (model, label, tier and configured/not configured); keys are never sent to the browser.
- A shared Redis per-user/per-minute limiter, bounded prompt/output settings, generic upstream errors, no automatic paid-provider fallback, and an optional aggregate-only 30-day business summary. The summary checkbox is off by default and requires workspace-wide analytics access.
- A Compose edge using HAProxy that sends browser traffic to two Next.js containers and routes the Next.js server-side API proxy to two API containers. It health-checks both pools and keeps the API listener internal to the Compose network.

## AI provider setup

Set provider keys only in the **server environment** or local `.env`; never use a `NEXT_PUBLIC_*` variable. Blank keys disable that provider.

| Provider | Key variable | Default model | Cost posture |
| --- | --- | --- | --- |
| Google Gemini | `GEMINI_API_KEY` | `gemini-3.8-flash` | Free tier availability and limits depend on account/model; paid tier is possible |
| Groq | `GROQ_API_KEY` | `openai/gpt-oss-20b` | Developer/free quota where available; enforce the account's model limits |
| Cerebras | `CEREBRAS_API_KEY` | `zai-glm-4.7` | Developer quota varies by account/model |
| OpenRouter | `OPENROUTER_API_KEY` | `openrouter/free` | Select an explicitly free model and verify the model's routing/terms |
| Hugging Face | `HUGGINGFACE_API_KEY` | `Qwen/Qwen3-32B` | Small free credits where available; paid use may follow |
| OpenAI | `OPENAI_API_KEY` | `gpt-6-luna` | Paid API usage; there is no silent fallback to it |

Every model is environment-configurable. A provider may limit account access or retire a model; if a configured model is unavailable, the assistant returns a generic actionable error without exposing the provider response or key. Set `LEXA_AI_REQUESTS_PER_MINUTE` (default 10), `LEXA_AI_MAX_INPUT_CHARS` (default 8000), and `LEXA_AI_MAX_OUTPUT_TOKENS` (default 500; bounded to 64–1200) to tune the application-side limits. Also configure provider-side spend/usage budgets; application limits do not replace provider account limits.

## Data and safety boundaries

- No provider key enters browser code, API JSON responses, or logs.
- No prompt or business data is logged. The default request sends only the user's question and category. If the user opts in, a small aggregate-only summary of saved tenant metrics (last 30 calendar days) is sent to their selected provider; branch-wide analytics access is required. No customer-level rows or individual payment details are included.
- Treat provider output as advice, not authoritative business truth. The assistant cannot write database records, approve actions, post journals, mutate inventory, issue refunds, make payments, settle transfers, or create official tax/fiscal documents.
- Free and paid AI services have different retention/training terms. The UI tells the user that requests leave LEXA; accounts must review provider terms before enabling sensitive use. Gemini's current free tier terms state submitted content may be used to improve Google's products, unlike its paid tier terms. The UI warns about this before use.
- The initial assistant uses direct provider REST APIs and does not enable tools/agent execution. Adding write-capable agents requires a separate approval/permissions design.

## Docker/load-balancing boundary

`docker compose up --build` starts PostgreSQL, Redis, API replicas, web replicas, the analytics worker, and HAProxy. The browser entry point is `http://localhost:3000`. HAProxy balances web traffic round-robin and API calls least-connections with HTTP health checks. Direct API service ports are not published to the host. Provider keys are injected into API containers only.

This is a **single-host local/development topology**, not production high availability: the host, HAProxy, database volume and cache can still be single points of failure. For production multi-node failover, deploy behind a managed load balancer or a deliberate multi-node orchestration platform, configure secrets securely, persist/backup the authoritative database, and size DB connection pools across all replicas. Do not equate two containers on one machine with resilient multi-node load balancing.

The Compose file does not automatically mutate the database schema. Initialize the disposable local schema through the existing migration tooling; do not point this local stack at the live business database or automatically run destructive resets.

## Scope of validation

This is an incremental source build. Lightweight local checks cover Python syntax, the AI helper unit tests, YAML structure, route/navigation contracts and the load-balancer configuration text. It does not assert live provider credentials, consume provider quota, run a full Next.js production build, alter hosted services, or run expensive pre-production gates.


## Official reference links checked for this increment

- OpenAI model catalog and current API model IDs: https://developers.openai.com/api/docs/models
- Google Gemini API model availability and free/paid tier terms: https://ai.google.dev/gemini-api/docs/pricing
- Groq request/token rate limits: https://console.groq.com/docs/rate-limits
- Cerebras GLM 4.7 API model/parameter documentation: https://inference-docs.cerebras.ai/resources/glm-47-migration
- OpenRouter free-model selection and current request caps: https://openrouter.ai/pricing and https://openrouter.ai/collections/free-models
- Hugging Face Inference Providers pricing model: https://huggingface.co/docs/inference-providers/pricing

Provider model IDs, free quotas and data practices can change; use these live provider sources and each account dashboard to confirm settings when enabling keys.
