# LEXA Phase 0/1/2 repair + CI run 40114334149 correction

**Package date:** 24 October 2026  
**Repository:** `MONALISA2003-CMD/LEXA-`

## Important status

This is a canonical-path **source patch**, not a full application archive and not a deployment. It contains the Phase 1 business-grounded assistant source/test corrections plus a Phase 2 cross-module transaction acceptance route and staging-only browser journey. At package root it includes `apps/api/app/main.py`, `apps/web/package.json` and `migrations/` so the repository's **LEXA ZIP Extractor** recognizes it instead of saving it under a nested `source/` folder.

The newest inspected red build is `40114334149` on SHA `1e93fc87022bf7d31cae0ae00c537371af148ccb`. API contracts, Docker/HAProxy and web typecheck passed; the web test suite reported 97 passed and 2 failed because the Phase 5 and Phase 7 contract tests still expected the old combined Playwright matcher. This ZIP updates those two assertions to match the actual separate Phase 2 and Phase 5–8 matchers. The production build did not run because `npm test` failed. **This is a targeted corrective patch, not proof of a green rerun.** GitHub access denied direct branch creation (HTTP 403), so a new run can only be confirmed after this ZIP is extracted/committed by the repository workflow.

## Apply and verify

1. Upload this ZIP at the repository **root** with the existing LEXA ZIP Extractor. Do not upload it under `.github/workflows/` or extract it into a new enclosing folder.
2. Wait for the extractor to create its commit and inspect the commit file list. It must include canonical paths like `apps/api/app/main.py`, `apps/api/app/routes/transaction_evidence.py`, `apps/web/e2e/phase2-transaction-acceptance.spec.ts` and `apps/web/playwright.config.ts`, not only `source/...` paths.
3. Confirm the extractor's **Dispatch the single canonical LEXA CI** step actually ran. Then verify every job in `LEXA Main Build CI` on that exact new SHA: API pytest, Node 24 contracts, typecheck, Next.js production build, and Compose/HAProxy config.
4. Do not treat successful extraction, a green extractor job, or a READY preview deployment as proof that Main Build CI passed.
5. Deploy only after CI is green and verify Render and Vercel use the same validated SHA.

The linked GitHub integration rejected direct branch creation with HTTP 403 during this repair, so this patch is prepared for the repository's existing extractor path rather than falsely claiming a direct commit or pull request.

## Database status

Production Neon migrations `045`, `046` and `047` have already been applied and verified; **do not rerun these migrations**. The Phase 2 addition requires no new schema migration. Production business tables still have no real sales, payments, inventory movements, journals or daily/product analytics metrics. The Phase 2 test uses only a separately provisioned disposable staging tenant and never seeds production.

## Phase 2 staging gate

See `PHASE2_STAGING_ACCEPTANCE.md`. The authenticated browser test is skipped unless explicit staging-only write opt-in, HTTPS allow-list, a disposable tenant fixture, QA storage state, and a healthy staging `/api/lexa/ready` check are supplied. The test also rejects known production hostnames. Do not enable it against production.
