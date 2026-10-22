# LEXA Phase 8 — Finance implementation report

**Date:** 22 October 2026  
**Candidate:** Phase 7 source extended with Phase 8 finance workflows  
**Status:** `IMPLEMENTED — SOURCE CANDIDATE / TARGETED LOCAL ACCEPTANCE`  
**Production status:** Unchanged; not deployed or production-approved

## Purpose

Complete the Phase 8 finance workflows on top of the current LEXA source candidate. The frontend uses everyday business language and avoids exposing implementation terms to shop owners and staff. Changes reuse existing commerce, payment-channel, customer-credit, accounting and supplier-ledger records wherever possible.

## Key product decision: payments are recorded, not processed

LEXA is not a payment gateway or money-transfer service. A business owner configures labels such as **Cash**, **MTN Line 1**, **Airtel Line 1**, **Stanbic** or **Centenary Bank**. Staff record amounts and optional ordinary transaction references against a sale or expense. LEXA does not initiate transfers, settle money, connect to wallets/banks to verify a transaction, or request/store payment PINs, OTPs, passwords, API keys, tokens, provider login details or webhook secrets.

Payment channel records and historical transactions are retained. Deactivating a method only stops its use for new entries; historical channel totals remain available for reconciliation. Manual end-of-day checks compare recorded receipts with amounts staff enter from cash counts or their own statements. These results are not described as bank- or provider-verified.

EFRIS remains a separate compliance boundary for a later phase. No payment gateway was added.

## Implemented workflows

### Finance workspace

- Plain-language Finance tabs for **Summary**, **Expenses**, **Customer balances**, **End-of-day check**, **Payment methods** and **Financial reports**.
- Summary displays recorded sales/collections, customer balances, supplier bills/payables and recorded expenses without presenting unavailable data as a fabricated zero.
- The finance page links users to the underlying transactions and relevant operational pages.

### Customer balances and collections

- Reuses the existing sales, receivables, payment, customer-credit and allocation model.
- Supports recording later customer payments using named payment methods and an optional ordinary reference.
- Keeps the remaining balance visible and applies existing server-side validation against the remaining amount.

### Supplier payables

- Reuses the Phase 7 supplier bills, supplier payments, allocations and supplier ledger.
- No duplicate supplier-balance ledger was introduced.
- Supplier balances are shown through the existing reporting/API contract.

### Expenses

- Expense entry includes the business date, receipt/reference, description, category, payment method, amount before tax and tax where applicable.
- New expenses start as drafts. A user reviews the record and explicitly adds it to official accounting records.
- A draft can be cancelled without treating it as a recorded expense.
- A posted expense is corrected through a traceable accounting reversal with a required reason; the original record remains visible.
- Expense history shows the saved draft, posting, cancellation or correction, timestamp, actor where available and correction reason.
- Expense actions are tenant-scoped, permission-checked, audited, and use stable idempotency keys so a retry after an uncertain response does not intentionally create a second action.
- References are checked for explicit credential terms. UI guidance tells users not to enter bank/account credentials or verification codes.

### Payment method management

- Supports owner-configured names, categories, optional institution/provider labels and currency.
- Adds a tenant-scoped deactivate action that preserves prior payments.
- Reconciliation creation includes inactive payment methods when they have recorded receipts/refunds on the chosen date, so historic totals are not silently omitted.
- Existing multi-method sale recording and payment allocations are retained.

### Manual end-of-day check

- Shows expected recorded receipts per method, manually entered actual receipts, differences and review notes.
- Staff can acknowledge/review a difference with an explanatory note before finishing a check.
- Actual values, review and close operations are idempotent and audited where implemented.
- Historical actual amounts and notes remain attached to the reconciliation.
- The UI explicitly explains that actual amounts come from the business's own count/statements and that LEXA does not connect to or verify wallets/bank accounts.

### Finance reports and definitions

- Separates sales from receipts recorded, customer credit, expenses, expense corrections and product-cost margin.
- Distinguishes product-cost margin from net profit; operating expenses are not hidden inside product margin.
- Keeps the reporting currency and selected date range in view.
- Separates an accounting correction from a physical return of cash. A corrected expense does not automatically count as money received. The recorded-money-movement calculation retains the original recorded outflow date for posted/corrected expenses, while expense totals and correction amounts are shown separately.
- Source changes add the expense-correction measure to the daily business reporting projection.

