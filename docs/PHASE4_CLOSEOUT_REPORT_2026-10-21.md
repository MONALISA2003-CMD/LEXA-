# LEXA Phase 4 closeout — 21 October 2026

## Summary

The Phase 4 implementation candidate has been consolidated as a safe overlay for the latest Phase 3 final-cutover source. This pass also fixed a KPI definition error and two dashboard integration regressions that source-only acceptance checks surfaced:

1. **Collected today:** now sums `RECORDED` payment-ledger rows for the tenant's business date and base currency, rather than summing the `amount_paid` field only on today's completed sales. This correctly includes separately recorded payments against receivables and keeps collection separate from sales.
2. **Currency consistency:** the API reports the tenant profile currency, filters daily sales/payments/receivables to that currency, and passes it to analytics and chart formatting rather than always formatting numbers as UGX.
3. **Inventory scale correctness:** the new `/api/v1/inventory/summary` aggregates stock value and exception counts across all locations accessible to the current user, without using the capped detail endpoint. The display's top attention list is intentionally bounded.
4. **Dashboard state correctness:** removed stale `balancesState` references from the dashboard after switching it to the inventory-summary endpoint; added source-contract checks to prevent reintroduction.
5. **Accessibility / resilience:** retained chart SVG title/description and daily data table, gap-preserving trend rendering, selected range states, mobile layout rules, refresh/error states and optional browser acceptance test.

## Test evidence

- Frontend contract suite: **24/24 passing** (`npm test`, Node 22.16.0). These are the repository's Node contract tests, not the production build.
- Backend suite: **27 passed, 1 skipped**. The skipped auth-refresh integration requires API test dependencies not installed in this runner.
- Python compileall: pass.
- Migration manifest integrity/separation: pass. The strict source checker still reports six accepted historical source substitutions; this Phase 4 patch adds no migrations.
- Standalone TypeScript transpilation check: **33 `.ts`/`.tsx` files parsed, zero syntax diagnostics**. This is a syntax check only, not a full typecheck.

## Release blockers that remain

- Only Node 22.16.0 is present locally; the application pins Node 24.x.
- `npm ci --offline` cannot complete because `undici-types@6.21.0` is not cached. Network name resolution for the package registry is unavailable in this execution environment.
- Vercel Sandbox creation returned **HTTP 402** because Hobby snapshot storage quota was exceeded; the API reported reset on **1 November 2026**. The previous package session has no snapshot to resume.
- Full TypeScript typecheck and Next.js production build were therefore not completed.
- Authenticated Playwright browser acceptance was prepared but not run; Playwright is not installed as a direct dependency and no non-production authenticated storage-state file was supplied.
- GitHub `main` cannot be written through the current connection, and changes remain uncommitted. No preview deployment was created; no production database writes or environment changes were made.

## Decision

**Phase 4 source implementation: READY FOR CONTROLLED CI/PREVIEW VALIDATION.**  
**Phase 4 release acceptance: PENDING.**

Phase 5 feature design and isolated development can begin from this candidate, but production promotion should wait until a clean Node 24 install/typecheck/test/build, authenticated preview/browser acceptance and source/deployment alignment checks have passed. This distinction avoids declaring a green production release on the strength of partial local tests.

Apply the overlay on top of the latest Phase 3 final-cutover source package. Do not replace the whole source tree with an older reconstructed ZIP, because doing so could omit accepted Phase 3 migration `031` and related router changes.
