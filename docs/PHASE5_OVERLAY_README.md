# LEXA combined Phase 4 + Phase 5 Increment 01 overlay

This archive contains repo-relative overlay files; it is **not a full-project replacement ZIP**. It bundles the latest Phase 4 closeout overlay files together with Phase 5 sales/POS changes, with the Phase 5 version winning on paths that overlap.

## How to apply

1. Start from the latest owner-accepted Phase 3 final-cutover project source.
2. Apply this combined overlay once. If the standalone Phase 4 closeout overlay has already been applied, this will safely update only the paths included in this archive.
3. Run the Node 24 clean install/typecheck/test/build gate plus the backend test suite. Do not copy `.env`/`.env.local`, `.git`, build caches, or dependency directories from any archive.
4. Deploy only to a preview environment and run authenticated cashier/manager role tests, cross-branch denial checks, multi-line checkout/partial payment, idempotent retry, and sale-detail/print verification.

The overlay creates no migration and contains no credentials. It does not deploy itself. The six historic SQL source substitutions from earlier phases remain a separate known provenance issue; this Phase 5 slice does not change their status.

## Included changes

- `apps/api/app/routes/commerce.py`: retains the latest Phase 4 currency/business-date fixes and adds Phase 5 branch-scoped sales filters/detail and server-side price/discount gates.
- `apps/web/app/commerce/page.tsx`: multi-line cart, product search, idempotent retry, history filters/details/print.
- `apps/web/lib/api.ts`: filtered sales query and optional checkout idempotency key, layered over the latest Phase 4 client contracts.
- `apps/web/app/globals.css`: latest Phase 4 styles plus cart, sales filter, detail and print styles.
- The remaining Phase 4 dashboard, inventory-summary, KPI/acceptance changes, plus Phase 5 reports and source-contract tests.