## Architecture and data ownership

```text
Identity + workspace + branch permissions
                   |
     Sales / returns / customer credit
                   |
       Payments + payment allocations
                   |
      Recorded receipts by named method
                   |
     Manual end-of-day comparisons
                   |
       Finance summaries and reports

Purchase bills + supplier payments ---> Existing supplier ledger

Expense draft ---> Review/post ---> Accounting journal
                         |
                   Traceable correction

All flows use tenant-scoped existing records and permissions.
```

Source-of-truth rules:

- Customer balances derive from existing receivables, valid allocations, customer credits and return/adjustment behavior; no new customer ledger was added.
- Supplier balances come from Phase 7 supplier bills, payments, allocations and supplier ledger; no second payable ledger was created.
- Payment methods classify a human-recorded receipt; they do not represent a connection to a financial provider.
- Inventory cost and sale/return records remain the source for product cost and margin.
- Financial write actions retain permission checks, audit/event records and targeted idempotency behavior where changed.
- Tenant and branch rules continue to be enforced server-side and through existing database protections.

## Main source changes

- `apps/api/app/routes/commerce.py` — safe payment-channel deactivation, reconciliation coverage for historic inactive methods and idempotent manual actual/review/close operations.
- `apps/api/app/commerce_rules.py` — shared safety checks for ordinary references and friendly payment-method labels; not a provider integration.
- `apps/api/app/routes/finance.py` — validated expense creation, draft/post/cancel/correct lifecycle, tenant-scoped expense history, idempotent/audited writes and source-date handling.
- `apps/api/app/routes/analytics.py` — carries the expense-correction reporting measure through the API response.
- `apps/web/app/accounting/page.tsx` — plain-language finance workspace, expense and correction history, manual receipt comparison and defined report wording.
- `apps/web/app/commerce/page.tsx` — plain-language payment method, split-payment and customer-payment flows, with explicit no-provider-verification messaging.
- `apps/web/lib/api.ts` — typed APIs and retry-safe idempotency key reuse for affected writes.
- `migrations/040_phase8_finance_workflows.sql` — additive Phase 8 schema/function/report updates; not applied to production.
- `apps/api/tests/test_phase8_finance_workflows_contract.py`
- `apps/api/tests/test_phase8_payment_reference_safety.py`
- `apps/web/tests/phase8-finance-workflows.test.mjs`
- `tests/unit/test_phase4a_frontend_contract.py` — updates the old navigation contract to the user-facing plain-language labels.

## Verification actually performed

- Backend: `python -m compileall -q apps/api/app` — passed.
- Backend tests: `PYTHONPATH=apps/api python -m pytest -q` from the repository source root — **233 passed**, one third-party deprecation warning (includes `tests/` and `apps/api/tests/`).
- Frontend contract tests: `node --test tests/*.test.mjs` from `apps/web` — **50 passed, 0 failed**.
- TypeScript/JSX syntax transpilation for `apps/web/app/accounting/page.tsx`, `apps/web/app/commerce/page.tsx` and `apps/web/lib/api.ts` using the globally available TypeScript compiler — passed. This is a syntax check, not a full typecheck or production build.

## Checks still open

These are known validation limits, not claims of completed acceptance:

- The full Next.js build and complete typecheck were **not** run successfully. The project requires Node 24.x, while the local runtime has Node 22.16.0; downloading dependencies also failed because the package registry was unreachable.
- Migration `040_phase8_finance_workflows.sql` has not been replayed against a disposable PostgreSQL database in this environment. Its syntax/behavior therefore remains unverified by a real PostgreSQL run.
- No authenticated browser E2E or visual/mobile-device session was run.
- This is not exact-SHA hosted CI evidence. No source commit or GitHub publication is claimed.

The next local-acceptance steps are to run the migration on a disposable database, run a clean Node 24 dependency install/typecheck/production build, and walk the finance screens on a phone-sized browser. These should remain targeted Phase 8 acceptance tasks. The shared hosted production, recovery, rollout and billing gates remain consolidated in Phase 12.

## Safety and release statement

- No live money movement or payment-provider connection was introduced.
- No payment-provider credentials are needed or requested.
- No production database migration was applied.
- No application was deployed.
- No paid resource was provisioned.
- Production status remains **unchanged and not accepted**.
