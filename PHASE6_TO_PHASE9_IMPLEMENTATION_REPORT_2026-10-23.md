# LEXA Phases 6–9 — implementation candidate report

**Date:** 23 October 2026  
**Candidate:** `LEXA_PHASE6_TO_PHASE9_CANDIDATE_2026-10-23`  
**Status:** Implemented locally with targeted acceptance evidence; **not merged, deployed, or production-accepted**.

## Executive summary

This increment carries forward the existing Phase 6 inventory-intelligence, Phase 7 purchasing/supplier, and Phase 8 finance vertical slices in the LEXA source candidate, adds explicit regression coverage for those workflows through the complete existing suite, and implements a new Phase 9 source-linked business-insights endpoint and UI slice.

The Phase 9 implementation is deliberately deterministic and read-only. It answers a small allowlist of question categories by showing the relevant saved metric cards, including current receivables and supplier-ledger balances in one requested currency at a time. It does not send customer or business records or the user's question to a model provider, execute model-generated SQL, change stock, create a purchase order, post a journal, record money, or mutate any business records.

The current revised roadmap defines Phase 9 as explainable, read-only business intelligence and AI. The larger multi-branch/customer-growth programme was moved to Phase 11 in `LEXA_PHASE8_REVISED_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_2026-10-22.md`; this candidate does not mislabel that broader programme as complete.

## Phase coverage

### Phase 6 — Inventory intelligence

Reuses the candidate's established stock-health, movement-history, stock-age, reconciliation, location-specific replenishment policy and deterministic replenishment recommendations. Stock age is not presented as FIFO accounting valuation. Recommendations remain advisory and do not post stock movements or purchase orders. Existing Phase 6 backend/frontend tests are included in this candidate and pass in the final test run.

### Phase 7 — Purchasing and supplier management

Reuses the candidate's supplier terms/effective prices, purchase orders, partial receiving, landed-cost allocation, purchase returns/credits, supplier bills, supplier payments/allocations and supplier-ledger source of truth. No second supplier-payables ledger was introduced. Existing Phase 7 purchasing model, rules, UI/API contracts and regressions are covered by the full local suite.

### Phase 8 — Finance and profitability

Reuses the finance workspace and its source-linked customer receivables, Phase 7 supplier payables, recorded payment methods, draft/post/cancel/reverse expense lifecycle, manual end-of-day reconciliation and financial reports. Payments are records entered by staff, not provider-verified money movement. There is no payment gateway, bank/mobile-wallet connection, payment initiation, or provider credential storage. Gross margin remains distinct from net profit.

### Phase 9 — Explainable, read-only business insights

New implementation:

- `GET /api/v1/analytics/insights` is permission-checked (`analytics.read`), limited to date windows of 93 days, currency-specific, and fail-closed for users without full workspace branch scope because the current projections are workspace-wide.
- Sales movement compares net sales against the immediately preceding period of equal length. A movement of at least 10% is highlighted; a missing baseline does not produce a percentage.
- Gross-margin movement calculates `gross margin = net sales − COGS` and rate from the summed source projection. A change of at least 3 percentage points is highlighted. The UI explicitly warns that gross margin is not net profit.
- Stock-risk insights use the latest saved inventory-health snapshot and mark it stale when more than two days old. The sales/margin metrics are withheld when either their metric refresh or the last successful refresh is older than 72 hours.
- Missing source rows, missing comparisons, stale refreshes and missing stock snapshots are surfaced as unavailable/partial/stale rather than being presented as confident zeroes.
- Results show source tables, dates, refresh timestamps, calculations, limitations, a capped set of item examples, and links back to reports, inventory, finance and purchasing.
- The question router supports sales movement, gross margin, stock risk, and current receivables/supplier balances. It returns a plain explanation and chooses a matching insight card; unsupported questions are not guessed. Questions about net profit are explicitly guarded because that figure is not calculated by this insight layer. Return-only, collections-only and unsupported customer analytics questions are not misrouted to an unrelated card.
- All Phase 9 insight calculation is read-only; no migration is required for this slice.
- A generative-model provider is not connected in this increment. The current implementation is the safe deterministic metric/question foundation; external model explanations remain deferred until their data-processing, retention and permission contract is separately approved.

## Changed source files

