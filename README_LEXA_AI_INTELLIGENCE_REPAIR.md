# LEXA assistant and intelligence repair package

This source package is prepared for the repository's **LEXA ZIP Extractor** workflow. It does not contain provider keys, user data, or a database connection string.

## Changes included

- Replaces the static Business Assistant page with an interactive, in-memory-only chat UI, a safe Markdown renderer, central-policy availability checking, business-area selection, and links to LEXA's local intelligence pages. Provider selection stays server-side so customers do not need to choose a model service.
- Adds the new `/api/v1/ai/assistant` endpoint. The legacy `/api/v1/ai/assist` endpoint remains blocked.
- Calls LEXA's central `intelligence.policy` router before a provider is selected. There is no automatic provider fallback.
- Restricts questions to supported LEXA/business workflows, gives greetings a local answer, rejects common off-topic and prompt-injection requests locally, screens personal identifiers, blocks numeric business details from external transfer by default, and never loads or sends another tenant's saved business data.
- Limits rate counting by authenticated `tenant_id` and `user_id`; rejects client-supplied tenant/user/workspace identifiers; reads only the authenticated tenant's `tenant_settings.timezone` for current business-local date/time/daypart; does not persist prompts or conversation history. The UI clears its in-memory conversation if the active workspace changes.
- Enables approved question-only external responses by default, with the central allowlist limited to Gemini and Groq. Actual external execution still requires the provider key on the server, and an explicitly configured `LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=false` continues to disable it. Paid providers and external business-data sharing remain off.
- Adds a hard 12-second server-side model deadline, 11-second provider HTTP timeout, a 14.5-second frontend deadline, and a smaller output budget to target a response within 15 seconds. Provider/model choice stays server-side; the system does not send saved business summaries, tenant identifiers, customer records, or unscreened figures.
- Improves business tone across the assistant and intelligence capability/forecast messages: concise, commercially fluent wording, useful headings when needed, and no repetitive canned heading or software-engineering language. The intelligence capability endpoint now distinguishes question-only assistant routing from future confidential-data/document extraction capabilities.
- Expands the compliance page with Uganda-specific URA/EFRIS setup: TIN, registered legal name, effective date, read-only URA registration status, official URA guidance links, and quick-create tax-rate references for 18% standard-rated and 0% eligible zero-rated supplies. These rates are not assigned as defaults; no supply is classified automatically.
- Extends the existing analytics worker to call a new optional backfill function from migration 047. The worker now schedules a complete 56-day projection refresh for tenants lacking a recent successful refresh, at most one tenant per poll, with a retry cooldown on failures.
- Adds regression tests for scope/privacy guardrails and the analytics worker's optional 56-day backfill path.

## Upload through the existing extractor workflow

1. Upload this ZIP at the **root** of `MONALISA2003-CMD/LEXA-` on the `main` branch. The archive includes `apps/web/package.json`, `apps/api/app/main.py` and a migration path so the existing extractor recognizes it.
2. Wait for **LEXA ZIP Extractor** to extract the files and commit the extracted source. Then inspect the extracted commit, GitHub Actions checks, Render deploy, and Vercel production deployment.
3. Do not upload the ZIP into `.github/workflows/`. The extractor deliberately protects that path.

This package is not committed to the repository by the assistant. It is a changed-files overlay, not a complete source repository. Upload it at the repository root through the existing extractor workflow so the full repository tests can run.

## Render environment values for question-only AI

The API defaults to allowing the Gemini/Groq route, but an environment override can turn it off. On the **Render API service**, verify these values and add a valid provider key as a secret; never put provider keys in Vercel browser-visible variables:

```env
LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=true
LEXA_AI_ALLOWED_PROVIDERS=gemini,groq
LEXA_AI_PAID_PROVIDERS_ENABLED=false
LEXA_AI_AGGREGATES_EXTERNAL_ENABLED=false
LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED=false
LEXA_AI_MAX_OUTPUT_TOKENS=300
LEXA_AI_REQUESTS_PER_MINUTE=10
GEMINI_API_KEY=<set as a Render secret>
GROQ_API_KEY=<set as a Render secret>
```

