# LEXA Stages 1–5 — Live Audit and Build-Fix Candidate

**Audit date:** 22 October 2026 (UTC)  
**Candidate:** `2.13.1+stage1-5-buildfix.candidate.20261022`  
**Decision:** **Do not call this a production-accepted release yet.** The confirmed Vercel TypeScript build failures have been fixed in this candidate and regression contracts added. Automated source tests pass. Live review also exposed a significant database drift: the configured `lexa-live` schema stops at migration 031, while the current candidate requires migrations 033–040. No production SQL or deployment mutation was performed.

## Executive status

| Area | Finding | Status |
|---|---|---|
| Stages 1–3 source | Canonical source structure, workflow connections, security and UI polish are carried forward from prior candidates | Source audit; full live acceptance pending |
| Stage 4 reporting | Date presets, independent states, exact-value tables, drill-through, scope-aware CSV, reports implemented in source | Source tests pass |
| Stage 5 acceptance | 44 migration inputs/hash manifest, guarded clean-replay harness, Phase 8 postconditions and staging-only browser lanes | Harness passes plan validation; acceptance incomplete |
| Local checks | 262 API tests, 54 frontend contract tests, Python compile, migration checks, TS/TSX syntax transpilation | Pass |
| Vercel main | Latest production deployment fails at Next.js TypeScript check | Known compiler errors fixed in candidate; not yet built on Vercel |
| Stable frontend link | `https://lexa-green.vercel.app` still resolves to a prior READY deployment on commit `f1e0e2f1373d7912ae1cab694615990071ef07b4` | Stale relative to latest main |
| Live database | Neon project `LEXA`, branch `lexa-live`; migration ledger latest is `031_phase3_auth_surface_rls` | **Behind current candidate** |
| Render | Not inspected through the account connector because its API requires workspace confirmation | Pending workspace confirmation |
| GitHub write | GitHub connector returned HTTP 403 `Resource not accessible by integration` on a blob write | Candidate not pushed by this session |

## Verified Vercel failure and exact source fixes

The Vercel project is `lexa` (`prj_QicfCnse8LU6hnq4ik9liHc289VW`). The latest production deployment checked was `dpl_9XjcgzpSnBFo3gPNkSxFbo8Rmmdd` on main commit `cf25deac57832ac897f76a86b03928664a85ddb6`. Next compilation succeeded, then `npm run build` failed during TypeScript validation with these reported errors:

- `apps/web/app/accounting/page.tsx`: accesses to `.value` on `PromiseSettledResult<Reconciliation[]>` and `PromiseSettledResult<AccountingAccount[]>`, plus implicit-any callback parameters.
- `apps/web/app/customers/page.tsx`: accesses to `.value` / `.reason` without retaining `Promise.allSettled` discriminant narrowing, and possible null dereference of business profile data.
- `apps/web/app/purchasing/page.tsx`: the UI referenced `SupplierBill.match_difference`, which is not part of the API type. The backend contract field is `match_variance`.

Candidate fixes:

1. Store the narrowed `Promise.allSettled` result in a local discriminated-union variable before reading the fulfilled value or rejected reason; this also restores callback inference.
2. Make the customer business-profile currency access nullable-safe.
3. Use `match_variance` consistently with the current supplier-bill response/type.
4. Add `apps/web/tests/stage5-build-regressions.test.mjs` so these failures have explicit regression assertions.

The current GitHub workflow run that reports success is named **LEXA ZIP Extractor**. It extracts/commits the source package; it is **not** evidence that Next.js typecheck/build passed. A query for `.github/workflows/lexa-ci.yml` in the actual remote `main` returned 404; the build/test workflow included in local candidate files is not installed in the remote repo by this session. The GitHub status on the latest `main` SHA reports a Vercel failure.

The runtime-error aggregator reported no grouped runtime errors in its seven-day window, and the recent runtime error/fatal log query returned no entries. Those results do not negate the verified build failure, because it fails before the new code runs.

## Live database/source parity evidence

