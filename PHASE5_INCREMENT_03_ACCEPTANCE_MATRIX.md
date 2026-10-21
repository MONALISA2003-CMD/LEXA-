# Phase 5 Increment 03 acceptance matrix — 2026-10-21

| Area | Implemented in candidate | Test/evidence | Gate |
|---|---|---|---|
| Multi-line sale & idempotent checkout | Existing Phase 5 code + explicit key/branch authorization | Existing backend/frontend contract tests | Candidate source-level pass; staging flow pending |
| Partial payment/split tender | Existing API and payment allocation ledger retained | Prior staged cases authored; no new staging run | Pending authenticated E2E |
| Cumulative refunds | Gross collection less all recorded refunds, sale lock | Unit/contract + QA function definition | Candidate pass; QA DDL pass |
| Partial return math | Proportional line/disc/tax proration | New pure-helper and source tests | Pass |
| No-refund returns | Reject if open receivable cannot absorb the return | Route contract + DB migration 035 + QA function verification | Pass in candidate/QA function checks |
| Refund settlement ledger | Recalculate sale totals after refund row and on refund mutations | Migration 033 test and QA trigger audit | Pass in QA function checks |
| Customer store credit | Dedicated account 2210 LIABILITY/CREDIT; apply only to target receivable | Migration 034 test + QA mapping/function audit | Pass in QA function checks |
| Return revenue/tax journal | Idempotent `RETURN_SETTLEMENT` journal | Migration 034 test + QA function presence | Function presence verified; transaction E2E pending |
| Returned-stock COGS | Inventory ledger cost reversed via `RETURN_COGS` journal | Migration 034 test + QA function presence | Function presence verified; transaction E2E pending |
| EFRIS return credit note | Pending CREDIT_NOTE for active registered tenant; idempotent | Migration 034 test + QA function presence | Function presence verified; live EFRIS submission not claimed |
| Analytics outstanding balance | Use authoritative `sales.amount_due` | Migration 033 contract + QA function formula audit | Pass for source/function definition; refresh-value integration test pending |
| Sale details / returns UI | Accounting journal and fiscal-document trail | Frontend contract suite 27/27 | Contract pass; browser E2E pending |
| Node 24 clean install/typecheck/build | Project configured for Node 24.x | Current production baseline build has succeeded; candidate clean build not run | **Pending** |
| Live same-SHA Render/Vercel | Current baseline same SHA is green | Render live, Vercel READY, readiness HTTP 200 | Green for baseline only, not candidate |
| Authenticated staged full E2E | Guarded Playwright suite included | Not run due missing isolated service/branch/Redis capacity | **Blocked** |
| Production migrations | Migrations 033–035 packaged | QA branch DDL verified; no prod apply | **Not applied pending review** |

## Local test results

- Backend: 66 passed, 1 skipped (Redis dependency absent).
- Frontend source contracts: 27 passed under Node 22.16.0.
- Python compileall: passed.

Phase 5 cannot be called release-green until the pending Node 24 build and authenticated staging gates pass for a single reviewed source SHA, and migrations are approved for production rollout.
