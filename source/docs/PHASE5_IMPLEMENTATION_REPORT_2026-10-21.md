# LEXA Phase 5 — Increment 01 implementation report

**Date:** 21 October 2026 (Africa/Kampala)  
**Disposition:** Source-level increment prepared; not deployed.  
**Scope:** Sales/POS first slice: multi-line cart, product/SKU search, checkout retry safety, price/discount authorization, scoped sales history, sale detail/print view.

## Implemented

### Checkout and cart

- Replace the single-item checkout path with a multi-line cart. Cashiers can search local product/variant/SKU data, add items, change line quantity/price, remove lines and see a subtotal preview.
- Send cart lines as one sale request so the backend continues to own tax, totals, stock decrements, payment allocations, receivables and accounting postings.
- Validate location/cart presence, non-negative price, positive quantity through input controls, payment totals, payment channel selection, and the need for a customer when the sale would create an outstanding balance.
- Disable repeated submit while a request is pending.
- Reuse the same idempotency key when the exact same checkout payload is retried after a possible lost response; a changed payload gets a different key. This leverages the existing backend idempotency contract.
- Respect configured workspace currency for checkout payment channels and amounts.

### Server-side price and discount controls

- The sale API independently verifies product catalogue price. A cashier without `catalog.pricing.manage` or `catalog.manage` cannot submit a different unit price.
- A non-manager cannot complete checkout with an item that has no catalogue price configured.
- Line discounts require `sales.manage`; the browser is not treated as an authorization boundary.
- These guards use existing permission codes; no schema migration was added.

### Sales history and receipt view

- Add bound server-side filters for customer/sale reference, status, business-date range, branch and pagination.
- Scope the listing to branches assigned to the authenticated member; validate the requested branch filter and protect sale-detail reads with the same branch guard.
- Add a read-after-load sale detail view with line values, discounts, tax, total, amount collected and outstanding balance, plus a print-friendly view.
- Keep gross profit distinct from sales total and avoid presenting a receipt as a net-profit report.

### Small reliability correction

- Removed a duplicate `setReconciliationActual` call that could submit the same actual amount twice when a user saved a reconciliation line.

## Validation evidence

- Frontend Node test suite: **25 passed, 0 failed**.
- Backend pytest suite: **31 passed, 1 skipped**. The auth-refresh test skip is caused by its optional API test dependencies not being installed in this local environment.
- Python `compileall`: pass.
- TypeScript/TSX syntax transpile: **33 files, 0 syntax diagnostics**. This is not a full typecheck.
- ZIP integrity/source-overlay composition checks are recorded alongside the packaged artifact.

## Not yet verified

- `npm ci` did not finish in this execution environment; the command stalled and was stopped. The available runtime is Node 22.16, while the project release gate calls for Node 24.
- Full `tsc --noEmit`, Next.js production build, authenticated browser acceptance, and a preview deployment were not completed.
- Live role-based checkout tests using cashier/manager accounts remain pending. Source-level authorization contracts pass, but they do not replace DB/API integration tests.
- No GitHub commit, preview deployment, production SQL write, or live business transaction was made.

## Release decision

**Phase 5 Increment 01: source candidate prepared.**  
**Phase 5 overall: in progress, not complete.**  
**Production/release gate: blocked on full Node 24 validation, authenticated role-based browser/API acceptance, and preview verification on one identified source revision.**
