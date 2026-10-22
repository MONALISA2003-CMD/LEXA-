# LEXA Phase 7 Acceptance Matrix

**Candidate:** `2.12.0+phase7.increment01`  
**Scope:** supplier management and purchasing lifecycle per `FRESH_NEW_PRODUCT_STRATEGY.md`, Phase 7.  
**Status:** Source candidate; not production-accepted.

| Strategy requirement | Implementation | Local evidence | Remaining release evidence |
|---|---|---|---|
| Supplier terms and master data | Tenant-scoped supplier identity, terms, currency, payment/delivery preferences, status/archive controls, effective supplier price tiers | Backend tests, API/UI contracts and static action audit pass | Node 24 build and authenticated browser workflow |
| Purchase orders | Draft, submit, approve, cancel/close and audit/status history; idempotency keys on retriable actions | Route contracts and backend suite pass | Real integration replay and role tests in CI/staging |
| Partial receiving | Receipt draft, quantity ceiling checks, cost variance reason, concurrency protection; stock changes only on posting | Backend rules/contracts pass | Actual PostgreSQL replay and full browser stock reconciliation |
| Landed/other supported costs | Receipt records plus deterministic allocation by value, quantity or equal share; allocated costs included in inventory valuation | Pure allocation tests and source contracts pass | Database replay and posted receipt reconciliation in staging |
| Supplier returns | Posted-receipt origin, outstanding quantity reservation, separate approval/posting; stock reversal at landed cost, supplier credit at base goods cost | Backend rules/contracts pass | End-to-end return balances and inventory ledger test |
| Supplier invoice matching | Supplier/PO/receipt/currency validation; `WAITING_RECEIPT`, `MATCHED`, `VARIANCE`, `OVERRIDDEN`; explicit reviewed reason required for exceptions | Backend contracts pass | Actual database and browser E2E |
| Supplier bills / payables | Bill remains draft until post; immutable supplier ledger debit on post; cannot post unresolved match | Backend tests and contract checks pass | Real ledger reconciliation in disposable PostgreSQL/staging |
| Supplier payments | Draft/post/void lifecycle; per-bill allocations; duplicate allocation and over-allocation rules; currency and supplier validation | Shared-rule tests and backend suite pass | Real concurrent payment/allocation integration tests in CI/staging |
| Supplier balances | Append-only supplier ledger, payable vs supplier credit, per-currency aggregation and supplier ledger trail | Rule tests and route/UI contracts pass | Reconciliation of seeded bills/payments/returns against database queries |
| Tenant isolation | Migration 039 applies forced RLS to six new tables and tenant policies; role permissions added | Source/migration assertions pass | Actual clean replay and runtime-role cross-tenant deny tests |
| Data and action traceability | Audits/events on supplier/PO/receipt/return/bill/payment transitions; no posted financial document deletion | API contracts and action audit pass | Authenticated acceptance report |
| Mobile usability | Tabbed workflow workspace, visible statuses, per-action busy/error/success behavior and responsive form layout | TSX parser and static control audit pass | Phone/desktop browser acceptance |
| Safe automated acceptance | Manual GitHub workflow requires HTTPS host allow-list, known production-host deny-list, disposable tenant/reset fixture and QA auth state | Static E2E safety contract passes | Configure secrets and run the optional workflow against isolated staging |
| Six permanently replaced historical sources | Recovery gate closed by approved disposition; current replacements remain explicitly non-original equivalents | Strict source reconciliation passes | Semantic replacement replay runs in CI; byte recovery is not reopened |

## Local verification results

- Backend tests: **206 passed, 1 skipped, 0 failed** (local Redis Python package missing causes one auth-refresh integration skip; CI provisions Redis).
- Frontend contracts: **36 passed, 0 failed** under Node 22.16.0.
- TypeScript/TSX parser: 38 source files, no parse diagnostics; this is not a full typecheck.
- Static action audit: PASS on 29 TS/TSX files, 153 button-like controls, 35 forms and 33 links.
- Python compilation, strict source reconciliation and migration disposition checks: PASS.
- Clean replay bundle: 43 paths/hashes pass plan-only mode; SQL was not executed locally.

## Hard stop gates before production

`Node 24 install/typecheck/build`, actual clean PostgreSQL replay with schema/RLS/least-privilege assertions, authenticated disposable-staging E2E, same-candidate-SHA Render/Vercel verification, and explicit approval of the production migration/rollback plan are still required. Migration 039 was not applied to production.


## Strategy coverage

See [`docs/PHASE7_STRATEGY_COVERAGE_2026-10-21.md`](docs/PHASE7_STRATEGY_COVERAGE_2026-10-21.md) for the source-grounded feature map and remaining release evidence.
