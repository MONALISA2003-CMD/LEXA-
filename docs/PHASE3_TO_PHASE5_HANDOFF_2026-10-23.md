# LEXA Phase 3–5 implementation candidate — 23 October 2026

## Status

**Source candidate prepared; not yet release-accepted, merged, or deployed.** This package includes the prior Phase 0–2 UX/setup improvements plus deeper Phase 3–5 sales, inventory/purchasing, and accounting safety work. No production database migration, data rewrite, Vercel promotion, Render deployment, or production alias change was performed in this work.

## What changed

### Phase 3 — Sales and checkout integrity

- Sales and the sales dashboard now require an explicitly saved, valid three-letter business currency. The old implicit `UGX` fallback is removed. A checkout in another currency receives a conflict response until an approved foreign-exchange path exists.
- Existing idempotent checkout, split-tender, return/refund and inventory-ledger flows are retained.
- The sales acceptance journey now verifies that a completed sale is linked to a posted sale-recognition journal and its recorded payment journals, and that all linked journals use the transaction currency.
- Write-enabled browser acceptance requires an explicit staging flag, hostname allow-list, a disposable tenant fixture, a disposal/reset declaration, and a readiness response proving the proxied API environment is `staging`/`test` with database and cache healthy. The known production frontend/API hostnames are rejected.

### Phase 4 — Inventory and purchasing

- Supplier prices/costs, purchase orders, receipts, landed costs, supplier bills, and supplier payments validate and normalize currency explicitly.
- Inventory-affecting purchasing operations are blocked when they would value stock in a currency other than the saved business currency. That is a deliberate safety boundary, not a replacement for a proper FX/subledger implementation.
- The purchasing UI no longer quietly fills write payloads with `UGX`; it validates supplier currency and shows an actionable message if a foreign-exchange workflow is required.
- Business currency cannot be changed after monetary or stock history exists, including supplier costs, landed costs, payment allocations, supplier ledger entries, journals, sales/returns and inventory transactions. This prevents a settings edit from re-denominating past records in reports.
- The existing isolated purchasing E2E covers supplier → approved order → partial receipt + landed cost → supplier bill → payment → return and stock/supplier balance checks. The combined Phase 3–5 release gate requires this journey as well as the sales/accounting journey.

### Phase 5 — Finance/accounting integrity

- Expense drafts now require the saved business currency; foreign-currency expenses are rejected until an approved FX/accounting path exists.
- New migration `043_phase5_journal_currency_guard.sql` tightens `post_journal_entry`: a journal must declare a valid currency, journal lines and any account denomination must agree with the header currency, there must be at least two lines, debits must equal credits, the accounting period must remain open, and all accounts must be active and postable.
- The runtime role `lexa_app` receives the explicit journal-posting execute grant; public execute is revoked. Existing posted data is not rewritten.
- Migration replay evidence now verifies both the posting guard and runtime grant.

### Release/CI safety

- The migration manifest now has **47 ordered, hashed inputs**. The runner remains plan-only by default, refuses non-disposable/non-loopback targets, and does not connect to Neon or production when invoked with `--plan-only`.
- The Node 24 CI job performs `npm ci`, TypeScript typecheck, frontend contract tests, frontend action/destination audit and a production build.
- A disposable PostgreSQL 16 replay job applies the ordered migration bundle only to a fresh CI database, then checks migration evidence, tenant isolation, RLS and privileges tied to the exact source commit SHA.
- Manual staging E2E jobs reject known production hosts and require explicit fixtures and QA auth states. The Phase 3–5 release gate writes checksummed, exact-SHA evidence only when backend tests, frontend build/typecheck, disposable replay, sales/accounting E2E and purchasing E2E all succeed. The evidence expressly does **not** authorize production deployment or migration.

## Verification completed in this environment

