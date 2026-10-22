# LEXA Phase 4–6 Completeness Acceptance Matrix

**Candidate:** `2.11.0+phase4-6.completeness.increment03`  
**Scope:** source implementation for the product-strategy commitments in Phases 4–6. This is not a production release certificate.

| Strategy requirement | Source implementation / evidence | Candidate status |
|---|---|---|
| Reports apply a validated business period | Reports Apply Period action, reversed-range validation, profile currency, explicit unavailable/no-records states | Local frontend contract PASS; Node 24 typecheck/build pending |
| Avoid conflating current snapshots with historical periods | Reports label all-time customer history and current inventory snapshot separately | Local contract PASS |
| Currency-aware stock/price presentation | Inventory and product stock-cost values use verified business-profile currency; no silent UGX fallback for those values | Source implemented; frontend contracts pass; browser check pending |
| Avoid dead controls and missing destinations | AST action audit in CI; explicit form submit buttons, event handlers and destinations | PASS static: 117 button-like controls, 27 forms, 33 links across 29 TS/TSX files; semantic browser acceptance pending |
| Multi-line sale returns | Return form collects multiple sale lines; backend enforces previous return quantities | Local frontend/backend contract tests pass; authenticated browser E2E pending |
| Prevent refund/receivable over-return accounting defects | Candidate Phase 5 backend logic and migrations 033–035 | Unit/contract tests pass; SQL replay and production rollout pending |
| Trace return accounting/COGS/fiscal status | Candidate journal/COGS/fiscal-document wiring | Source present; full DB replay and provider-specific acceptance pending |
| Location-level on-hand, reserved, available and inbound | Existing inventory ledger/balance projections and inventory workflows | Source exists; full module E2E pending |
| Controlled stock adjustment and stocktake | Adjustment/count draft, approval, posting and variance UI/API | Source exists; full module E2E pending |
| Location-to-location transfers | Transfer state flow including dispatch and receipt | Source exists; full module E2E pending |
| Transparent replenishment suggestion | Policy per tenant/location/variant; Decimal math; demand, lead time, safety stock, reserved and inbound explanations | Source implemented; migration 036 and authenticated E2E pending |
| Low-stock/out-of-stock and no-sale exceptions | New Stock Health endpoint and UI; gross sales and returned units separate; completed-sale recency | Source implemented; migration 038/index replay and authenticated E2E pending |
| Aged stock without fabricating historical layers | 30/60/90-day age bands, unknown provenance, oldest traceable layer and reconciliation gap | Source implemented; migration 037 replay and accounting interpretation review pending |
| Historical migration recovery does not recur | Six permanent dispositions and strict checker | PASS — recovery task closed; historical byte parity not claimed |
| Full migration replacement correctness | 42-input guarded clean replay and exact-SHA evidence verifier | Plan-only PASS; actual disposable DB execution pending CI |
| Complete integration testing | CI provisions Redis, PostgreSQL/pgvector, Node 24 and Playwright tooling | Workflow implemented; candidate CI not yet observed |
| Candidate deployed consistently | Exact-SHA verification and readiness requirements documented | NOT RUN; candidate not committed/deployed here |

## Local check results

- Backend: **188 passed, 1 skipped, 0 failed**. The only skip is a local environment limitation: the Redis Python package is absent in this offline runner. CI provisions Redis and must execute the integration test.
- Frontend contract suite: **33 passed, 0 failed** using Node 22.16.0.
- AST UI action audit: **PASS** across 29 TS/TSX files; 117 button-like controls, 27 forms, 33 links.
- Python compile check: **PASS**.
- Permanent-disposition manifest: **PASS**.
- Strict source reconciliation: **PASS**.
- Clean replay plan: **PASS**, 42 SQL input paths and hashes. Actual SQL was not executed locally.

## Explicitly not accepted

Production migration status, Node 24 build, actual replay semantics, runtime-role database tests, authenticated browser E2E, deployed candidate SHA parity, and production rollout remain unverified. The six historical recovery items are *not* part of these open gates: their recovery was permanently closed by Phase 3 approval.
