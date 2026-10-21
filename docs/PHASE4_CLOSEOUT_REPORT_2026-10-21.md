# LEXA Phase 4 closeout — 21 October 2026

## Summary

Phase 4 implementation work has been completed as a source candidate. It fixes dashboard correctness, expands analytics visibility and adds acceptance documentation. **Phase 4 release acceptance is not yet closed**, because the exact accepted Phase 3 source was not fully reconciled and the clean Node 24/browser/deployment gates could not run in this execution environment.

### Implemented

1. **Collected today:** sums `RECORDED` payment-ledger rows for the tenant's business date and profile currency, rather than only `sales.amount_paid` on newly completed sales. This includes separately recorded receivable payments and keeps cash collection distinct from sales revenue.
2. **Currency consistency:** the API reports the tenant profile currency, filters the daily sales/payment/receivable KPIs to that currency and passes the configured currency to analytics and chart formatting instead of always assuming UGX.
3. **Inventory scale correctness:** `/api/v1/inventory/summary` aggregates stock value and exception counts across all locations accessible to the current member, without using the capped detail endpoint. The attention list is separately bounded.
4. **Dashboard state correctness:** removed stale `balancesState` references after switching the dashboard to the inventory-summary endpoint; added a regression contract to prevent reintroduction.
5. **Charts and UX:** retained accessible SVG chart descriptions and daily data table, gap-preserving trend rendering, selected date ranges, mobile layout, independent loading/error states and the optional browser acceptance test.
6. **Product governance:** delivered KPI definitions, acceptance matrix, source reconciliation, overlay instructions and machine-readable closeout status, alongside `FRESH_NEW_PRODUCT_STRATEGY.md`.

## Test evidence

- Frontend contract suite: **24/24 passing** with `npm test` on Node 22.16.0. These contract tests are not the production build.
- Backend suite: **27 passed, 1 skipped**. The skipped auth-refresh integration requires API test dependencies unavailable to this runner.
- Python `compileall`: pass.
- Migration-manifest integrity/separation check: pass. The strict source checker still reports six accepted historical SQL substitutions; this Phase 4 work adds no migration.
- Standalone TypeScript transpilation-only check: **33 `.ts`/`.tsx` files parsed, zero syntax diagnostics**. This does not replace `tsc --noEmit`.

## Remaining release blockers

- **Source rebase:** `commerce.py`, `inventory.py` and `analytics.py` candidate blobs differ from currently fetched GitHub `main` blobs. Their replacement content includes preserved API source-overlay changes as well as Phase 4 changes; it must be reconciled against the exact accepted Phase 3 final-cutover ZIP before committing. The active workspace does not contain that ZIP, and only selected stable-file hashes could be checked.
- **Node 24 clean install/build:** local runtime is Node 22.16.0 while the app requires Node 24.x. `npm ci --offline` cannot complete because `undici-types@6.21.0` is not cached and registry DNS/network is unavailable. Full typecheck and Next.js production build were not completed.
- **Vercel sandbox:** new sandbox creation returned HTTP 402 because Hobby snapshot storage quota was exceeded; reset indicated as 1 November 2026. The previous package session has no snapshot to resume.
- **Authenticated browser acceptance:** the test is prepared but was not run. Playwright is not a direct app dependency in the lockfile, no authorized lockfile update/browser install ran, and no authenticated non-production storage-state file was supplied.
- **Commit/deploy:** GitHub write access is denied by the current integration. No preview deploy, production DB write or environment modification was made.

## Decision

**Phase 4 implementation candidate: PREPARED.**  
**Phase 4 release gate: PENDING SOURCE REBASE + NODE 24 BUILD + AUTHENTICATED PREVIEW ACCEPTANCE.**  
**Phase 5 planning/development: UNBLOCKED; do not promote Phase 4 to production yet.**

Apply this as a reviewed overlay on the final Phase 3 source, preserving migration `031_phase3_auth_surface_rls.sql` and the accepted Phase 3 router mounts. Reconcile the three API route files first, then run the release matrix. This is the quickest safe way to start Phase 5 without risking accepted Phase 3 security work.
