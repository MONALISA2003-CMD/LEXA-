# LEXA Phase 4B — Accounting, Tax and EFRIS Foundation

## Scope

Phase 4B adds the deterministic financial foundation that sits between the Phase 4A commercial records and later intelligence/reporting:

`Sales → Payments & Receivables → Accounting → Reconciliation → Business Intelligence`

Tax calculation remains deterministic. EFRIS is a separate compliance layer and does not become the payment or accounting source of truth.

## Research basis

### Uganda Revenue Authority

URA's current EFRIS guidance states that EFRIS is the Electronic Fiscal Receipting and Invoicing Solution and is mandatory for VAT-registered businesses and businesses in designated sectors. URA also states that EFRIS supports e-invoices/e-receipts and can operate offline for up to five days on supported channels.

Source: https://ura.go.ug/en/efris/

URA's invoice/receipt guidance identifies the fiscal document number (FDN), verification code and QR code as key features of EFRIS fiscal documents.

Source: https://ura.go.ug/en/efris/invoice-receipt-issuance/

URA's current accredited-integrator page is dated 14 July 2026, confirming that system-to-system integration is an available integration model rather than a requirement for the internal accounting model.

Source: https://ura.go.ug/en/efris/list-of-accredited-efris-software-integrators/

### IFRS presentation reference

IAS 1 defines the structure and minimum content of a complete set of financial statements, including financial position, profit or loss and other comprehensive income, changes in equity, cash flows and notes.

Source: https://www.ifrs.org/issued-standards/list-of-standards/ias-1-presentation-of-financial-statements/

## Implemented

### Accounting

- Tenant-scoped chart of accounts.
- Accounting periods with OPEN/CLOSED/LOCKED states.
- Double-entry journal entries and lines.
- Balanced posting validation.
- Posted journal immutability.
- Reversal workflow instead of destructive editing.
- Deterministic sale revenue/tax recognition.
- Deterministic payment settlement posting.
- Weighted-average inventory COGS journal bridge where inventory ledger evidence exists.
- Expense journal posting.
- Trial balance.
- Income statement.
- Balance sheet.
- System account mappings for payment channels and core financial accounts.

### Tax

- Effective-dated tenant tax rates.
- Default/product/category tax configuration scopes.
- Deterministic tax-rate resolution.
- Historical transaction tax remains stored on commercial transaction records.

### EFRIS

- Tenant EFRIS configuration without storing URA login passwords, OTPs, API secrets or payment credentials.
- Fiscal document records separated from internal payment/accounting records.
- Fiscalization event queue with retry-ready status model.
- FDN, verification-code and QR-code fields are populated only from an actual fiscalization response; LEXA never invents them.
- Immutable accepted/voided fiscal document facts.

### Security

All new Phase 4B tables are forced tenant RLS tables. Accounting and EFRIS permissions are role-scoped and audit-ready.

## Product boundary

This phase does **not** claim a live URA/EFRIS system-to-system connection. The integration boundary is represented explicitly so that an accredited/approved integration can be added later without changing LEXA's internal accounting truth.
