# LEXA Phase 4A End-to-End Release 2.2.0

## Scope

This release completes the Phase 4A commerce application layer on the canonical LEXA Neon PostgreSQL project and adds the remaining customer-credit allocation/reversal safeguards plus the mobile sidebar layering fix.

## Included

- FastAPI commerce routes for customers, payment channels, products, sales, receivables, receivable payments, returns, refunds, customer credits and reconciliation.
- Next.js commerce workspace with connected API contracts and customer-credit allocation UI.
- Neon PostgreSQL migrations 015 through 019.
- Deterministic financial calculations and reconciliation.
- Idempotency on critical financial mutations.
- Payment immutability and reversal safeguards.
- Receivable refresh from recorded payments and customer-credit allocations.
- Customer-credit over-allocation protection and reversal handling.
- Sale-return inventory restoration using original-sale ledger cost basis.
- Mobile sidebar layering fix using a transparent bounded brand asset.

## Canonical Neon

Project: `wispy-mud-75323042`  
Branch: `lexa-live` (`br-soft-star-b1dj2m2w`)  
Database: `neondb`

## Verification

- `python -m pytest -q`: **84 passed**
- `python -m compileall -q apps/api/app`: passed
- `node apps/web/tests/visible-product-contract.test.mjs`: passed
- `npx tsc -p tsconfig.contract.json --noEmit`: passed
- Canonical Neon runtime tests: passed, including sale payment, payment reversal, receivable adjustment, return, customer-credit allocation/reversal, and reconciliation closure.
- Canonical validation data removed after testing.

## Deployment

The source package is ready for deployment. The user reports Vercel and Render are currently green, but the updated sidebar source must still land on the deployed Vercel commit. Render's automatic deployment trigger remains a separate infrastructure issue because the latest commit previously required a manual trigger.
