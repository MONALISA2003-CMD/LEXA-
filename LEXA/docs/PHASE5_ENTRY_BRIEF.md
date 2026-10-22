# LEXA Phase 5 entry brief — Sales Cockpit and POS Excellence

**Entry disposition:** Phase 5 planning and isolated feature development are unblocked. Do not promote the Phase 4 candidate to production until its source reconciliation, Node 24 build, and authenticated preview gates pass.

## Goal

Make selling faster and give owners a dependable, explorable view of sales performance. Phase 5 must extend the shared business model and dashboard introduced by Phase 4 rather than replace it with a disconnected analytics surface.

## Workstreams

1. **Checkout reliability and speed:** product/SKU/barcode search, cart editing, customer association, authorized discounts, payment recording, receipts, held sales, return/refund paths, and clear recovery when a request fails.
2. **Sales cockpit:** date and branch filters; daily/weekly trend; sales transactions/orders; average sale value; product ranking by units, revenue and gross profit; payment mix; discount/return summaries; and drill-down into source transactions.
3. **Financial definitions:** keep completed net sales, cash/payment collections, customer receivables, expenses and gross profit separate. Document treatment for tax, discounts, returns, cost of goods sold, and partial payments before implementing new KPIs.
4. **Permissions/audit:** test cashier versus manager permissions for price changes, discounts, refunds, voids and end-of-shift actions. Keep auditable actor/time/reason fields.
5. **Accessible UX:** mobile-first till actions, keyboard operation, visible focus, touch-friendly controls, helpful empty/error/loading states, and readable table equivalents for charts.

## Required acceptance evidence

- Totals reconcile against underlying completed transactions and recorded payment ledger rows for the same workspace, business date, currency and selected branch scope.
- Gross profit is not labelled net profit; payment collections are not labelled sales revenue.
- Refunds/returns, voids, discounts, partial payments and retries are tested, including idempotency and failure recovery where supported.
- Authenticated end-to-end tests cover role restrictions and read-after-write verification on non-production data.
- Desktop and 390px mobile review; keyboard/focus and chart-table alternative check.
- Full Node 24 `npm ci`, typecheck, tests and production build; backend tests; preview deployment from one identified source SHA; API/browser smoke checks.

## Explicit non-goals

- No production data writes for acceptance tests.
- No silent rewrite of historic migration identities, and no migration is added merely for dashboard presentation.
- No automated discount/refund or cash movement without existing permissions and audit controls.
- No assertion that Phase 4 is release-accepted while the documented source/build/browser gates remain pending.

## Implementation order

1. Close the Phase 4 source rebase and preview-validation blockers.
2. Map existing POS/cart/payment/receipt/return routes and tests before changing them.
3. Add missing end-to-end cases before extending each flow.
4. Implement one checkout slice at a time, then dashboard drill-down and comparison filters.
5. Reconcile chart totals and acceptance results before calling the slice complete.
