# LEXA Phase 5 — Increment 02 implementation report

**Date:** 21 October 2026 (Africa/Kampala)  
**Scope:** Checkout acceptance hardening: partial payment reconciliation, idempotent retries, stock read-after-write, cumulative refund safeguards, and auditable sale detail.  
**Disposition:** Candidate implemented and source-tested. Staging E2E, full Node 24 validation, and preview deployment remain outstanding. This is not a release approval.

## Implemented

1. **Cumulative refund safety.** Added a pure amount-rule helper and changed `POST /commerce/sales/{sale_id}/returns` to lock the source sale, sum all recorded refunds on that sale, and enforce the refund amount against the remaining amount collected. A later refund can no longer reuse the original full `amount_paid` ceiling after an earlier refund has consumed part of it. The existing sale-row lock serializes concurrent return attempts for the same sale.
2. **Branch-scoped returns list.** `GET /commerce/returns` filters return records to the member's active membership and active branch assignments; it no longer lists every branch's return records to any member holding the permission.
3. **Sale audit detail.** `GET /commerce/sales/{sale_id}` now includes payment allocations, returns, customer-credit balance summaries, and refund records alongside sale lines. The existing sale branch-access check still precedes the response.
4. **Frontend audit presentation.** The sale detail panel can display the payment ledger and return/refund history. The fields are optional in the frontend contract so a staged rolling deployment against an older API response will not fail rendering.
5. **Staging-only acceptance test.** Added an opt-in Playwright spec covering a three-line sale, split tender and partial payment, same-key idempotent retry, sale/payment/stock read-after-write, a cumulative refund rejection, and cashier price/discount denial. It requires an explicit staging hostname allow-list, non-production storage state, fixture data, and `LEXA_PHASE5_ALLOW_STAGING_WRITES=1` before its writes are enabled.

## Local validation completed

| Check | Result | Limits |
|---|---|---|
| Backend tests (overlay subset) | 19 passed | Local Python suite; not a real database transaction test |
| Backend tests (reconstructed full-source candidate) | 41 passed, 1 skipped | Broader suite; skip is auth-refresh test because Redis is unavailable |
| Backend compilation | Passed | Syntax/bytecode compilation only |
| Frontend source-contract tests (overlay subset) | 3 test files passed | Tests inspect source contracts; not a browser run |
| Frontend source-contract tests (reconstructed full-source candidate) | 25 passed | `node --test tests/*.test.mjs`; not a browser run |
| TypeScript transpile syntax scan | Passed — 34 implementation/config files; zero syntax diagnostics | Syntax-only scan is not a full typecheck |
| Node 24 clean install, typecheck, production build | Blocked | Runner uses Node 22.16 and required package is missing from offline npm cache |
| Authenticated staging Playwright acceptance | Not run | Requires a disposable staging deployment, seeded fixture, and QA storage-state file |
| Preview deployment | Not run | No deployment performed for this increment |
| Production database or service changes | None | No production sales, payments, returns, or stock changes were created |

## Acceptance scenario encoded for staging

The example fixture is deliberately explicit:

- Three configured inventory-tracked variants priced at 8,000, 3,000, and 4,000 in one currency; one unit each.
- Sale total 15,000, with two payment allocations totalling 10,000 and outstanding balance 5,000.
- Retry the identical checkout with the same idempotency key; the server must return the original sale identifier.
- Verify recorded payment allocations and per-variant stock decrement with matching sale ledger references.
- Refund the 8,000 line once; then attempt a separate 3,000 refund. Because only 2,000 of the original 10,000 collections remain refundable, the second refund must be rejected with HTTP 422.
- Attempt a catalogue-price override and discount as a cashier; each must be rejected with HTTP 403. A manager-positive override/discount sale is also encoded behind a separate manager storage-state. An optional manager cross-branch test asserts the specific branch-assignment denial for sale detail and return creation, and checks that the returns list does not leak a seeded cross-branch return.

The test needs a staging schema containing the current source's required migration set and active test data, including `sales`, `payment_allocations`, `inventory_balances`, and the stock ledger. Do not repurpose a production workspace or credentials. The full backend suite was run in the preserved source candidate after this increment was overlaid: 41 passed and 1 skipped (Redis-dependent auth-refresh test). The full frontend source-contract suite also passed all 25 tests. These results are from a reconstructed candidate source tree, not proof of byte-for-byte parity with the accepted Phase 3 handoff.

## Remaining release gates

- Run full Node 24 `npm ci`, `npm run typecheck`, `npm test`, and `npm run build` on the exact proposed source tree.
- Run the Playwright suite against a fresh, disposable staging workspace; verify cashier denial, manager positive authorization, cross-branch denial, payment reconciliation, stock ledger balance, and cleanup/archive policy for created test records.
- Execute the new positive manager price/discount test and cross-branch sale-detail/returns denial test; they are authored but not run in this environment.
- Inspect the PostgreSQL transaction contract for the cumulative refund path under concurrent requests, including the idempotency table's uniqueness handling and stock-return ledger behavior.
- Review migration/source provenance and rebase these source changes onto the exact accepted Phase 3 handoff before deployment.
- Deploy frontend/API from one identified source SHA to preview, run smoke checks, and document a rollback target.

## Explicitly not done

- No real browser or authenticated E2E execution was completed in this environment.
- No new migration was added.
- No commit was pushed to GitHub, no production service was redeployed, and no live database was modified.
- The staging suite is a prepared test, not a claim that its scenarios have passed against a live backend.
