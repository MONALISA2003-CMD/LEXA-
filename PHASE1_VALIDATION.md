# LEXA Phase 1 / Phase 2 validation and release record

**As of:** 24 October 2026

## Database facts already verified

- Production migrations 045, 046 and 047 were applied in order and their versions are present in `public.schema_migrations`. Do not rerun them.
- Production had 134 public base tables and all 134 had both RLS enabled and `FORCE ROW LEVEL SECURITY` enabled.
- Intelligence/document tables exist; the bounded forecast-baseline refresh completed with zero reported failures and seven recent successful 56-day windows for the seven active tenants.
- The production business ledger still has no sales, payments, inventory movements, journal entries or daily/product metric rows. Do not generate production fixture data or infer forecasts from successful refresh coverage alone.

## CI observations

- The latest failed canonical Main Build CI inspected during this repair was run `40100560783` on old SHA `d5be996d8cf45c93200351c6a21251c4d3a6c934`.
- That failed run had three web contract assertions against older compliance copy, plus two API test expectations that had gone stale against the configured provider default/capability response.
- The current canonical `main` source now includes the corresponding source/test fixes. However, no fresh fully green CI run on the latest source SHA was confirmed while preparing this archive. Do not report the workflow as fixed until the new extractor-generated commit's canonical CI is green.
- Prior ZIP Extractor run `40104642951` reported success while skipping the archives because they lacked recognizable marker files at the archive root; no source commit was created and the canonical CI dispatch step was skipped. This new archive intentionally includes `apps/api/app/main.py`, `apps/web/package.json`, and `migrations/` at its root so the extractor can identify it.

## Local checks for this bundle

- Python compilation of the new transaction evidence route, API main and contract tests passed.
- New API contract tests: 2/2 passed.
- Focused Node checks for business-grounded assistant, URA/external question policy, and Phase 2 transaction acceptance contract: 5/5 passed.
- TypeScript syntax transpilation for the new Playwright acceptance spec, global setup and Playwright config: zero syntax diagnostics.

## Not verified yet

- Full canonical API pytest run on this complete bundle.
- Full Node 24 test suite, web typecheck and Next.js production build on this complete bundle.
- The authenticated Phase 2 E2E using a provisioned disposable staging tenant and QA storage state.
- Deployment of the exact validated commit to both Render and Vercel.

Upload this archive at the repository root using LEXA ZIP Extractor. Verify that it creates a commit with canonical `apps/api/...` and `apps/web/...` changes; then verify the exact commit SHA and all `LEXA Main Build CI` jobs before promoting it.
