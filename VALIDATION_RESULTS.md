# LEXA CI + Phase 1–4 validation results

**Date:** 24 October 2026  
**Target:** `MONALISA2003-CMD/LEXA-`, branch `main`  
**Purpose:** fix CI contract regressions and add a bounded predictive baseline without modifying live infrastructure or business data.

## Passed in the source-overlay environment

| Check | Result | Scope |
|---|---:|---|
| Python focused tests | **61 passed** | Intelligence Phase 1/2/3 contracts, provider-settings regression, and the Phase 4 demand-forecast unit/source contracts |
| Node contract tests | **11 passed** | Seven existing Phase 3 contracts and four new Phase 4 demand-forecast contracts |
| Python compilation | **PASS** | Overlay API application and tests |
| Node syntax checks | **PASS** | Revised Phase 5 sales and Phase 7 purchasing contract tests, plus forecast tests |
| TypeScript/TSX transpilation | **PASS** | New forecast page/client and modified intelligence UI modules; syntax transpilation only, not `tsc --noEmit` |
| ZIP integrity/layout | **PASS** | Checked at final packaging: required root markers, no unsafe paths, cache files or bytecode |
| CI test-root-cause correction | **PASS by source review** | Default workflow contracts now check its real API/web/Compose jobs; write-enabled staging safety is checked in Playwright sources, not by expecting absent jobs in ordinary CI |

## Root cause of run 40064896058

`Web typecheck, contracts and production build` passed TypeScript and failed the frontend contract stage. `phase5-sales-cockpit.test.mjs` and `phase7-purchasing-contract.test.mjs` were asserting identifiers/details for optional staging E2E and database replay jobs that the canonical `LEXA Main Build CI` does not run. The fix does not disable the guard tests. It asserts the existing lightweight CI structure while retaining checks that the sales/purchasing E2E entry points require a disposable staging environment, reject production hosts, require explicit write opt-in, verify API readiness, and protect authenticated state.

The earlier run 40063918855 had different root causes (nullable profile currency, provider settings fields absent from Pydantic `Settings`, and outdated migration-order assertions). Those source fixes remain included.

## Phase 4 forecast validation

The pure forecast logic validates non-negative finite unit values, requires exactly 56 consecutive days, requires at least six days of observed demand, uses only prior observations at each rolling test origin, computes MAE and WAPE safely, compares against last-week-same-weekday, and omits WAPE when holdout actuals are zero. The API requires a successful refresh covering the complete 56-day range and completed within 72 hours before treating missing product-day rows as zero.

Forecast output is advisory and read-only. No model provider is called. The endpoint has no transaction, inventory, purchasing, or finance write path. Stockout-censored demand is not corrected and is explicitly disclosed as a limitation.

## Not verified here

- Full repository API test suite against all non-overlay source and integration files.
- Full Node 24 `npm ci`, `npm run typecheck`, complete `npm test`, and Next production build. This overlay is not the full repository checkout with the lockfile and all supporting pages, so the full suite must run in GitHub Actions after extraction.
- SQL parsing/execution and clean replay against disposable PostgreSQL; actual RLS/cross-tenant and branch-adversarial probes; migrations 045/046 remain candidate only.
- Actual API endpoint output against live tenant data, and a production `GET /api/v1/intelligence/capabilities` check for deployed OCR binaries.
- Authenticated staging/mobile acceptance for the new forecasting view, document flow, or write-enabled purchasing/sales flows.
- Post-upload deployment status for this ZIP's new commit.

## Release safety

- External provider execution remains disabled by default; the legacy AI assistant pause remains in place.
- No production data, migration, runtime configuration, secrets, or deployment were changed as part of preparing this ZIP.
- The ZIP intentionally does not include `.github/workflows/`; the existing extractor protects that directory.
- Upload to `main`, then verify CI and the Render/Vercel deployments for the exact new `[lexa-extractor]` source SHA.
