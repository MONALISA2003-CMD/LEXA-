# LEXA deployment fixes — 13 October 2026

## Changes in this package

- Removed PostgreSQL timeout GUCs from SQLAlchemy connection startup options. Neon PgBouncer can reject these startup options. Transaction-local `SET LOCAL` settings now apply statement, lock, and idle-in-transaction limits after a transaction begins.
- Updated the database hardening regression test to prevent the startup-options regression.
- Removed the incorrect npm cache dependency on `package.json` in root GitHub Actions CI; npm caching requires a lockfile.
- Made malformed/corrupt legacy password hashes fail closed rather than raising a server error during verification.

## Before production deployment

1. Review `git diff --check` and the source diff.
2. Run backend tests and the frontend typecheck/build in CI.
3. Push to GitHub; wait for Vercel and Render deployments to finish.
4. Verify `/health` and `/ready` on the actual Render service, then test login and core workflows.

This package does not claim that production has already been deployed. Environment secrets and live service settings are not included.

## Frontend/Vercel repair follow-up

- The Vercel failure is caused by `apps/web/app/invite/page.tsx` importing `acceptInvitation` from `apps/web/lib/api.ts`, where no such export exists. The current API source also has no invitation-acceptance route, so adding a made-up client wrapper would only move the failure from build time to runtime.
- The frontend now renders a safe, customer-facing unavailable state for invitation links until the backend exposes a real, tested invitation contract. This removes the unresolved import without pretending to activate memberships.
- For Vercel, use Root Directory `apps/web`. The build log's `app/invite/page.tsx` path is relative to that app root. Run `bash scripts/cleanup-obsolete-frontend-routes.sh`, review the intended web-only route deletions, and commit them before switching Vercel to the standard `npm run build` command. The temporary cleanup build command may remain until those deletions land.
- CI now asserts that the invite route does not import the missing API helper.


## Phase 0 reliability repair — v2.8.2

- Fixed the browser/server refresh request contract: frontend sends `{}`; backend also supports HttpOnly-cookie refreshes without a body.
- Added single-flight refresh across concurrent page loaders and session preflight before protected API calls.
- Gated authenticated workspace content until session verification resolves; added retry on transient session checks and reliable local sign-out.
- Dashboard KPI, exception and daily movement components no longer show fabricated zeros/empty states when the API load fails.
- Standardized the Vercel build command in `apps/web/vercel.json` and removed obsolete frontend-only technical routes.
- Added a backend cookie-only refresh regression test and frontend contract tests.

No database migrations, production data, credentials or live environment variables were changed.

## Phase 0 — session and build reliability

- The browser's cookie-backed refresh call now sends an explicit empty JSON object and concurrent refreshes share a single promise to avoid rotating the refresh cookie multiple times in one tab.
- The API refresh handler accepts the HttpOnly cookie even if a client sends no JSON body, avoiding FastAPI's prior 422 validation response for cookie-only refreshes.
- Protected reads wait for a valid in-memory access token; the app shell hides transactional content until session verification completes. The dashboard now distinguishes request failure from real zero-valued business data.
- The web package contains `apps/web/vercel.json` with the standard `npm run build` command. The root ZIP `DELETE.txt` is consumed by the repository's existing ZIP extractor to remove obsolete `apps/web/app/business-engine`, `apps/web/app/kernel`, and generated TypeScript cache without touching backend routes or live business data.
- Local verification: Python suite 96 passed, 1 skipped (optional API dependency stack absent locally); Node frontend contract tests 2 passed; Python compile and TypeScript syntax parsing passed. A full npm install/typecheck/Next.js build was not possible in this environment and must be confirmed by Vercel after extraction/push.
