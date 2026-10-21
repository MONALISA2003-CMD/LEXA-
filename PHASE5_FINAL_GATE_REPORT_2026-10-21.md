# LEXA Phase 5 — Final Gate Report

**Review date:** 2026-10-21 (Africa/Kampala)  
**Latest uploaded GitHub revision:** `779f8fe5dc704411b9abab371a29311e7dbc844a`  
**Candidate package:** Phase 5 Increment 03 (local source delta, not committed)  
**Disposition:** **Current deployed baseline is green on Render and Vercel. Increment 03 is locally implemented and tested but is NOT release-accepted until the candidate is uploaded, built and accepted on isolated staging. Phase 6 remains blocked.**

This report deliberately separates the **currently deployed baseline** from the new Phase 5 Increment 03 source. A healthy production readiness response is not evidence that the new, uncommitted files are live.

## Gate summary

| Gate | Evidence | Result |
|---|---|---|
| Source baseline | GitHub `main` latest upload is `779f8fe5dc704411b9abab371a29311e7dbc844a`; Increment 03 working-tree delta is in this ZIP only | **Amber — source handoff** |
| Vercel production | `dpl_DhA4A5ZFDg9LYVSpuY7rjSxHGCTx` is `READY` on SHA `779f8fe5…`; project Node version configured as 24.x | **Green for currently deployed revision** |
| Render production | `dep-dbca7f8u01pc73d2doj0` is `live` on the same SHA `779f8fe5…` | **Green for currently deployed revision** |
| Readiness | Render `/ready` and Vercel same-origin `/api/lexa/ready` both returned HTTP 200 with DB/cache OK | **Green smoke test for deployed baseline** |
| Backend tests | `python -m compileall -q apps/api/app apps/api/tests`; pytest `66 passed, 1 skipped` | **Green for local candidate contracts/unit tests; Redis integration skipped** |
| Frontend contract tests | `node --test apps/web/tests/*.test.mjs`: 27/27 under Node 22.16.0 | **Green for source contract tests** |
| Clean Node 24 suite | Fresh `npm ci`, typecheck, tests and build have not been run on Increment 03 candidate. Local runner only has Node 22; Vercel Sandbox allocation has been blocked by Hobby snapshot-storage quota. | **Pending** |
| Neon production RLS/runtime | Current production branch remains at migration 031; 119 public tables RLS enabled and forced; runtime login is least-privilege. No production SQL mutation made this increment. | **Green for existing production baseline** |
| Neon QA DDL verification | Branch `br-young-base-b1mi15fs` has migrations 033–035 and all new functions/triggers; RLS disabled/not-forced counts both zero; sales and journal entries both zero. | **Green for DDL/source-function checks only** |
| Authenticated staging E2E | Not run: no separate LEXA staging service; Neon branch quota is full; Render Free plan has its one Key Value instance already used. QA branch carries parent data and is not sanitized. | **Blocked — fail closed** |
| Production migration rollout | Candidate migrations 033–035 have NOT been applied to production | **Pending review/approval** |
| Historical source parity | Six accepted historical source gaps remain byte-unrecovered; migration 021 is a labelled repair candidate; a QA-only 032 ledger entry lacks a source file in this repository. | **Amber — no parity claim** |

## What Increment 03 implements

1. **Refund integrity:** refund capacity is computed from the original recorded collections minus all previously recorded refunds, avoiding double-subtraction after sale totals have already become net of refunds. Sale paid/due amounts are recalculated from payment/refund/credit ledgers and a refund-row trigger keeps them synchronized.
2. **Return math:** partial return quantities prorate discounts, taxes and line totals; previously completed quantities are excluded from further return allowance.
3. **Settlement accounting:** completed returns produce an idempotent `RETURN_SETTLEMENT` journal, including sales-return/tax reversals and the right balancing path for cash refund, customer credit or an open receivable.
4. **Inventory and cost:** returned stock is posted through the existing stock ledger and a `RETURN_COGS` journal reverses COGS when there is recorded returned inventory cost.
5. **Customer credit:** code 2210 is mapped as a dedicated customer-store-credit liability; unallocated credit does not silently write off the source sale’s receivable. Allocated credit only reduces the receivable it is applied to.
6. **EFRIS:** an active registered tenant receives an idempotent pending `CREDIT_NOTE` fiscal document/event for the completed return. No live EFRIS submission is claimed.
7. **Analytics/UI:** analytics reads authoritative `sales.amount_due`; sale details and returns expose accounting journal/fiscal-document references; safe staging Playwright contracts cover checkout and refund/return flows.
8. **Receivable guard:** no-refund/no-credit return settlement is rejected if the open receivable cannot absorb the full return, in both API validation and database function.

