# LEXA Phase 1 repair + Phase 2 acceptance source patch

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

The latest historical failed canonical Main Build CI inspected in this repair was `40100560783` on the old SHA `d5be996d8cf45c93200351c6a21251c4d3a6c934`. Source fixes for those five known contract failures are present in the current main files, but a fresh green run on the resulting source SHA was not confirmed. Local validation for this patch passed Python compilation, 2/2 API static contracts, 5/5 focused Node checks, and TypeScript syntax transpilation for the new Playwright spec/setup/config (zero syntax diagnostics). The full API suite, full Node 24 suite, typecheck, production build and authenticated staging E2E remain release gates.

## Apply

Upload the ZIP at repository root with LEXA ZIP Extractor. Confirm it generates a commit touching canonical `apps/api/...` and `apps/web/...` paths and dispatches the one canonical `LEXA Main Build CI`. Verify all CI jobs on the exact new commit before deployment. Do not enable staging-write acceptance against `lexa-green.vercel.app`, `lexa-n10e.onrender.com`, or any production database. See `START_HERE.md`, `PHASE1_DATABASE_EVIDENCE.md`, `PHASE1_VALIDATION.md`, and `PHASE2_STAGING_ACCEPTANCE.md` for operational details.
