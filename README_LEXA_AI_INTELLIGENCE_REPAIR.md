# LEXA assistant and intelligence repair package

This source package is prepared for the repository's **LEXA ZIP Extractor** workflow. It does not contain provider keys, user data, or a database connection string.

## Changes included

- Replaces the static Business Assistant page with an interactive, in-memory-only chat UI, a safe Markdown renderer, provider discovery, business-area selection, and links to LEXA's local intelligence pages.
- Adds the new `/api/v1/ai/assistant` endpoint. The legacy `/api/v1/ai/assist` endpoint remains blocked.
- Calls LEXA's central `intelligence.policy` router before a provider is selected. There is no automatic provider fallback.
- Restricts questions to supported LEXA/business workflows, gives greetings a local answer, rejects common off-topic and prompt-injection requests locally, screens personal identifiers, blocks numeric business details from external transfer by default, and never loads or sends another tenant's saved business data.
- Limits rate counting by authenticated `tenant_id` and `user_id`; reads only the authenticated tenant's `tenant_settings.timezone` for current business-local date/time/daypart; does not persist prompts or conversation history.
- Shortens provider timeout and default output budget to improve responsiveness. Assistant responses are normalized to Markdown prose rather than JSON.
- Extends the existing analytics worker to call a new optional backfill function from migration 047. The worker now schedules a complete 56-day projection refresh for tenants lacking a recent successful refresh, at most one tenant per poll, with a retry cooldown on failures.
- Adds regression tests for scope/privacy guardrails and the analytics worker's optional 56-day backfill path.

## Upload through the existing extractor workflow

1. Upload this ZIP at the **root** of `MONALISA2003-CMD/LEXA-` on the `main` branch. The archive includes `apps/web/package.json`, `apps/api/app/main.py` and a migration path so the existing extractor recognizes it.
2. Wait for **LEXA ZIP Extractor** to extract the files and commit the extracted source. Then inspect the extracted commit, GitHub Actions checks, Render deploy, and Vercel production deployment.
3. Do not upload the ZIP into `.github/workflows/`. The extractor deliberately protects that path.

The GitHub integration used to prepare this package cannot create branches or push changes directly (GitHub returned `403 Resource not accessible by integration`), so this package has not been committed to the repository by the assistant.

## Render environment values for question-only AI

Once the new code is present on `main`, set these on the **Render API service** (not on Vercel browser-visible variables):

```env
LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=true
LEXA_AI_ALLOWED_PROVIDERS=gemini,groq
LEXA_AI_PAID_PROVIDERS_ENABLED=false
LEXA_AI_AGGREGATES_EXTERNAL_ENABLED=false
LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED=false
LEXA_AI_MAX_OUTPUT_TOKENS=350
LEXA_AI_REQUESTS_PER_MINUTE=10
```

This enables only the configured Gemini/Groq question-only route. Paid providers remain disabled. The assistant does not send saved business summaries, customer/employee records, numeric business figures, or tenant identifiers to external models. A question containing business numbers is answered locally with a privacy explanation until a separate aggregate-sharing decision is made. Keep all provider secrets on Render only.

## Intelligence migrations and data readiness

The repository already contains migrations `045_intelligence_foundation.sql` and `046_intelligence_documents.sql`; the live database has not recorded them as applied and their tables are absent. This package adds `047_analytics_forecast_history_backfill.sql`, which gives the worker a bounded, tenant-aware way to build a full 56-day analytics refresh window. Migrations are not applied by this ZIP and no production SQL was run by this package.

A read-only check of the live Neon branch found:

- 7 tenants;
- 0 completed sales, 0 recorded payments and 0 completed returns;
- 5 active product variants;
- 0 analytics refresh runs, 0 analytics business-metric rows and 0 product-daily-metric rows;
- no pending or dead-letter refresh jobs.

After the migrations are reviewed and applied, the worker can establish fresh 56-day projection windows. Forecasting will still say **no recorded demand history** until transactions exist; it must not invent forecasts from missing data.

**Validation limitation:** a prepared Neon validation branch could not be created because the Neon project returned `branches limit exceeded`. The live database was queried read-only to check prerequisites, but migrations 045–047 have not been clean-replay-tested on an isolated branch and must not be applied to production until that test is completed. Do not delete an existing branch without confirming that it is disposable; the project currently has several named validation/replay branches.

## Validation run in this preparation environment

- Python files: syntax/AST compilation checked.
- Full API pytest and frontend TypeScript/build suites were not run here because this package intentionally contains only changed/marker files, the network is unavailable for cloning dependencies, and the full application source plus web `node_modules` are not present locally.
- The new tests are included so the canonical GitHub Actions workflow can run them against the complete repository after extraction.
