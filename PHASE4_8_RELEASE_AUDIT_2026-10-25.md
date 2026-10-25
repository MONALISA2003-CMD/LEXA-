# LEXA Phase 4–8 CI Repair and Acceptance Audit

**Source reviewed:** `MONALISA2003-CMD/LEXA-`, `main`, commit `7f931196af654cb697eb7b6863edac2e1db0ab0e`.
**Target:** Correct the exact CI failures in run `40184725822`, keep the Phase 2/5–8 acceptance safeguards, and document hosted release gates. This ZIP is a source overlay; it does not apply database migrations or deploy services.

## Exact CI failures fixed

Run `40184725822` failed for test-contract drift, not a failing business-rule test:

- API tests: **335 passed, 1 failed**. `tests/test_intelligence_phase3.py::test_replay_manifest_appends_candidate_migrations_in_order_without_production_opt_in` still expected only migrations 045–046 even though the current ordered manifest correctly includes 047 (56-day forecast-history worker) and 048 (Phase 7 authorization, reversals, and accounting).
- Frontend contracts: **108 passed, 2 failed**. `phase2-transaction-acceptance-contract.test.mjs` and `phase5-e2e-safety-contract.test.mjs` asserted the old exact Playwright `testMatch` array, omitting the subsequently added explicit Phase 7 reversal, approval-limit and allocation suites.
- Frontend typecheck passed. Docker Compose/HAProxy passed. The production web build was skipped after the frontend contract step failed.

The updated contracts now assert the complete ordered migration suffix (045, 046, 047, 048) and require the core Playwright matchers while allowing the separately gated Phase 7 suites. They do not disable those tests or loosen their staging safeguards.

## Phase specification cross-check

| Phase | Required behavior reviewed | Current source/test evidence | Remaining release evidence |
|---|---|---|---|
| 4 — UX, dashboard and reporting foundation | Calendar-range validation; currency-aware amounts; branch-scoped reports; empty/error/stale disclosure; report filtering and drill-through | Phase 4 dashboard/report contract tests and `test_stage4_reporting_acceptance.py` | Re-run the full candidate CI and production build after this overlay |
| 5 — Sales and accounting evidence | Completed sales and returns/refunds; payment states kept distinct from collected cash; source-backed gross profit/COGS; balanced journals; idempotent writes | Phase 5 sales acceptance contracts; refund/return accounting migration and API tests | Authenticated staging transaction acceptance; real journal parity under disposable PostgreSQL |
| 6 — Inventory intelligence | Stock counts, adjustments, location transfers, ledger/cost history, ageing, movement health and advisory reorder recommendations; rejected/duplicate/unauthorized writes | Phase 6 inventory contracts and staging-gated acceptance specs | Run write-enabled tests only with a disposable staging tenant; verify stock and cost history in PostgreSQL |
| 7 — Purchasing and authorization | Supplier → approved PO → partial receipt/landed costs → inventory and accounting; bill → payable → partial allocations/payment record; supplier return/reversal; role/currency approval caps; ledger-to-GL reconciliation | `test_phase7_approval_limits_rules.py`, `test_phase7_approval_reversal_accounting.py`, purchasing rules/model tests and frontend contracts all passed in the cited run | Migration 048 must be applied on a backup-verified rollout target; then pass authenticated staging E2E and readiness gate |
| 8 — Reports, analytics and forecasting | Accounting/transaction-backed measures; refresh failure/freshness; rolling 56-day backfill; insufficient/stale/empty history must not create a forecast; bounded read-only forecasts with limitations/backtest | Reports acceptance tests, forecast worker tests, `test_demand_forecast.py`, existing Phase 8 CI contracts | Verify an exact-SHA replay, continuous scheduled worker operation and authenticated report/forecast acceptance after deploy |

## Current hosted-state observations (read-only)

- **Vercel:** the latest observed production-target deployment is `READY` at commit `7f931196af654cb697eb7b6863edac2e1db0ab0e`.
- **Neon, project `LEXA`, default branch `lexa-live`:** the database's `schema_migrations` contains 039–047, including `047_analytics_forecast_history_backfill`, but **does not contain 048**. `purchase_approval_limits` is absent. The 56-day-history refresh was present and fresh at audit time: `from_date=2026-08-31`, `to_date=2026-10-25`, latest successful completion `2026-10-25T07:23:42Z`; the Phase 8 history/freshness gate was therefore satisfied by the current database evidence.
- **Render:** this session returned one available workspace named `My Workspace`, but Render's connector requires explicit workspace selection before listing services/deploys. No current Render green status or source-SHA parity is claimed here.

## Release safety (do not skip)

Migration 048 contains more than table creation: it installs purchasing approval/reversal protections, seeds account mappings, posts journals for existing posted purchasing records, and enables triggers/readiness gates. Do **not** apply it to live `lexa-live` based on ZIP creation alone. First produce and restore-test an encrypted backup, review the actual migration diff and expected journal postings on an isolated branch/database, run exact-SHA CI and authenticated staging acceptance, then schedule an owner-approved production rollout. Until 048 is installed and the backend readiness contract passes, Phase 7 is not production-green even though the source tests pass.

## Apply this overlay

Upload `LEXA_PHASE4_8_CI_REPAIR_2026-10-25.zip` at the repository root with `main` selected using the existing LEXA ZIP Extractor. It overwrites only the acceptance tests and supplies the Phase 7 closeout source already contained in the package. Then review the new exact-SHA GitHub Actions run. Do not infer Render or Neon health from a Vercel `READY` result.