| Check | Result |
|---|---:|
| Python backend suite | **290 passed, 0 failed** |
| Frontend contract tests | **58 passed, 0 failed** |
| TypeScript/TSX syntax transpilation | **37 files, 0 syntax errors** with global TypeScript 5.8.3 (syntax check only) |
| Frontend action/destination audit | **Pass** — 29 files; 205 button-like controls, 48 forms, 72 links checked |
| Python `compileall` | **Pass** |
| Workflow YAML parse | **Pass** |
| Migration recovery manifest consistency | **Pass** — but six approved reconstructed historical source equivalents still require semantic replay validation |
| Strict migration source reconciliation | **Pass for source/disposition checks**; semantic validation is still pending |
| Migration plan-only | **Pass** — 47 input files hashed; no SQL was executed and no database connection was opened |
| Migration bundle SHA-256 | `031c396c42946210e3ab4f61a9ab6c7a3b3faf0bc62bfb1728dbbe584879471d` |

One unrelated Starlette deprecation warning remains in the cookie-refresh test.

## Release blockers — do not mark complete yet

1. **Full frontend build/typecheck for this candidate is not verified here.** The environment only has Node `v22.16.0`, while LEXA requires Node 24; frontend dependencies are not installed. Syntax transpilation is not a full typecheck. Vercel Sandbox creation was blocked by the account's snapshot-storage usage limit (HTTP 402), and GitHub branch creation was denied by integration permissions (HTTP 403). The current production baseline commit `bde067ae0444dc3b345f2c12cc47572534455caf` is READY on both Vercel and Render, but that is not the new local Phase 3–5 candidate.
2. **PostgreSQL semantic migration replay is not run.** No local `postgres`, `psql` or Docker engine is available. The 47-file replay has only been hashed/validated in plan-only mode. It must pass the CI PG16 disposable replay before release.
3. **Authenticated staging E2E is not run.** The staging URLs, fixtures and QA storage-state secrets are not configured in this environment. CI is set to fail closed when those dependencies are missing, rather than silently accept a skipped browser journey.
4. **Production database is behind this candidate.** Neon `lexa-live` remains at migration `031_phase3_auth_surface_rls`; migrations `033` through `043` are pending for that live branch. Do not apply these migrations directly to production. The clean-replay job must pass on a disposable database and then the schema plan needs a separately reviewed, backup-protected deployment sequence.
5. Six reconstructed historical migration equivalents are recorded as approved replacements rather than exact historical bytes. The recovery manifest passes its consistency checks, but the equivalents remain pending schema/RLS/security validation through clean replay.
6. **The candidate is not published.** GitHub branch creation returned HTTP 403. Therefore the CI workflow additions in this package have not run on GitHub and no candidate build/replay/E2E artifacts exist yet.

## How to complete candidate acceptance

1. Publish/review the candidate in GitHub once repository write permissions are available. Do not copy it directly onto production `main` as an unreviewed replacement.
2. Run the `LEXA CI` workflow with `run_clean_replay=true` and `run_phase345_staging_e2e=true`. This requires repository variables `LEXA_PHASE345_STAGING_URL` and `LEXA_PHASE345_STAGING_HOSTS`, and secrets `LEXA_PHASE5_ACCEPTANCE_FIXTURE_JSON`, `LEXA_PHASE5_STORAGE_STATE_B64`, `LEXA_PHASE5_MANAGER_STORAGE_STATE_B64`, plus the existing purchasing E2E variables/secrets `LEXA_PHASE7_STAGING_URL`, `LEXA_PHASE7_STAGING_HOSTS`, `LEXA_PHASE7_ACCEPTANCE_FIXTURE_JSON`, `LEXA_PHASE7_STORAGE_STATE_B64`.
3. Staging fixtures must point at an isolated test tenant/database and declare `environment: staging`, `disposable_scope: true`, and `reset_strategy: dispose_test_tenant`. The sales scenario additionally requires a cashier role, three stock-tracked fixture variants at the expected prices, two compatible payment methods and a manager QA session for direct journal-line reconciliation. Purchasing needs its own seeded manager/finance fixture.
4. Inspect the exact-SHA migration evidence and the release acceptance artifact. Only after those pass should the team review the production backup/restore plan, compare the deployment source SHA across Vercel and Render, review the pending schema deltas against live migration `031`, and separately approve a staged production rollout with rollback instructions.

## Safety statement

**No live LEXA records were changed. No production SQL was executed. No Vercel or Render deployment was triggered by this candidate work.**