Read-only queries were made against Neon project `wispy-mud-75323042` (`LEXA`) and its primary/default branch `br-soft-star-b1dj2m2w` (`lexa-live`). The queries read schema metadata and migration ledger only.

- Latest recorded migration is `031_phase3_auth_surface_rls` (applied 21 October 2026).
- No `032`–`040`-numbered rows were present in the live migration ledger for this branch.
- `purchase_orders` and `purchase_receipts` exist.
- `supplier_bills`, `supplier_payments` and `supplier_ledger_entries` do **not** exist.
- The Phase 8 postconditions are absent: `expense_records.reversal_journal_entry_id`, its reversal index, the analytics metric `expense_reversals_total`, tenant-safe reversal foreign key and a status constraint supporting `REVERSED` are all missing.
- The routine `public.post_expense_journal(uuid,uuid)` does exist, but that alone does not satisfy the migration 040 schema/analytics requirements.

Therefore the current live database and the Stage 4/5 source are not aligned. The migration plan is complete only as a reviewed source plan; it has **not** been executed on this live database. This audit did not change the database. Before rollout, run a clean disposable PostgreSQL replay for all 44 inputs, review the six historical source dispositions, back up and validate recovery, then apply the approved pending migrations with a deliberate deployment window. Do not apply the full clean replay to the existing live database.

## Render/backend review status

The configured source has Render blueprint settings under `render.yaml` for an API web service, and `.env.example` documents a Render API URL. However, the connected Render tool returned `no workspace selected`. It lists one workspace named **My Workspace** with ID `tea-d9cssgflk1mc73br1cp0`. The account/workspace has not been selected because the correct workspace needs explicit confirmation. Therefore Render deploy status, current service commit, `/health` and `/ready`, service logs and database attachment remain **unverified** in this report. No Render service or environment variable was edited.

Vercel has production variables named `LEXA_API_URL` and `NEXT_PUBLIC_API_URL`, but the connector returned encrypted envelopes instead of usable URL values. Their targets exist, but their actual origins could not be verified. Thus frontend-to-backend URL parity has not been proven yet.

## Stage-by-stage source coverage

### Stage 1 — foundation and source integrity

- Root-oriented project layout is preserved for the archive and source extractor.
- API security, auth/session hardening, tenant context, RLS policies and migration source controls from earlier candidate work are retained.
- Migration recovery/source checkers are included. The six historical source substitutions are declared as permanent equivalent dispositions; semantic validation still must occur through the clean replay and security checks.
- Important: passing manifest/path/hash checks does not prove a live schema has every expected table or that every historical SQL replacement is semantically identical.

### Stage 2 — connected business flows

- Inventory, sales, payment/returns, customer balances, purchasing/receiving, supplier balances and accounting/report flows are connected at the source/API contract level.
- UI values should come from authorized API data; unavailable results must be displayed as unavailable rather than fabricated zeroes.
- Live acceptance still needs authenticated cross-branch/tenant journey tests with real staging fixtures.

### Stage 3 — consistent interface and user-facing errors

- Emerald Fusion styling, responsive layout, reusable workspace navigation, accessible chart/table patterns and plain-language error handling are retained.
- Source/test checks do not substitute for a full browser/device check or an authenticated live walkthrough.

### Stage 4 — reporting

- Date presets and manual ranges, independent panel loading/error/empty states, sales trends, location/payment/expense/product/customer/stock views, exact-value tables, drill-through and safe CSV export are present.
- All-date balances and current inventory snapshots are labelled accurately; report money is recorded activity, not external provider verification; stock cost is not revenue/cash.

### Stage 5 — acceptance/release

- The 44-input migration replay plan includes `migrations/040_phase8_finance_workflows.sql` and its postconditions.
- Replay runner defaults to plan-only and guards apply mode against remote/non-empty/production-looking targets.
- Separate read-only reporting, sales-write and purchasing-write Playwright suites require explicit staging host, test fixture and QA authentication opt-ins.
- Actual live acceptance is not complete: Node 24 full build/typecheck, disposable PostgreSQL replay, authenticated browser journeys and production parity are still required.

