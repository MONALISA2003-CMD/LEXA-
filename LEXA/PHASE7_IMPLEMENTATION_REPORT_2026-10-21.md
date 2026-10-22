# LEXA Phase 7 Implementation Report — Increment 01

**Package:** `2.12.0+phase7.increment01`  
**Strategy source:** `FRESH_NEW_PRODUCT_STRATEGY.md` (Phase 7: Purchasing and Supplier Management)  
**Disposition:** Full-source review candidate; not production-accepted.

## Scope implemented

Phase 7 turns supplier commitments into a traceable purchasing workflow using the existing tenant-scoped business transaction and inventory models.

1. **Supplier master and terms:** supplier identity, legal/contact/tax information, payment terms, currency and default receiving location, status changes, guarded archive, supplier cost history and lead times.
2. **Supplier-specific buying prices:** effective-dated price tiers by supplier/variant/currency/minimum quantity; active-tier uniqueness is checked before adding a unique partial index. Currency is locked after supplier price or transaction history so old prices are not silently reinterpreted.
3. **Purchase orders:** draft creation, submission, approval, cancellation and closure; location-to-branch validation, supplier/currency consistency, unique variant lines, status history, audits/events and idempotent retried writes.
4. **Receiving and partial receipts:** draft receipt with received quantities and explicit variance reasons; approved/open orders only; concurrent receipt guards; posting increases inventory through the canonical inventory ledger and only at posting time.
5. **Landed costs:** receipt-specific freight/other landed-cost records allocated by value, quantity or equally. Decimal money math assigns deterministic rounding residuals. Effective inventory unit cost incorporates allocated landed cost. Cost allocation records are append-only at the application database role.
6. **Supplier returns:** requests reference posted receipt lines; requested/approved/posted returns reserve quantities against the same receipt; approval is separated from posting; posting reverses inventory at landed cost while supplier credit uses base goods cost, so costs not owed to the supplier are not credited.
7. **Supplier bills and three-way evidence:** bill links are checked against supplier, PO, receipt and currency. A PO bill without a posted receipt remains `WAITING_RECEIPT`; receipt subtotal mismatches become `VARIANCE`. Posting is blocked until matched or an authorised reviewer writes a justified exception. Pre-receipt exceptions remain explicit and auditable.
8. **Payments and balances:** supplier payment drafts, per-bill allocations, same-supplier/same-currency checks, duplicate allocation validation, allocation ceiling checks, posting and voiding of drafts, append-only ledger entries and payable/credit balances grouped by currency. Advances remain visible; currencies are never combined.
9. **Security and traceability:** migration 039 creates supplier finance/landed-cost structures with forced tenant RLS and tenant policies; permission codes are added for bill/payments management. Runtime table grants are least-privilege: ledger, landed costs and allocation records are read/insert only; bill/payment rows are select/insert/update for lifecycle only.
10. **Release and acceptance controls:** Playwright can discover both Phase 5 and Phase 7 E2E specs. Phase 7 acceptance is a manual workflow-dispatch option guarded by HTTPS base URL, a host allow-list, a known-production-host deny-list, explicit write opt-in, staging fixture requiring a disposable test tenant/reset strategy, and a temporary authenticated browser storage-state secret. Reports are retained without the storage-state file; the storage file is deleted even after failure.

## Local validation

| Check | Result | Qualification |
|---|---|---|
| Python backend + repository tests | **206 passed, 1 skipped, 0 failed** | The skip is the auth-refresh integration test because `redis`' Python client is unavailable in the offline local runner. CI provisions Redis and installs full API dev dependencies. |
| Frontend contract tests | **36 passed, 0 failed** | Ran under Node 22.16.0 locally. |
| TypeScript/TSX parse diagnostics | **38 sources, 0 parse errors** | Syntax-only parser run, not a full TypeScript typecheck. |
| Static frontend action audit | **PASS** | 29 TS/TSX modules; 153 button-like controls, 35 forms and 33 links inspected. |
| Python compileall | **PASS** | `apps/api/app`, `apps/api/tests`, `scripts`. |
| Permanent replacement manifest | **PASS** | The six Phase 3-approved lost historical SQL sources remain permanently replaced; this is not historical byte recovery. |
| Strict source reconciliation | **PASS** | Does not claim original-byte parity for approved equivalents. |
| Clean SQL replay plan | **PASS — 43 paths and hashes** | Plan-only; no SQL execution occurred locally. |
| SQL duplicate-column source scan | **PASS** | The duplicated `bill_id` line found during review was removed; test locks this contract. |
| Node 24 install/typecheck/build | **NOT VERIFIED LOCALLY** | Local environment is offline and has no `apps/web/node_modules`; CI workflow is configured. |
| Actual disposable PostgreSQL replay | **PENDING CI** | The local command was plan-only; clean schema/RLS/role assertions must run on the disposable CI service. |
| Authenticated browser E2E | **NOT RUN** | No disposable, authenticated staging environment supplied. A guarded manual workflow was added. |
| Candidate deployed to Render/Vercel | **NOT DEPLOYED** | Candidate is local source; no claim of deployment parity. |
| Migration 039 applied to production | **NO** | No production SQL changes were made. |

## Important defects found and corrected

- A duplicated `bill_id` column declaration in migration 039 would have made the migration invalid; it is corrected and guarded by a contract test.
- A duplicated supplier-payment GET route decorator was removed.
- Payment allocation validation now rejects the same bill twice before database writes and rejects totals above the payment amount; this also avoids a unique-key violation becoming an opaque server error.
- Runtime database permissions for the supplier ledger, landed-cost allocations and supplier payment allocations were narrowed to append-only behavior. The landed-cost insert is idempotent without requiring an update privilege.
- Supplier base-currency changes now remain blocked once a supplier-specific price tier exists, preventing active price history from being reinterpreted.
- The Phase 7 browser test cannot run against the known LEXA production hostnames and requires a disposable staging tenant that is reset after the run.

## Required next release evidence

1. Push this exact ZIP to GitHub through the existing ZIP extractor.
2. Wait for the exact-SHA GitHub CI jobs to complete: dependency-complete backend tests, Node 24 install/typecheck/contracts/build, real clean PostgreSQL replay and replay evidence validation.
3. Configure the optional `run_phase7_staging_e2e` workflow with `LEXA_PHASE7_STAGING_URL`, `LEXA_PHASE7_STAGING_HOSTS`, `LEXA_PHASE7_ACCEPTANCE_FIXTURE_JSON`, and `LEXA_PHASE7_STORAGE_STATE_B64`. The fixture must declare `environment=staging`, `disposable_scope=true`, and `reset_strategy=dispose_test_tenant` and point to a disposable, isolated tenant. Only then explicitly trigger the staging E2E input.
4. Review actual clean replay and candidate-specific test artifacts, then verify one commit SHA on Render and Vercel, health/readiness and the buyer-to-payable lifecycle.
5. Approve production rollout and a rollback plan before applying migrations 033–039. Do not treat this ZIP, a passing local suite or baseline health as production acceptance.

## Phase 7 release conclusion

The Phase 7 source implementation and local contract checks are complete for this increment. The release remains a **review candidate** until cloud build, real clean replay, authenticated disposable-staging E2E, deployment SHA parity and the approved database rollout are evidenced. The six lost historical SQL sources are not release blockers; their permanent disposition remains closed.


## Strategy coverage

See [`docs/PHASE7_STRATEGY_COVERAGE_2026-10-21.md`](docs/PHASE7_STRATEGY_COVERAGE_2026-10-21.md) for the source-grounded feature map and remaining release evidence.
