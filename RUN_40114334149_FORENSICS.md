# Forensic addendum — Main Build CI run 40114334149

**Audit timestamp:** 24 October 2026 (UTC)  
**Repository:** `MONALISA2003-CMD/LEXA-`  
**Failed run:** https://github.com/MONALISA2003-CMD/LEXA-/actions/runs/40114334149  
**Inspected main commit:** `1e93fc87022bf7d31cae0ae00c537371af148ccb`

## Exact CI result

The run checked out the above commit. Its three jobs ended as follows:

| Job | Result |
|---|---|
| API unit and contract tests (no staging) | Passed |
| Docker Compose and HAProxy configuration | Passed |
| Web typecheck, contracts and production build | Failed in `npm test` |

The web TypeScript typecheck passed. The contract command ran **99 tests: 97 passed, 2 failed**. The Next.js production build was **not run** because the test command exited non-zero.

## Root cause (reproduced from job log and origin source)

Two static contract tests were still checking the former *single* matcher source string:

- `apps/web/tests/phase5-e2e-safety-contract.test.mjs`
- `apps/web/tests/phase7-purchasing-contract.test.mjs`

Both expected `/phase(2-transaction|5-sales|6-inventory|7-purchasing|7-authorization|8-reports)-acceptance/`. The actual origin config deliberately has two independently named matchers:

- `phase5Through8AcceptancePattern` for phases 5–8
- `phase2TransactionAcceptancePattern` for the Phase 2 transaction-chain scenario

and declares `testMatch: [phase5Through8AcceptancePattern, phase2TransactionAcceptancePattern]`.

This is a **test/config expectation mismatch**, not a demonstrated runtime checkout or TypeScript failure. The new Phase 2 contract test itself passed in this run. The mistake in the preceding bundle was that the Phase 2 contract had been updated, but these two older tests retained assertions for the former combined matcher; that oversight is corrected in this bundle.

## Change in this bundle

Both stale assertions now check the real explicit matcher declarations and the `testMatch` array. The Phase 5–8 matcher still names sales, inventory, purchasing, authorization and reports; the Phase 2 matcher remains separate. Staging safeguards, HTTPS allow-list, known-production denial, disposable-tenant checks, authenticated storage-state and readiness checks remain untouched.

A local source-contract probe is included in the validation process to confirm the two pattern declarations cover `phase2-transaction-acceptance.spec.ts`, `phase5-sales-acceptance.spec.ts`, `phase6-inventory-acceptance.spec.ts`, `phase7-purchasing-acceptance.spec.ts`, `phase7-authorization-acceptance.spec.ts`, and `phase8-reports-acceptance.spec.ts`.

## Deployment snapshot at the time of inspection

Vercel's deployment API listed production deployment `dpl_5KDrTKdfjjahCkEx5ADXLAYFrymw` as `READY` for exactly commit `1e93fc87022bf7d31cae0ae00c537371af148ccb`. A Vercel runtime-error query for the previous 24 hours returned “No runtime errors found”; a production error/fatal log query over the previous 30 minutes returned no matching logs. The separate 24-hour raw log query was unavailable on the account's retention tier, so absence of those logs is not evidence of no application faults. `READY` is deployment state, not proof of correct business behavior.

Render was not inspected because its integration requires the user to confirm the workspace before querying any service. No Render action or deployment was performed.

## Remaining release gates — do not waive

1. Extract the bundle through the canonical LEXA ZIP workflow.
2. Wait for a **new** CI run on the resulting source SHA; confirm all 99 web contracts pass, then the Next production build actually runs and passes, alongside the API and Compose/HAProxy jobs.
3. Run the opt-in Phase 2 scenario on a disposable HTTPS staging tenant; do not treat the skipped-by-default test or static contracts as a live transaction acceptance result.
4. Compare Vercel and Render source SHAs and smoke-test readiness, login and authenticated business flows before calling either service healthy.
5. Do not claim real URA EFRIS or live mobile-money integration: registered test/merchant accounts, current official specs, credentials, authenticated callbacks and reconciliation evidence are prerequisites and are not included in this patch.

**Integrity note:** this incident addendum records the precise observed failure and the corrective source change; it does not misrepresent a not-yet-run full CI/build or staging acceptance as passed.
