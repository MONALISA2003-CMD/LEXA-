# LEXA v2.3.0 — Phase 4B

Phase 4B adds accounting, tax and EFRIS foundation capabilities on the canonical LEXA Neon PostgreSQL architecture.

## Highlights

- Chart of accounts and tenant accounting mappings
- Accounting periods and controlled period closing
- Double-entry journals with balanced-posting validation
- Posted-journal immutability and reversal workflow
- Sales revenue and output-tax journal posting
- Payment settlement journal posting
- Inventory COGS posting bridge from authoritative inventory ledger evidence
- Expense records and deterministic expense posting
- Trial balance, income statement and balance sheet functions
- Effective-dated tax rates and scoped tax resolution
- EFRIS configuration and fiscal document queue
- FDN / verification code / QR placeholders that remain empty until returned by EFRIS
- Forced RLS across all Phase 4B tenant tables
- Accounting, tax, expense and EFRIS permissions
- Accounting and Compliance frontend workspaces
- Mobile sidebar containment fix for the previously observed white overlay/asset overflow

## Validation

- 83 automated source/contract tests pass
- Python backend compilation passes
- TypeScript contract compilation passes
- Isolated Neon validation passed for sale accounting, payment accounting, expense posting, tax resolution, journal reversal, financial reports and EFRIS queue creation
- Canonical LEXA Neon migration `020_phase4b_accounting_efris_foundation` is applied

## Canonical Neon

Project: `wispy-mud-75323042`
Branch: `br-soft-star-b1dj2m2w` (`lexa-live`)
Database: `neondb`