## Automated checks run for this candidate

- Backend tests: **262 passed** (one existing Starlette cookie deprecation warning).
- Frontend contract tests: **54 passed**, including the new TypeScript build-regression contract.
- Python `compileall`: passed.
- Migration recovery/source checkers: passed; six historical replacement sources are still marked for semantic replay validation.
- 44 migration input paths and hashes: passed in plan-only mode; bundle SHA-256 `15555832b8153b52f412937de6f153e96afb1c6f6187a15b487b5e874ed5ae46`. No database connection opened during this check and no SQL executed.
- Frontend action audit: 28 TypeScript/TSX files parsed; 195 button-like controls, 44 forms and 71 links passed the source-level audit.
- TS/TSX syntax transpilation: 35 files, 0 syntax errors. This used globally available TypeScript 5.8.3 and is **not** the project Node 24/TypeScript 5.9.3 production typecheck.
- A local attempt to run `npm ci --offline --no-audit --no-fund` could not install dependencies: npm returned `ENOTCACHED` for `undici-types@6.21.0`, and this environment runs Node 22.16.0 while the project requires Node 24.x. Therefore `npm run typecheck` and `npm run build` remain **not run locally**. Vercel's real build did run and exposed the TypeScript errors listed above; those errors are patched in this candidate but need a new remote build to verify.
- Final candidate archive integrity: ZIP contains 411 files with repository-root paths; CRC check passes; no real `.env` files, `node_modules`, `.next`, `__pycache__`, `.pytest_cache`, or Python bytecode are packaged. A fresh extraction reran the acceptance runner: 262 backend tests, 54 frontend contract tests, Python compilation, migration recovery/source checks, the 28-file frontend action audit, and 44 migration input/hash checks passed. The separate 35-file TS/TSX syntax transpile also passed with zero syntax errors.

## Release order (do not skip)

1. Confirm Render `My Workspace` is the right workspace, inspect API service/deploy/runtime logs, verify `/health` and `/ready`, source branch/commit and its Neon connection target without exposing secrets.
2. Run project Node 24 `npm ci`, `npm run typecheck`, `npm run build`, all Python/frontend tests and a clean disposable PostgreSQL replay; retain replay evidence against an immutable commit SHA.
3. Exercise authenticated staging journeys end to end: registration/login/session restore; catalog → stock → sale → payment/receivable → Finance/Reports; purchase order → receipt → stock → supplier bill/payment; expense → posting/correction → reports; and tenant/branch isolation/permission-denial paths.
4. Review and back up the live database. Apply only the approved pending migrations to the configured live branch in the correct order; verify RLS, grants, schema, `/ready`, and representative API requests after the migration.
5. Publish the corrected source to GitHub through the user's permitted upload/push path. Wait for a **READY** Vercel deployment on that new exact commit and successful API deployment on the same source line, then verify `lexa-green.vercel.app` resolves to that new deployment. Do not promote a failed or unverified build.
6. Keep Phase 9 AI on hold until Phase 8 acceptance is signed off; final production gate remains Stage/Phase 12.

## Acceptance decision

This ZIP is a **build-fix candidate**, not a claim that production is clean or that deployment is complete. The known Vercel TypeScript failures have been fixed at source level and regression assertions pass. **The live frontend, backend and database are not yet demonstrated to be on the same release**: the stable frontend alias is older than current `main`, the Neon branch lacks migrations 033–040 (and required supplier/Phase 8 objects), and Render logs await the user's workspace confirmation. No production database or deployment changes were made by this run.

## Research references

The reporting/acceptance design also draws on these official references: [Texas Department of Insurance — data visualization guidance](https://www.tdi.texas.gov/styleguide/style-guide-for-data-visualization-tools.html), [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/), [Playwright authentication](https://playwright.dev/docs/auth), [Render monorepo support](https://render.com/docs/monorepo-support), and [Vercel monorepo guidance](https://vercel.com/docs/monorepos). These inform UX, accessibility, secure browser state and deployment-root handling; they do not replace the live test gates above.
