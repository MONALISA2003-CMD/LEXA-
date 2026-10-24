# LEXA Intelligence — Phase 2: Rules-first Intelligence and Daily Brief

**Phase:** 2 — deterministic rules-first intelligence  
**Baseline reviewed:** `MONALISA2003-CMD/LEXA-`, `main` ZIP-upload commit `1fd4ee081bf45be6c78e330e52851d8a33bb4667`  
**Dependency:** the Phase 1 overlay supplied in `../phase1/` must be installed alongside this increment.  
**Execution model:** synchronous, read-only, deterministic; no LLM/provider call.

## Product outcome

LEXA gains a cross-module daily brief that ranks source-backed business findings without replacing the underlying accounting, inventory, sales, purchasing or analytics systems. It composes the existing analytics insight calculator rather than duplicating its SQL. The existing deterministic builders remain the source of truth for sales movement, gross-margin movement, stock risk and customer/supplier balances.

The brief's first version is intentionally seven calendar days through the tenant-local business date, with a same-length preceding comparison period for the existing calculator. The currency is explicit and the UI sends the currency configured for the business; the API defaults to `UGX` if called directly, and callers may supply another three-letter currency. It never adds currencies together.

## New API

`GET /api/v1/intelligence/daily-brief?currency_code=UGX`

Authentication and `analytics.read` permission use the existing LEXA dependency. Tenant and user IDs are taken only from the validated server context. The endpoint obtains the business date through `public.lexa_business_date(now(), tenant_id)`, calculates the preceding seven-day period, and calls the shared deterministic insight service.

Response categories:

- `action_items`: only current (`available`) findings marked `critical` or `attention`, sorted by severity then stable rule order.
- `information_items`: positive, informational, partial and no-finding observations that do not meet action criteria.
- `data_quality`: stale or unavailable sources. Their metrics and comparisons are deliberately removed even if a source regresses and returns stale values.

Every item carries a stable rule ID, source insight ID, severity/status, bounded summary, safe same-app evidence link, source table names, record count, source freshness, and any available metric/comparison/details. Links cannot supply an external origin. The response includes rule version, scope, period, data quality counts, last successful analytics refresh, and explicit advisory-only flags.

## Architecture

`GET /analytics/insights` and the new daily brief both use `app.intelligence.insight_service.calculate_business_insights`. The installer extracts and moves the existing insight body into the shared service, then keeps `/analytics/insights` as a thin API wrapper. The new daily-brief endpoint calls the same service directly. This is a source-code refactor, not an HTTP loopback and not a second SQL implementation.

`app.intelligence.daily_brief.build_daily_brief` is a pure deterministic function. It has no database, provider, file, network, or business-write capability. Prioritization is rules-based and versioned. The existing `/intelligence` web page consumes the endpoint through a typed API helper and renders urgent review items, evidence links, informational links, and a distinct data-quality state. LLM-generated explanations are not part of Phase 2.

## Safety invariants

- No model/provider API is called by daily brief.
- No SQL from a model or user is executed.
- No business record is created, updated, posted, reversed, fiscalized, paid, received or deleted.
- The existing insights calculator fails closed if tenant-wide analytics would exceed the user's branch authorization.
- Missing/stale source data is reported as such, never converted into a zero-valued business metric.
- Separate currencies are processed separately.
- Evidence links are internal relative paths only.
- Recommendations remain review prompts; they are not executable jobs or commands.
- No Phase 2 database migration is introduced. It does not depend on Phase 1's future durable intelligence-job schema being applied.

## Scope deliberately deferred

Document OCR/extraction, predictive forecasts, stored insight lifecycle/acknowledgement, event-driven background execution, proactive alerts/notifications, external LLM explanation, and approved business actions remain future increments. The included frontend integration is the first read-only brief panel, not a full workspace rewrite, push-notification service, or mobile/offline implementation.

## Phase 2 acceptance checklist

- [x] Bundled Python syntax and Phase 1 + Phase 2 synthetic tests pass (20 Phase 1 + 9 Phase 2).
- [x] Synthetic installer tests cover shared-service extraction, fail-closed source anchors, capability flags, typed web API helper, page integration, and idempotence (6 installer tests).
- [ ] Install onto the current LEXA source in a disposable working tree and review the full diff, including the web type/API client and Intelligence page.
- [ ] Verify route registration and OpenAPI; verify `analytics.read` denial/allowance using API tests.
- [ ] Test full-branch-scope denial for restricted members; no tenant or branch ID accepted from request parameters.
- [ ] Run existing analytics/business-insight regression tests after extraction; compare before/after payloads for the same fixtures.
- [ ] Run all normal API tests and project CI on the installed source, not just tests bundled in a ZIP.
- [ ] Run the repository's Node 24 typecheck, test suite and Next.js production build; review the daily-brief panel at desktop and narrow/mobile widths.
- [ ] Perform a disposable PostgreSQL replay for Phase 1 migration 045 separately; no production migration is authorized by this package.
- [ ] Review stale/no-row, multiple-currency, stock-risk overlap, `public.lexa_business_date`, and failure behaviour.
- [ ] Do not enable external AI providers or deploy from this bundle without a separate release decision.

## What is still open from Phase 1

The Phase 1 ZIP is present on `main`, but the latest upload commit reviewed here adds the ZIP file itself, not its Python modules or migration to the application source. The overlay must still be applied to an authorized LEXA checkout. Its 20 synthetic tests pass locally when run with `PYTHONPATH=.` from the bundle's API directory; that does not validate the full upstream suite or PostgreSQL migration. Migration `045_intelligence_foundation.sql` remains a candidate and has not been executed. The visible status on the ZIP-upload commit is a successful Vercel check; no Python or PostgreSQL status was surfaced for that commit. The provider execution path remains deliberately disabled.
