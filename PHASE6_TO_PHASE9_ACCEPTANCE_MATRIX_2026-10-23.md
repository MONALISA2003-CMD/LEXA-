# LEXA Phases 6–9 — acceptance matrix

**Candidate:** `LEXA_PHASE6_TO_PHASE9_CANDIDATE_2026-10-23`  
**Date:** 23 October 2026  
**Status:** Local candidate evidence only; not production-accepted.

| Phase / outcome | Implemented in candidate | Evidence completed here | Remaining acceptance |
|---|---|---|---|
| **6 — Inventory intelligence** | Stock health, movement history, age analysis, reconciliation status, explainable replenishment policies/recommendations; no automatic inventory or purchasing mutation. | Existing inventory backend/frontend regression suites pass in the 306-test backend and 62-test frontend suites. Python compile passes. | Seeded browser flow for age bands, unknown history, location scoping and reconciliation; Node 24 build and exact-candidate staging. |
| **7 — Purchasing and supplier management** | Supplier profiles/terms/prices, orders, partial receiving, landed costs, supplier returns/credits, bills, payment allocation and shared supplier ledger. | Existing purchasing rules, model validation, API/UI contracts and idempotency regressions pass in full local suites. No duplicate payables ledger introduced. | Authenticated E2E with supplier/order/partial-receipt/return/bill/payment fixtures; realistic multi-branch denied-scope test. |
| **8 — Finance and profitability** | Customer receivables, Phase 7 payables, human-entered payment methods, expenses with traceable correction/reversal, manual cash reconciliation and source-linked reports. | Finance workflows, payment reference safety, record/currency contracts and report/UX regressions pass in full local suites. | Seeded reconciliation of sales/collections/credit/returns/expenses/COGS; mobile browser workflow; full Node 24 typecheck/build. |
| **9 — Explainable insight layer** | Read-only sales movement, gross-margin movement, stock-risk and current receivables/supplier-ledger balances; source/date/formula/freshness/limitations; allowlisted question router and net-profit guardrail. No external model receives business records. | Fourteen pure rule tests; read-only/authorization/date-limit contract tests; frontend question-router/UI tests; 8/8 SQL query shapes succeed against isolated clean schema. | Authenticated seeded-data end-to-end verification; confirm evidence links follow effective permissions; Node 24 typecheck/build; review supported-question UX on a phone-sized viewport. Generative-model explanation remains deferred pending a separate data-processing contract. |

## Cross-cutting checks

| Check | Status | Evidence / limitation |
|---|---|---|
| Python compile | PASS | `python -m compileall -q apps/api/app apps/api/tests scripts` |
| Backend suite | PASS | `PYTHONPATH=apps/api python -m pytest -q` — 306 passed, 1 third-party deprecation warning |
| Frontend contracts | PASS | `node --test tests/*.test.mjs` — 62 passed, 0 failed, 0 skipped |
| Changed TSX/TS syntax | PASS | TypeScript transpile diagnostics: none |
| Frontend full typecheck | BLOCKED | Dependencies not installed; missing `react`/`next` declarations; runtime is Node 22.16.0 while project requires Node 24.x |
| Next.js production build | NOT RUN | Needs a clean Node 24 install |
| Authenticated browser E2E / mobile UX | NOT RUN | Requires staging credentials and seeded non-production data |
| Production code deployment | NOT DONE | Candidate remains local/unmerged |
| Production feature acceptance | NOT ACCEPTED | Must wait for exact-candidate Phase 12 gate |
| `LEXA Backup` integrity | PRESERVED | No edits, SQL writes or restore operations against the backup project |

## Scope note

The latest `LEXA_PHASE8_REVISED_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_2026-10-22.md` moves the broader multi-branch/customer-growth programme to **Phase 11**. This increment covers Phases 6–8 as existing candidate workflows and implements the current revised Phase 9 outcome. It does not claim the broader Phase 11 work or Phase 12 launch gate as complete.
