# LEXA Phase 5 — CI Repair and Sales Acceptance

**Prepared against:** `main` at `74ef460c4e2dd90c239f981bf5b2fd7fced7a84d` (25 October 2026)

This ZIP contains repository-root source files for the existing LEXA ZIP Extractor. Upload the ZIP at the repository root while `main` is selected. Do not unzip it on your phone. The extractor applies root-relative files and then triggers Main Build CI.

## Forensic CI repairs

- The EFRIS request middleware no longer inspects or consumes request bodies. It only blocks attempts to submit a fiscal document live.
- Typed EFRIS configuration rejects any mode other than `MANUAL` with HTTP 409 before database writes.
- The Phase 4 reporting-period helper receives its missing TypeScript declaration, addressing the frontend TS7016 error.
- The performance/privacy contract now checks that the request logging middleware never reads request bodies, rather than falsely banning all body handling anywhere in the API.

## Phase 5 sales acceptance hardening

- Checkout requires an `Idempotency-Key`. Retry with the same key and unchanged payload; altered payloads are rejected by the existing idempotency engine.
- Sales no longer enqueue or create fiscal documents from legacy `SYSTEM_TO_SYSTEM` settings. URA documents remain manual-only.
- The existing transaction workflow continues to perform server-owned effective-dated tax calculations, role-checked discounts and price overrides, branch/location authorization, local payment recording, receivable creation, stock ledger movements and journal posting within a rollback-capable transaction.
- Existing return paths remain sale-locked and branch-authorized, with remaining-quantity checks, cumulative refund caps, prorated line values, stock-cost reconciliation, refund/customer-credit entries, and accounting reversals.
- Six backend source-contract tests cover the repaired guards and Phase 5 transaction safety requirements.

## Scope / release note

LEXA records payment methods, amounts and references; it does not move funds or integrate with mobile-money/payment gateways. Tax calculations are local and EFRIS/URA document handling is manual-only. No production database writes or migrations are included in this package.

Checks on this chat-rebuilt package: Python compile passed for the three changed API modules and the added backend test; six new backend source-contract tests passed; the focused manual-only tax/EFRIS frontend contract suite passed 3/3; and the ZIP integrity/path checks passed. The complete backend suite, full frontend suite, TypeScript typecheck, and Next.js production build were passed in the earlier isolated preparation workspace, but were not rerun after reconstructing this attachment locally. Let GitHub Actions validate the exact uploaded commit. These checks do not substitute for authenticated browser/database acceptance or production-checkout verification.
