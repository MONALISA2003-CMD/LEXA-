# LEXA Phase 8 — Finance implementation candidate

**Status: implemented in source candidate with targeted local acceptance. Not production-approved, not deployed.**

Start here:

1. `LEXA_PHASE8_IMPLEMENTATION_REPORT_2026-10-22.md` — what changed, test evidence and open acceptance checks.
2. `LEXA_PHASE8_REVISED_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_2026-10-22.md` — agreed architecture, phase responsibilities and no-repeated-production-gate approach.
3. `source/PHASE8_IMPLEMENTATION_REPORT_2026-10-22.md` — copy of the report included alongside the source.
4. `source/README.md` — current source-candidate overview; older Phase 7 reports are retained as historical evidence.

## Payment boundary

LEXA records the payment method and amount a business enters. It does not initiate transfers, settle money, or automatically verify transactions with a wallet or bank. Business owners can configure labels such as Cash, MTN Line 1, Airtel Line 1, Stanbic or Centenary Bank. LEXA should not ask for or store mobile-money PINs, OTPs, bank passwords, API keys, provider tokens, account sign-in details or payment-provider secrets. No payment gateway integration was added.

## What was changed for Phase 8

- Finance workspace uses everyday business wording for balances, expenses, payment methods, end-of-day checks and reports.
- Customer collections reuse sales, receivables and payment allocations.
- Supplier payables reuse the Phase 7 supplier ledger; no parallel payable ledger is added.
- Expenses have draft, official-record, cancellation and traceable correction/history workflows.
- Payment methods can be deactivated while their historical transactions remain available.
- Manual end-of-day comparison separates recorded receipts from amounts entered from actual counts/statements.
- Reports separate sales, recorded receipts, expenses, expense corrections and product-cost margin.
- Migration `040_phase8_finance_workflows.sql` adds the required reversal and reporting support.

## Verified on the included source candidate

- Full repository Python tests: **233 passed**, one third-party deprecation warning.
- Frontend contract tests: **50 passed**, zero failed.
- Python compile and TypeScript/JSX syntax transpilation: passed.

The full Node 24 dependency install/typecheck/production build and actual PostgreSQL replay of migration 040 remain open because this environment has Node 22 and cannot reach the package registry or a local PostgreSQL service. No production database was changed, no deployment was performed, and no paid resource was provisioned. The consolidated hosted production/recovery/billing/launch gate stays in Phase 12.