- `apps/api/app/business_insights.py` — pure deterministic rules and provenance/limitations output.
- `apps/api/app/routes/analytics.py` — bounded `GET /analytics/insights` endpoint.
- `apps/api/tests/test_business_insights.py` — edge-case tests for missing/stale data, comparative periods, percentage-point margin changes, stock risk and capped evidence.
- `apps/api/tests/test_phase9_insights_contract.py` — permission, branch scope, bounded date and read-only contracts.
- `apps/web/lib/api.ts` — typed insight payload and client API.
- `apps/web/lib/business-insight-question.mjs` and `business-insight-question.d.mts` — allowlisted local question router and type contract.
- `apps/web/lib/business-insight-answer.mjs` and `business-insight-answer.d.mts` — selected-focus mapping that returns only the matching saved insight and explicit unavailable/overview states.
- `apps/web/app/intelligence/page.tsx` — source-linked cards, supported question field, accessible feedback, filters and evidence links plus a direct answer panel with metric, comparison, date scope, source rows, refresh provenance, calculation, limitations and authorized source-screen link.
- `apps/web/app/globals.css` — responsive insight-card/question-field styles.
- `apps/web/app/page.tsx` — show overdue supplier bills in the daily attention queue only when the purchasing summary loaded successfully.
- `apps/web/tests/stage2-3-module-connections.test.mjs` — regression assertion for the new overdue-bill alert.
- `apps/web/tests/phase9-business-insights.test.mjs` — insight and question-router contracts.
- `apps/web/tests/phase7-release-polish.test.mjs` and `tests/unit/test_analytics_currency_contract.py` — update existing expected labels and currency boundary count for the new endpoint.

## Verification performed

The following checks passed against the working candidate:

- Python compile check: `python -m compileall -q apps/api/app apps/api/tests scripts`.
- Complete backend suite: `PYTHONPATH=apps/api python -m pytest -q` — **347 passed**, one existing third-party Starlette cookie deprecation warning.
- Frontend contracts: `node --test tests/*.test.mjs` from `apps/web` — **77 passed, 0 failed, 0 skipped**.
- TypeScript/JSX syntax transpilation for the changed frontend TypeScript files using the globally available TypeScript compiler — syntax diagnostics: none.
- Read-only SQL checks against the isolated `LEXA-PHASE7-REPLAY-20261022` clean replay database — **8/8** query shapes ran successfully for daily metrics, product metrics, last refresh, current receivables, supplier ledger, latest stock snapshot, stock summary and capped stock examples. The replay database contains no business fixtures, so this validates SQL/schema shape only; behavioral edge cases are exercised in helper tests.

## Limits and release gates still open

- The frontend package declares **Node 24.x**, but this runtime has **Node 22.16.0**.
- `npm run typecheck` could not complete because this working copy has no installed `react`, `next` or corresponding type packages. The missing-module diagnostics cascade into JSX/type errors; this is not claimed as a successful full typecheck.
- The Next.js production build, authenticated Playwright E2E, visual/mobile-device review, and end-to-end testing against populated authenticated staging data have **not** been run for this exact candidate.
- The isolated SQL checks used the current replay schema but an empty tenant/business-data fixture set. A separate realistic staging-data acceptance run remains required.
- This candidate has not been committed, merged or deployed. The deployed frontend/API identifiers are not evidence that this unmerged code is live.
- No production code deployment, production database write, or change to the separate `LEXA Backup` project was performed as part of this candidate implementation pass. The existing live schema rollout through migration `043` happened before this pass and is not proof of feature-level E2E acceptance.

## Decision

**Phase 6–8: existing candidate workflows retained and locally regression-tested. Phase 9: deterministic read-only insight/question slice implemented with local targeted acceptance; generative model connection remains intentionally deferred. Overall state: `IMPLEMENTED — LOCAL ACCEPTANCE`, not `PRODUCTION ACCEPTED`.** Proceed to a clean Node 24 install/typecheck/build and authenticated, seeded staging acceptance before publishing or deploying this candidate.


## Frontend review increment (23 October 2026)

The owner dashboard now surfaces overdue supplier bills in “Things to check today” when the authorized purchasing summary successfully loads and the overdue count is greater than zero. The alert links to Purchasing and does not invent an alert if purchasing data is unavailable. The frontend contract suite includes a regression assertion for this behavior. This is a local candidate change, not a deployment.


## Frontend answer-workflow increment (23 October 2026)

The existing Business Insights question field now follows through beyond classification: a supported question renders a focused answer from the matching saved insight, with its original summary, available metric, comparison, reporting period, source tables/row count, refresh provenance, calculation method, visible limitations, and source-screen destination. “All insights” shows coverage counts rather than inventing a general business conclusion. Missing matching insight data remains unavailable; stale or unavailable insight responses do not surface a fabricated value. Editing the question clears the prior answer so an earlier result is not presented as answering new text.

New regression tests cover answer-to-source mapping, stale/missing-data handling, overview counts and the visible provenance panel. Frontend contract count: 77 passed. Full Node 24 typecheck, Next.js production build, authenticated E2E, populated staging and visual device acceptance remain outstanding.