Use at least one actual key. Key values must be added through Render's secret/environment UI; no key is included in this ZIP. Requests containing personal identifiers or business figures remain local/blocked by default. External providers receive only the screened text question and the business-style system instruction, not saved business summaries, tenant identifiers, customer/employee records, or workspace data. The 15-second target is a hard response budget, not a guarantee during provider outages or severe latency; timeouts return a useful business-language message rather than waiting indefinitely.

## Uganda URA / EFRIS configuration

The compliance page stores the available business-specific EFRIS fields, shows the registration status as read-only, and links to official URA registration guidance. The reference-rate actions create tax-rate records only: 18% for standard-rated supplies and 0% for supplies legally eligible for zero-rating. They do not create a default tax rule because product tax treatment depends on the applicable law and the business's supply mix.

Official guidance: [URA EFRIS registration](https://ura.go.ug/en/efris/efris-registration/), [URA EFRIS overview](https://ura.go.ug/en/efris/), and [URA VAT guidance](https://ura.go.ug/en/value-added-tax-vat/). Actual system-to-system fiscalisation still requires the taxpayer's URA registration/approval and a real approved connector with credentials. This package intentionally does not invent URA endpoints, credentials, FDNs, verification codes, or an ACTIVE status. A payment receipt is not labelled as an accepted EFRIS document unless genuine URA-returned details exist.

## Intelligence migrations and data readiness

The repository already contains migrations `045_intelligence_foundation.sql` and `046_intelligence_documents.sql`; the live database has not recorded them as applied and their tables are absent. This package adds `047_analytics_forecast_history_backfill.sql`, which gives the worker a bounded, tenant-aware way to build a full 56-day analytics refresh window. Migrations are not applied by this ZIP and no production SQL was run by this package.

A read-only check of the live Neon branch found:

- 7 tenants;
- 0 completed sales, 0 recorded payments and 0 completed returns;
- 5 active product variants;
- 0 analytics refresh runs, 0 analytics business-metric rows and 0 product-daily-metric rows;
- no pending or dead-letter refresh jobs.

After the migrations are reviewed and applied, the worker can establish fresh 56-day projection windows. Forecasting will still say **no recorded demand history** until transactions exist; it must not invent forecasts from missing data.

**Migration validation:** migrations 045, 046 and 047 were executed together successfully on the non-production Neon replay branch `lexa-phase3-security-replay-20261021` (`br-dark-breeze-b1mgcaxj`). The branch recorded all three versions; `intelligence_jobs`, `intelligence_runs`, `intelligence_documents` and `intelligence_document_reviews` are present with both row-level security and forced row-level security enabled. The document tables have tenant/branch-scoped policies for `lexa_app`. No migration was run against the live `lexa-live` branch.

**56-day refresh check:** on that replay branch, the new backfill function processed two active tenants on separate bounded calls (`processed_count=1, failed_count=0` per call). A third call correctly returned zero work. Read-only verification then found a recent successful 56-day window for both active tenants, from 30 August 2026 through 24 October 2026. These are coverage-window checks, not proof of recorded demand: forecasts must still remain unavailable or clearly marked insufficient where completed sales history is absent.

## Validation run in this preparation environment

- `unzip -t` passed for the incoming archive before repair.
- Python source syntax/AST compilation is checked during packaging.
- Migrations 045–047 and the real 56-day worker function were tested against the non-production Neon replay branch described above. Production migration state was checked read-only and remains separate.
- The complete API pytest and frontend TypeScript/production build suites were not run locally because the ZIP contains only changed/marker files, not the entire application or web dependencies. This ZIP includes updated API and web contract tests for the next GitHub Actions run.
- The latest source on GitHub had a red Main Build CI run because older contract tests expected a disabled, non-interactive assistant. The included test updates validate authenticated server-side routing, tenant privacy, and the live chat instead of requiring the assistant to stay disabled.
