# Phase 7 strategy coverage — Purchasing and Supplier Management

**Strategy source:** `FRESH_NEW_PRODUCT_STRATEGY.md`, version 1.0, 21 October 2026, section 6 “Roadmap and release outcomes”, Phase 7. Supporting source-derived expectations are in sections 2–4 and 7–10.
**Current disposition:** full-source local candidate; not production-accepted.

| Strategy requirement / source-derived expectation | Candidate implementation | Evidence / remaining proof |
|---|---|---|
| Supplier terms and supplier obligations | Supplier register, commercial terms, currency, effective supplier variant costs, lead-time references | API/service tests and UI contracts pass; authenticated role tests remain CI/staging gate |
| Purchase order lifecycle | Draft, submit, approve, cancel/close; status history, audit events, idempotency and tenant/branch/location controls | Backend and contract suites pass; authenticated lifecycle E2E pending |
| Goods receiving | Partial receipts, quantity ceilings, reasoned variance and stock updates only after explicit posting | Rule/contracts pass; disposable PostgreSQL and inventory ledger read-after-write E2E pending |
| Landed/other supported costs | Receipt-scoped landed costs allocated by value, quantity or equal share with deterministic rounding; inventory unit cost includes allocated cost | Pure tests and migration contracts pass; real DB replay and valuation reconciliation pending |
| Supplier returns | Return requests reference posted receipt lines; reservations protect unreturned quantities; approve then post; stock reversal uses landed cost and supplier credit excludes non-supplier-paid landed cost | Backend contracts pass; real transaction/ledger reconciliation E2E pending |
| Supplier invoice/three-way matching | Supplier/PO/receipt/currency match, `WAITING_RECEIPT`, `VARIANCE`, reviewed reason before exceptions, posted payable after match/override | Contract tests pass; real clean replay and authenticated exception journey pending |
| Supplier payments and balances | Per-bill allocation, no duplicate bill allocation, over-allocation and currency checks, posting, draft voiding, append-only supplier ledger, per-currency payable/credit balances | Rule/route tests pass; actual DB concurrency and ledger reconciliation pending |
| Trustworthy operational records and permissions | Tenant RLS, migration-backed finance permissions, least-privilege/append-only grants and event/audit trail | Source/postcondition checks pass; clean PostgreSQL role tests pending CI |
| Mobile-first usable workflow | Tabbed purchasing workspace, visible states and per-action loading/error/success feedback | Static TSX/action checks pass; phone/desktop real-browser acceptance pending |
| Do not auto-create purchases | Reorder recommendations stay advisory; purchase order requires explicit action and approval | Existing Phase 6 contract retained; source contract pass |
| Phase/release gates do not recur | Six original lost sources stay permanently replaced; source reconciliation distinct from semantic replay; CI has Node24, Redis, clean PostgreSQL and guarded optional staging E2E jobs | Strict source check and 43-input plan-only check pass; cloud CI evidence/staging E2E/deploy parity pending |

## Required before declaring Phase 7 release accepted

1. Upload this exact package through the existing GitHub extractor and retain the resulting full commit SHA.
2. Run the exact-commit backend CI with Redis, Node 24 clean install/typecheck/build and actual disposable PostgreSQL replay/postconditions; archive the replay evidence/checksum.
3. Trigger optional Phase 7 E2E only with the HTTPS host allow-list, authenticated storage state and a disposable staging fixture/reset strategy; verify both normal receipt/payment and the reviewed pre-receipt exception path.
4. Confirm the same candidate SHA and readiness on Render and Vercel, with exact commit parity.
5. Obtain migration review and explicit production rollout/rollback approval. Migrations 033–039 are still candidates and were not applied to production here.

**Source provenance note:** the six Phase 3 historical SQL sources remain permanently dispositioned as replacements; this document does not claim original-byte recovery. No production database or deployment was changed by this candidate build.
