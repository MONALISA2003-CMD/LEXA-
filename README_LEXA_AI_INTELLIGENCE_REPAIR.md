# LEXA Phase 0/1/2 repair + CI run 40114334149 correction

This ZIP contains selected changed files at canonical repository paths for `MONALISA2003-CMD/LEXA-` and is intended for the existing **LEXA ZIP Extractor**. It is not a full source archive, installer or deployment. Root marker files (`apps/web/package.json`, `apps/api/app/main.py`, `migrations/`) allow the extractor to recognize and commit the real source tree. The archive includes no provider credentials or secrets and does not modify workflow files.

## Phase 1 — business-grounded assistant

- Exact factual questions about sales/net sales, recorded payments, recorded expenses, gross margin and current stock-health exceptions are answered from LEXA's own tenant-scoped projection data.
- Reads require permission, full authorized branch scope and fresh successful analytics coverage; stock-health advice also requires a fresh stock-health snapshot.
- Answers include source mode, source/date window, last refresh, response latency and an in-app evidence link.
- Missing/stale figures remain unavailable rather than being fabricated as zero.
- General advice uses the central Gemini/Groq question-only policy. Saved business records, customer data, tenant identifiers and business metrics are not attached to provider prompts. No model-driven business writes or automatic paid fallback are added.
- Compliance text and the stale CI contract expectations are aligned; this does not create a URA connection or self-activate EFRIS.

## Phase 2 — cross-module transaction acceptance

- Adds the read-only endpoint `GET /api/v1/commerce/sales/{sale_id}/evidence`, permission-, tenant- and branch-scoped, returning audit/outbox lifecycle metadata without payloads or idempotency keys.
- Adds a staging-only end-to-end test for idempotent checkout and replay, stock ledger quantity/cost, revenue/tax and COGS journals, partial payment and receivable settlement, outbox/audit evidence, and refreshed analytics.
- Adds backend and Node contracts for endpoint registration, authorization scope, redaction and staging guards.
- Does not require a migration. It relies on existing sales, inventory, payments/receivables, journal, audit, outbox, idempotency and analytics tables.

## Production database — updated 24 October 2026

Neon `lexa-live` has migrations `045_intelligence_foundation`, `046_intelligence_documents`, and `047_analytics_forecast_history_backfill` applied and verified. **Do not rerun them.** There are 134 public base tables, with RLS enabled and forced on every table. The bounded forecast-baseline refresh completed with zero failures and seven successful 56-day windows covering 30 August through 24 October 2026 for seven active tenants. Actual sales, payments, stock movements, journal entries and daily/product analytics rows remain empty. Refresh coverage does not imply real demand data or available forecasts.

## CI status and validation

The latest inspected canonical Main Build CI is `40114334149` on SHA `1e93fc87022bf7d31cae0ae00c537371af148ccb`. API unit/contracts, Docker/HAProxy and web typecheck passed, but Node contracts reported 97/99 because two older tests still asserted the former combined Playwright matcher. This bundle updates exactly those assertions to match the configured Phase 2 and Phase 5–8 patterns. The failure prevented the GitHub workflow Next production build step from running. A source-only regression probe against the current origin verified 13/13 Phase 5/7 contract conditions, and a matcher probe confirmed all six intended Phase 2/5/6/7/7-auth/8 specs are covered; that is not a rerun of `npm test`. The full CI run, production build and authenticated staging transaction acceptance remain release gates. GitHub branch creation was denied to the connected integration (403), so **CI is not yet declared green**.

## Apply

Upload the ZIP at repository root with LEXA ZIP Extractor. Confirm it generates a commit touching canonical `apps/api/...` and `apps/web/...` paths and dispatches the one canonical `LEXA Main Build CI`. Verify all CI jobs on the exact new commit before deployment. Do not enable staging-write acceptance against `lexa-green.vercel.app`, `lexa-n10e.onrender.com`, or any production database. See `START_HERE.md`, `PHASE1_DATABASE_EVIDENCE.md`, `PHASE1_VALIDATION.md`, and `PHASE2_STAGING_ACCEPTANCE.md` for operational details.
