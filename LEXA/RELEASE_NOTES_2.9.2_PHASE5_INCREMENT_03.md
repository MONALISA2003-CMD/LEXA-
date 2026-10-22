# LEXA 2.9.2 — Phase 5 Increment 03 candidate

## Added
- Refund/return settlement consistency and refund-table refresh trigger.
- Correct partial-return discount/tax proration and no-refund receivable guard.
- Idempotent accounting journals for sales returns and returned-inventory COGS.
- Dedicated customer store-credit liability mapping and optional EFRIS credit-note workflow.
- Analytics based on authoritative sale receivable balance and accounting/fiscal trail on the frontend.
- Guarded Playwright acceptance cases and regression/source contracts.

## Verification
- 66 backend tests passed, 1 skipped due to missing Redis in the offline local runner.
- 27 frontend contract tests passed under Node 22.16.0.
- Phase 5 migrations 033–035 and important function definitions verified on the non-production Neon QA branch; no sales or journal rows were created there.
- The currently deployed baseline revision `779f8fe5dc704411b9abab371a29311e7dbc844a` is live on Render and READY on Vercel. This Increment 03 candidate has not yet been committed/deployed.

## Release status

Candidate only, not release-accepted. Clean Node 24 `npm ci`/typecheck/test/build, authenticated isolated staging E2E, same-SHA Render/Vercel deployment, source/migration replay review and approved production migration rollout remain open. Canonical migration-source parity is not proven.
