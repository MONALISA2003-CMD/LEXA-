# LEXA Phase 2 — Cross-module transaction acceptance

## What this patch adds

- `GET /api/v1/commerce/sales/{sale_id}/evidence`, a read-only endpoint that checks `sales.read`, tenant ownership and branch access before returning sanitized audit/outbox lifecycle metadata. It does not return event payloads or idempotency key values.
- A guarded authenticated Playwright journey covering checkout, replay with the same idempotency key, stock quantity and weighted-average cost movement, revenue/tax and COGS journals, partial payment/receivable creation, idempotent receivable settlement, sanitized audit/outbox evidence, and refreshed analytics.
- Backend and Node contract tests for endpoint registration, tenant/branch scope, redaction and staging safety controls.

No database migration is needed: the code uses existing commerce, inventory, journal, audit, outbox, idempotency and analytics tables. This package does not insert fixtures or transactions into production.

## Staging-only enablement

The write-enabled browser scenario is skipped by default. Run it only against a separately provisioned disposable staging tenant with real QA authentication and working database/cache readiness. Set all of the following explicitly:

- `LEXA_BROWSER_BASE_URL`: the staging HTTPS origin only.
- `LEXA_PHASE2_STAGING_HOSTS`: comma-separated exact staging hostnames including that origin's hostname.
- `LEXA_PHASE2_ALLOW_STAGING_WRITES=1`.
- `LEXA_PHASE2_STORAGE_STATE`: path to the dedicated QA Playwright storage-state JSON.
- `LEXA_PHASE2_ACCEPTANCE_FIXTURE_JSON`: JSON containing `environment: "staging"`, `disposable_scope: true`, `reset_strategy: "dispose_test_tenant"`, `actor_role: "owner"` or `"administrator"`, `branch_id`, `location_id`, `customer_party_id`, `variant_id`, `payment_channel_id`, `currency_code`, `business_date`, `unit_price`, `quantity`, `initial_payment`, and `expected_total`.

The fixture must reference a stock-tracked SKU with enough inventory and a positive saved average cost, a valid customer, an active payment channel in the saved business currency, and a branch assignment that grants the tester access to sales, receivables, analytics refresh, inventory and journals. The current receivables list endpoint is branch-assignment scoped, so ensure the QA membership has an active assignment to the fixture's branch. `expected_total` must match the actual effective-dated tax configuration for the one-line sale. The initial payment must be positive and lower than that total.

Global setup validates HTTPS, rejects known production hostnames, checks the explicit hostname allow-list, validates fixture and QA state, and calls `/api/lexa/ready` without following redirects. It refuses to continue unless the API identifies itself as staging/test with database and cache healthy. The scenario does not use `DATABASE_URL` or service credentials in the browser.

The fixture's tenant must be disposable and separately reset after execution. The test deliberately does not delete a tenant or business data automatically. Do not point it at `lexa-green.vercel.app`, `lexa-n10e.onrender.com`, or any production database.

## Validation status

Verified locally for this patch: Python compile of the new route/main and contract test; 2 API static contract tests passed; 5 focused Node checks passed; TypeScript syntax transpilation of the new Playwright spec/config/setup returned zero syntax diagnostics. The whole API suite, Node 24 suite, TypeScript typecheck, frontend production build and authenticated staging journey have **not** been run on this new bundle. Successful ZIP extraction alone is not a CI pass.