## Verification performed

- Backend: **66 passed, 1 skipped**. The skip is `apps/api/tests/test_auth_refresh.py` because Redis is not installed in this offline test environment. Python `compileall` passed.
- Frontend contracts: **27 passed** under Node 22.16.0. These are lightweight source-contract tests, not browser acceptance.
- QA Neon branch: installed/verifed migrations `033_phase5_refund_settlement_consistency`, `034_phase5_return_accounting_journals`, and `035_phase5_none_return_receivable_guard`; verified corrected payment/refund totals function, refund synchronization trigger, analytics `amount_due` formulas, 2210 credit-liability mapping, return settlement and COGS functions, fiscal credit-note function, and no-refund receivable guard. RLS disabled=0, RLS not forced=0, sales rows=0, journal rows=0.
- Live endpoints: `/ready` and Vercel’s same-origin readiness proxy both return HTTP 200 for the currently deployed baseline commit `779f8fe5…`.
- A raw scraper request briefly returned a Render block/challenge page with HTTP 503 and the same-source proxy returned `UPSTREAM_UNAVAILABLE`; re-checking with a browser-side fetch for Render and the Vercel-owned fetch tool returned HTTP 200 from both with `database: ok` and `cache: ok`. Render remained not suspended, latest deploy status is live, no matching Render 5xx log rows were found, and Vercel had no runtime-error cluster. The successful re-checks are used as the current readiness evidence; the earlier raw-scraper 503 is recorded as an intermittent scraper/proxy response, not silently discarded.

## Why the new candidate is not release-accepted

The Increment 03 code and migrations are local source files in the full-source ZIP and are **not** part of the deployed SHA `779f8fe5…` yet. The connected GitHub integration previously denied direct branch/file writes with HTTP 403, so this package has not been committed. A separate clean Node 24 install/build is pending. Authenticated Playwright tests create sales/returns and must run only against a distinct, sanitized staging service; the present QA Neon branch is parented to production and not a safe mutating staging target. The Neon project is at its branch limit and Render Free allows only one Key Value instance, currently used by production.

## Required promotion sequence

1. Upload the supplied full-source ZIP through the existing approved ZIP extractor and verify the produced GitHub SHA contains migrations 033–035 plus the Phase 5 source/tests/UI changes.
2. Run clean Node 24 `npm ci`, `npm run typecheck`, `npm test`, and `npm run build`, plus backend tests with Redis installed so the auth-refresh integration executes.
3. Confirm Render and Vercel both deploy that **same exact reviewed SHA** and readiness returns 200 after the API startup imports successfully.
4. Provision genuine isolated staging (sanitized Neon DB/branch, non-production API and Redis, preview-specific API origin, disposable cashier and manager accounts). Resolve Neon branch quota / Render KV capacity without deleting unknown branches or changing billing automatically.
5. Run `apps/web/e2e/phase5-sales-acceptance.spec.ts` in staging for split tender, partial payment, idempotent retry, stock ledger read-after-write, refund cap, permissions, branch denial, return settlement, accounting journals, and EFRIS pending credit note. Reconcile amounts before promotion.
6. Review migrations 033–035 and the repaired migration 021 candidate, then apply production schema changes only under an approved rollback/backup plan.

**No production sales, returns, refunds, stock movements, roles or schema were modified in this increment.** Do not advance to Phase 6 until all pending gates are green.
