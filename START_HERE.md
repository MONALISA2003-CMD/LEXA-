# LEXA Phase 0/1/2 repair + Phase 3 local tax and manual-only compliance

**Package date:** 24 October 2026  
**Repository:** `MONALISA2003-CMD/LEXA-`

## Important status

This is a canonical-path **source patch**, not a full application archive and not a deployment. It contains the Phase 1 business-grounded assistant source/test corrections, a Phase 2 cross-module transaction acceptance route and staging-only browser journey, and Phase 3 local Uganda tax calculators with manual-only payment/EFRIS recordkeeping. At package root it includes `apps/api/app/main.py`, `apps/web/package.json` and `migrations/` so the repository's **LEXA ZIP Extractor** recognizes it instead of saving it under a nested `source/` folder.

The prior corrective ZIP has been uploaded by the owner; the owner reports its GitHub CI is green and Vercel is deployed. The base source inspected before this Phase 3 overlay is `085eee35fdc93d736d2febea7ad9c09967c94e72`. Render was then deployed to that same SHA and `/ready` returned HTTP 200 with database/cache healthy. This new Phase 3 overlay adds local Uganda tax estimates and manual-only payment/EFRIS recordkeeping. **It has not yet been extracted or tested by full GitHub CI and is not yet deployed.** The root package is an overlay, not a full repository archive; extract it at repository root using LEXA ZIP Extractor and require a fresh green Main Build CI before deploying.


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

## Phase 3 policy

The overlay adds Python/Decimal calculations for Uganda VAT, all published presumptive-tax bands, resident/non-resident PAYE and conditional withholding estimates using official sources available by 23 October 2026. Targeted local validation passed: **13 Python tests**, **5 Node tests**, Python compilation and compliance-page TypeScript syntax transpilation. The complete web suite, full typecheck, production build and post-extraction GitHub CI remain unverified. No URA, mobile-money or payment-gateway integration is added. LEXA records payment methods only and blocks EFRIS submission. A standard 18% default VAT rule requires explicit owner confirmation, date-scoped configuration and correct inclusive/exclusive price treatment. The VAT-registration threshold is disclosed as conflicting across two current official pages (URA FAQ UGX 300m vs Government VAT page UGX 250m); LEXA does not infer legal registration status. Review `PHASE3_URA_AND_MOBILE_MONEY_INTEGRATION_GATES.md`.
