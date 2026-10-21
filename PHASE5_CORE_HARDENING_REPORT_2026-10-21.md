# LEXA Phase 5 Core Hardening Report

**Date:** 2026-10-21  
**Package:** `2.9.3+phase5.core-hardening`  
**State:** Implemented in a local source candidate; **not release-accepted or deployed**.

## What was hardened

### Sale returns and refunds

- Refund capacity derives from recorded original payment allocations minus all previously recorded refunds for the sale. It does not reuse `sales.amount_paid` as though it were a gross immutable collection total.
- The source sale is locked while return/refund validation is performed, so concurrent return requests serialize at the sale boundary.
- A return cannot list the same sale-line ID more than once; this prevents validating separate quantities independently against the same remaining sale quantity.
- Partial returns prorate the original line discount, tax and line value by returned quantity.
- `NONE` settlement fails before writes when the return exceeds the remaining open receivable. The same guard is present at the database journal-posting boundary.
- The refund record is inserted before settlement totals are recalculated. Accounting and fiscalization trails are returned to, and displayed by, the product UI.

### Inventory costing and accounting

- Returned tracked inventory uses the original sale's immutable inventory ledger movements to derive its unit-cost basis, instead of using whatever average cost happens to exist at return time.
- Non-stock variants do not create inventory ledger entries.
- If a product is still configured as stock-tracked but its original sale movement cannot be found, the return fails closed with a reconciliation error rather than silently inventing a cost basis.
- The existing migrations 033–035 provide refund-settlement recalculation, idempotent return/COGS journals, customer-credit liability mapping, a pending EFRIS credit-note path when EFRIS is active, and the no-refund/open-receivable guard.

### Regression tests

- Corrected the refresh-cookie test to check the shared authentication helper that owns the cookie attributes, instead of expecting duplicated cookie flags in the route file.
- Added regression contracts for repeated sale-line IDs, original sale stock cost, non-stock inventory behavior, and missing original stock movements.
- Verified migration recovery manifest/hash separation and checked the observed migration-source ledger in non-strict mode.

## Reproducible local checks

| Check | Result | Scope / limitation |
|---|---:|---|
| Python compileall | PASS | Candidate files only |
| Python backend suites | 170 passed, 1 skipped | Local runtime has no `redis` package; auth-refresh integration skipped. CI installs the API dependency set and must execute this test. |
| Frontend Node contract suite | 27 passed, 0 failed | Node 22.16.0; these are source contracts, not browser E2E or Node 24 build proof. |
| Migration recovery manifest | PASS | Internal hash/separation consistency only |
| Migration source reconciliation | PASS in non-strict mode | Six historical SQL sources remain documented gaps; strict exact-source replay remains blocked |
| Node 24 `npm ci`, typecheck, production build | NOT VERIFIED | The local package registry request failed with DNS/network `EAI_AGAIN`; offline cache lacks at least one locked package. Do not infer success from the existing deployed baseline build. |
| Authenticated browser E2E | NOT RUN | No sanitized isolated staging environment was available; test writes were not sent to production. |

## Live infrastructure evidence (baseline only)

The latest observed Render live deployment and latest Vercel production deployment both reference commit `a6acc0eb53660ea938a314640bf28283ae2a98a8`. Vercel alias `lexa-green.vercel.app` and the latest deployment URL both returned HTTP 200 from `/api/lexa/ready`, reporting database and cache healthy. This resolves same-revision parity for the *current baseline*; this hardening candidate is not included in that deployed revision yet.

## Release gates still open

1. Upload this ZIP through the established GitHub ZIP extractor. Confirm the resulting Git SHA and inspect its CI run.
2. Require CI to complete backend tests with `redis` installed and Node 24 clean install, typecheck, frontend contracts and production build on that exact SHA.
3. Confirm Render's live deploy and Vercel production deploy resolve to that same resulting SHA; re-probe readiness on both providers.
4. Review and apply migrations 033–035 to production only under the authorized release/rollback procedure. They have not been applied to production by this work.
5. Run authenticated Playwright sales/return/refund/accounting/fiscal-trail acceptance against a sanitized, isolated staging deployment with explicit staging credentials and fixtures. Do not aim write-enabled tests at production.
6. Resolve or formally supersede the six missing historical SQL byte sources and the migration-032 provenance gap. Reconstructed substitutes remain clearly identified as substitutes, not claimed as original source bytes.

## Root-cause decision for Phase 6

Do not let unavailable historical bytes silently become a permanent blocker to **non-destructive Phase 6 development**. Keep two separate gates:

- **Historical provenance gate:** blocks claims of exact historical-source parity or a strict byte-for-byte replay until original bytes are recovered or an explicit audited substitute decision is recorded.
- **Forward schema/feature gate:** can pass with reviewed, versioned replacement migrations only after a clean-database semantic replay, schema/permission/RLS assertions, tests, rollback plan, and evidence of migration-ledger parity. Never edit old migration history to make the ledger appear green.

Phase 6 design and non-destructive implementation can proceed against the documented contract. Phase 5 production release acceptance remains blocked until the release gates above are proven.
