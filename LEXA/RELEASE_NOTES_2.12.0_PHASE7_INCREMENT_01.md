# Release notes — LEXA 2.12.0 Phase 7 Increment 01

## Added

- Full supplier register, supplier terms, contacts/tax identifiers, receiving preferences and guarded lifecycle changes.
- Effective-dated supplier price tiers and lead-time references by product variant and minimum buying quantity.
- Purchase order submission, approval, cancellation/closure, partial receiving and status history.
- Receipt-level freight/other landed-cost recording and deterministic allocation into inventory cost.
- Supplier returns with request/approve/post stages, inventory reversal at landed cost and supplier credit at base goods cost.
- Supplier invoice receipt matching, `WAITING_RECEIPT` guard, variance/pre-receipt exception review, posted payables and per-bill payment allocation.
- Supplier ledger, payable/credit split and balances by currency.
- Migration 039 with forced tenant RLS, new purchasing finance tables, permissions and append-only runtime grants on ledger/allocation tables.
- Optional manually triggered Phase 7 staging acceptance workflow with production-host deny-list, disposable tenant/reset fixture and temporary QA browser state.

## Fixed / strengthened

- Removed duplicate `bill_id` column in migration 039 and added regression coverage.
- Removed duplicate supplier-payments route registration.
- Validate duplicate bill allocations and total allocation limits before database writes.
- Supplier currency cannot change after supplier-specific price history or purchasing activity exists.
- Landed-cost/allocation/ledger table mutation privileges are reduced at the database boundary.

## Validation state

Local backend suite: 206 passed, 1 skipped due to missing local Redis Python dependency. Frontend contract suite: 36 passed. Static TS/TSX parse, action audit, Python compile, migration-disposition/strict-source checks and 43-input replay plan pass. Full Node 24 build, real clean replay, authenticated staging E2E and candidate deployment are pending. This release note does not certify production acceptance.


## Strategy coverage

See [`docs/PHASE7_STRATEGY_COVERAGE_2026-10-21.md`](docs/PHASE7_STRATEGY_COVERAGE_2026-10-21.md) for the source-grounded feature map and remaining release evidence.
