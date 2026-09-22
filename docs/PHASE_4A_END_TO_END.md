# LEXA Phase 4A End-to-End Release

## Canonical Neon target

- Project: `wispy-mud-75323042`
- Branch: `lexa-live` (`br-soft-star-b1dj2m2w`)
- Database: `neondb`
- Scope: LEXA Neon PostgreSQL only

## What is connected

The Phase 4A commerce surface now connects the browser UI to the LEXA FastAPI API, and the API uses the canonical Neon tenant/RLS context for the same domain model.

Browser flow:

`LEXA Web → /api/lexa proxy → FastAPI /api/v1/commerce/* → SQLAlchemy/SQL → Neon PostgreSQL`

Core workflows:

- customer creation and lookup
- payment-channel configuration without credentials
- product/location lookup
- sales checkout
- split payment allocations
- credit sales and receivables
- receivable payment
- inventory reduction through the immutable inventory ledger
- sale returns
- refund records
- customer-credit records
- daily reconciliation
- actual settlement entry
- variance acknowledgement
- business-day closing
- sales history

## Database safeguards

Migrations `015`, `016`, `017`, `018`, and `019` are recorded on the canonical branch.

Phase 4A currently has 12 tenant-scoped tables with forced RLS and one tenant isolation policy each.

The application integrity layer enforces:

- payment allocations cannot exceed the payment amount
- sale allocations cannot exceed the remaining sale amount
- receivable allocations cannot exceed the receivable amount
- recorded payment facts are immutable
- voided/reversed payments automatically reverse recorded allocations
- receivables refresh from recorded allocations
- sale paid/due totals refresh from allocations
- reconciliation expected amounts are deterministic
- reconciliation variances are deterministic
- closed reconciliations cannot be edited
- zero-variance reconciliation can close without manual variance handling
- return adjustments update sale and receivable values atomically
- customer credit allocations update credit balances and receivables deterministically
- customer credit allocations require matching customer ownership and cannot over-allocate
- customer credit reversals restore both credit and receivable balances
- critical reconciliation mutations use idempotency keys

Payment channels contain only business configuration fields: name, channel type, provider, currency, active state. No bank/mobile-money credentials are stored.

## Verification performed

Backend/source contracts: `84 passed`.

Frontend contract TypeScript check: passed with the repository-local contract stubs used for this sandbox because the production `node_modules` set is not installed in the working container.

Python bytecode compilation: passed for the commerce backend route.

Canonical Neon runtime validation passed for:

- sale payment allocation and automatic totals
- payment reversal and automatic allocation reversal
- receivable balance adjustment after a return
- reconciliation expected amount and variance calculation
- zero-variance reconciliation header transition
- reconciliation close
- rejection of edits after close

All Phase 4A validation data was removed after testing. Canonical live counts after cleanup were zero for validation parties, payment channels, business transactions, payments, reconciliations, inventory transactions, and outbox events. Existing audit rows were preserved.

## Deployment status

The source and canonical Neon database are aligned in this release package.

Hosted Render/Vercel deployments are not claimed as repaired by this ZIP alone. The existing repository integration previously returned a GitHub write permission error, so a new hosted deployment still requires the changes to land on the repository's deployment branch and for the hosting providers to build them.

The package includes the deployment repair source changes already identified earlier, including the FastAPI kernel import correction, the business-engine quantity type correction, and the workspace boot hardening.
