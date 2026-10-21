> Historical increment snapshot: this report describes the original Increment 03 candidate and its test counts at that time. The current merged core-hardening candidate and authoritative current gates are in `PHASE5_CORE_HARDENING_REPORT_2026-10-21.md` and `PHASE5_RELEASE_GATE_STATUS_2026-10-21.json`.

# Phase 5 Increment 03 — Settlement, Returns, Accounting & EFRIS

## Scope implemented in source

- Cumulative cash-refund cap based on gross recorded allocations minus all prior recorded refunds, protected by sale-row locking.
- Authoritative sale paid/due recomputation driven from collection/refund/customer-credit ledgers and automatic refresh on refund ledger change.
- Quantity-prorated line totals, discounts and tax for partial product returns.
- API + database guard preventing a no-cash/no-credit return from crediting accounts receivable beyond the remaining open receivable.
- Idempotent return settlement journals, separate customer credit liability account (`2210`), returned inventory cost / COGS reversal journal, and pending EFRIS credit-note workflow for active registered tenants.
- Analytics reads `sales.amount_due` instead of independently re-computing due; frontend sale detail and return list surface relevant accounting/fiscal links.
- Added unit/contract coverage and a pinned Playwright runner that refuses write tests unless an explicit staging host, staging fixture and opt-in flag are provided.

## Tests and database evidence

- Backend: **66 passed, 1 skipped**. Skipped auth-refresh integration requires Redis absent from the offline runner. Python compileall passed.
- Frontend contract tests: **27/27 passed** under Node 22.16.0.
- Neon QA branch `br-young-base-b1mi15fs`: migrations 033–035 recorded. Read-only verification confirmed the cumulative refund function, refund trigger, analytics due formula, `CUSTOMER_CREDITS` mapping to account 2210 LIABILITY/CREDIT, return settlement journal function, return COGS journal function, optional EFRIS credit-note function and receivable guard. RLS-disabled=0, RLS-not-forced=0, sales=0, journal entries=0.
- Production Neon: no changes in this increment. The live branch stays on migration 031.
- Render/Vercel live baseline: both on SHA `779f8fe5dc704411b9abab371a29311e7dbc844a`; Render deploy is live, Vercel deployment is READY, and both readiness endpoints returned HTTP 200 with database/cache OK.

## Not yet proven

- Local runner uses Node 22.16.0, not Node 24. A clean Node 24 `npm ci` + typecheck + test + build of the Increment 03 working tree has not completed. The Vercel project is configured for 24.x, but the currently deployed source is not the Increment 03 source.
- Authenticated Playwright staging E2E has not run. The current workspace has no isolated LEXA staging service; the available Neon QA branch inherits parent data and is not sanitized staging; branch and Render Key Value quotas prevent creating a full isolated environment on the current plans.
- Direct GitHub branch/file writes previously returned 403. These source changes are in the package, not committed/deployed.
- Migration 021 is a clearly labelled repaired source candidate, not byte-recovered historical SQL; source parity remains false. The six accepted historical migration sources remain substitutes. A `032_phase5_return_settlement_reconciliation` ledger entry exists on a previous QA branch, but the corresponding SQL source is absent from the repository; migrations 033–035 provide the current replacement behavior without claiming historical 032 parity.

## Release position

**Implemented as a review candidate; not release-accepted.** Upload the package through the approved extractor, run the clean Node 24 pipeline on the resulting SHA, deploy that same SHA to Render/Vercel, validate all migrations against clean staging, and run the guarded authenticated Playwright suite on disposable fixtures. Do not run mutating E2E against production.
