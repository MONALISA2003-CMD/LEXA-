# LEXA P0 / P1 / P2 — completed source build candidate

Date: 2026-10-23
Package type: repository-root overlay ZIP for the existing LEXA GitHub ZIP update workflow.

## 1. P0 — sales, stock, and finance blockers

- Added a tenant- and active-branch-scoped customer history endpoint keyed by saved customer/party ID instead of fuzzy customer-name search.
- Customer history returns original sales alongside completed return value, recorded cash refunds, customer credit issued, and remaining customer credit. The frontend keeps these amounts separate so a return is not misrepresented as cash received.
- Customer history is paginated in batches of 100, with stale-request protection and a “Load older sales” action.
- Added explicit reversed-date guards to the trial-balance and income-statement reports.
- Preserved existing server-side checkout validation, payment-allocation safeguards, multi-line returns, credit/refund handling, inventory movement ledger, and idempotent write paths.

## 2. P1 — inventory and purchasing

The existing integrated workflows remain in the package: location-scoped stock balances and movement history, stocktake/adjustments/transfers, stock ageing and stock-health explanations, advisory replenishment recommendations, supplier records and price terms, purchase orders, partial receiving, landed-cost allocations, supplier returns/credits, supplier bills, payment allocations, and the supplier ledger. Replenishment remains advisory; it does not automatically change stock or create/approve a purchase order.

The source-path test and package-validation helpers were updated to use canonical project paths instead of the missing legacy `overrides/` copies. This allows the package's own validation suite to test the canonical files shipped to the app.

## 3. P2 — finance and reconciliation integrity

- Added forward-only migration `migrations/045_phase8_reconciliation_closed_snapshot.sql`. Payment/refund refreshes now skip `CLOSED` reconciliation headers in both the line-refresh and header-refresh loops, preventing a subsequently recorded money change from silently rewriting the prior day's closed reconciliation snapshot.
- The migration registers its version in `schema_migrations`; it does not alter prior migration files or business records during migration.
- Added API readiness checks for the migration and the two closed-status guards. `/ready` must not report full readiness until the database contract is installed.
- Added clean-replay-plan entry and runtime postconditions for migration 045; the plan now validates 49 migration inputs.
- Added contract tests for date range validation, customer history scoping/return totals, and the closed-reconciliation guard.

## Validation run

- Python backend + source tests: **351 passed**, one Starlette cookie deprecation warning.
- Frontend and package contract tests: **82 passed**.
- Frontend action audit: **PASS** — 32 TS/TSX files parsed; 213 button-like controls, 51 forms, and 89 links checked.
- Package validation helper: **PASS**.
- Migration recovery manifest: **PASS** for manifest/hash/separation/permanent-disposition consistency.
- Clean replay plan-only: **PASS** — 49 migration inputs are present and hashed. This command opened no database connection and executed no SQL.
- Migration source reconciliation: canonical source reconciliation passes, but semantic validation of six approved reconstructed historical equivalents remains pending. This is recorded as pending, not claimed as historical byte recovery.

## Not yet verified

- Full Next.js TypeScript check/production build: not verified locally. The available Node runtime is 22.16.0 while the project requires Node 24.x, and the local `node_modules/@types/node`, `@types/react`, and `@types/react-dom` directories are incomplete, producing TS2688 errors.
- Seeded authenticated staging E2E and an actual disposable-PostgreSQL execution of the entire clean migration replay: not run in this environment.
- Migration 045 has **not** been applied to any database. The included ZIP does not execute SQL automatically.

## Safe update order

1. Run the migration plan against an isolated disposable PostgreSQL database and complete the semantic/schema/RLS checks; do not point the replay script at Neon or production.
2. Apply migration 045 to an approved non-production/staging database through the project's reviewed migration process, then run the app using Node 24.x and complete the full web build and seeded E2E checks.
3. Only after those checks pass on the exact candidate SHA, use the existing GitHub ZIP update flow for `main` and verify the resulting Render API and Vercel frontend deployment commit.

No GitHub write, `main` update, Render/Vercel deploy, production migration, or production-data change was performed while assembling this archive.
