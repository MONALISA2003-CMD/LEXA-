# LEXA Phase 5 — Final Gate Report

**Review date:** 2026-10-21 (Africa/Kampala)  
**Pinned GitHub source revision:** `d228e6467894857aeeb632a189d10680179404db`  
**Repository:** `MONALISA2003-CMD/LEXA-`  
**Decision:** **Phase 5 is NOT release-accepted. Do not advance to Phase 6 yet.**

This report distinguishes deployed evidence from local candidate validation. Passing UI tests and an accessible production readiness endpoint do not prove a same-commit, authenticated frontend → API → Neon end-to-end release.

## Executive status

| Gate | Verified state | Result |
|---|---|---|
| Source revision | GitHub `main` at `d228e6467894857aeeb632a189d10680179404db`; package manifest still marks canonical source parity false | **Amber** |
| Vercel production build | Deployment `dpl_4h1ftGMSNohHWvgxMqjpN2FwJQuD` is `READY`, target `production`, commit matches the pinned revision | **Green for frontend build only** |
| Node version | Vercel project setting is `24.x`; deployed build completed TypeScript and Next production build | **Green for deployed build; clean `npm ci` still not run** |
| Frontend contracts | 25/25 passed locally under Node 22.16.0 | **Green for source contracts** |
| Backend unit/contract suite | 43 passed, 1 skipped locally; the skipped auth-refresh integration requires Redis | **Green for available tests; one dependency test outstanding** |
| Render deployment | Deployment `dep-dbc9rmo473hc73a6niog` for the same pinned commit failed at startup with `ImportError: cannot import name '_set_refresh_cookie' from 'app.auth'` | **Red** |
| Live API readiness | Current older live Render deployment returns HTTP 200 `/ready` with database and cache `ok`; current live deploy remains on commit `c1cd002bece6de028357d7ed156c6f03d3d5a7f7`, not the pinned frontend SHA | **Amber — code mismatch** |
| Vercel → API proxy | `https://lexa-green.vercel.app/api/lexa/ready` returned HTTP 200 and the expected dependency readiness JSON | **Green for read-only proxy smoke** |
| Neon RLS | 119 public base tables have RLS enabled and forced; RLS-disabled and not-forced lists empty | **Green** |
| Neon runtime role | `lexa_runtime_login_p3`: login enabled, not superuser, no inherit, no create DB/role, no bypass RLS; member of `lexa_app` | **Green** |
| Neon migration 031 | `031_phase3_auth_surface_rls` is present in `schema_migrations` | **Green** |
| Neon query health | No long-running queries over 5 minutes; no locks returned by the read-only inspection | **Green at audit time** |
| Neon production branch protection | Enabling protection was refused by Neon because the plan has reached its protected-branch quota; branch remains unprotected | **Amber — plan restriction** |
| Authenticated staging E2E | Not run. There is no isolated Render staging service; current Vercel API-origin variables are production-only and code defaults to production Render URL | **Blocked for safety** |
| Preview deployment | No safe preview built from the locally repaired source: GitHub branch creation and direct file update both returned 403; Vercel Sandbox creation is blocked by the Hobby snapshot-storage quota | **Blocked** |
| Production data writes | None made by this gate review | **Confirmed** |

## Concrete Render startup failure and local repair

The pinned source's `apps/api/app/routes/workspace_context.py` and `apps/api/app/routes/membership_admin.py` import `_set_refresh_cookie` from `app.auth`, but `apps/api/app/auth.py` does not define it. The login route had a local implementation, which did not satisfy those shared imports.

The repaired source in this handoff:

1. Adds the shared `_set_refresh_cookie(response, token)` helper to `apps/api/app/auth.py` with the existing cookie contract: HttpOnly, SameSite=Lax, root path, configured refresh-token max age, and Secure in production.
2. Changes the login/refresh route module to reuse the shared helper rather than maintaining a duplicate local copy.
3. Updates the security contract test to assert the shared helper's location and adds a regression test that verifies all expected imports and cookie attributes in source.

**This repair exists in this local package only. It was not committed or deployed.** The GitHub integration rejected both branch creation and `update_file` with HTTP 403 (`Resource not accessible by integration`). I did not bypass repository permissions or alter Render startup commands to mask the missing import.

## Frontend / Node 24 evidence

The Vercel project configuration reports `nodeVersion: 24.x`. Deployment logs for the pinned SHA record TypeScript completing, successful compilation, static page generation (21/21), and `Build Completed in /vercel/output [19s]`. The Vercel install log says `npm install --include=dev --no-audit --no-fund`, not `npm ci`.

The separate local frontend contract suite passed 25/25 under Node 22.16.0. A clean Node 24 local install/typecheck/test/build could not be run here: the runner only has Node 22, npm access to the Node 24 package and uncached tarballs failed due network/cache restrictions, and Vercel Sandbox creation was rejected with HTTP 402 because the Hobby team's snapshot-storage quota is exceeded until 2026-11-01.

Therefore the deployed Next production build is verified on a project configured for Node 24, but the explicitly requested clean Node 24 `npm ci` + test run is not claimed as complete.

## Why authenticated staging was not run

The Phase 5 Playwright suite is designed to fail closed: it requires an explicit allow-listed staging hostname, a fixture marked `environment: staging`, separate QA storage states, and `LEXA_PHASE5_ALLOW_STAGING_WRITES=1`. The suite creates sales and returns by design.

The available Vercel `LEXA_API_URL` and `NEXT_PUBLIC_API_URL` variables are targeted to `production`; without preview-specific environment variables, the app's API proxy falls back to `https://lexa-n10e.onrender.com`. Testing mutations through that path would write to production. Render's LEXA service has previews disabled and is on the Free plan; Render documentation says Preview Environments require a Pro workspace or higher. Neon branches copy schema and data, so a new branch forked from live should not be treated as scrubbed staging.

No production sales, returns, refunds, or stock movements were generated for acceptance. Once isolated staging is provisioned and the shared cookie repair is committed, run `apps/web/e2e/phase5-sales-acceptance.spec.ts` with a sanitized disposable fixture and separate cashier/manager QA storage states.

## Required gates before Phase 6

1. Restore GitHub write capability for this integration, or apply the included small auth repair overlay to the uploaded source. Confirm the new commit contains the shared helper and regression tests.
2. Verify the Render deployment for that exact new SHA reaches `live`; inspect logs to confirm `app.main` and all routers import; verify `/health` and `/ready`.
3. Configure dedicated Vercel Preview API origins and an isolated Render staging service backed by a sanitized Neon branch/database and non-production Redis. Do not use the live branch for mutating acceptance.
4. Run clean Node 24 `npm ci`, `npm run typecheck`, `npm test`, `npm run build`; run backend tests including Redis-dependent auth refresh; run authenticated Playwright for cashier and manager, multi-line/split payment, partial payment, idempotent replay, stock ledger, cumulative refund cap, branch denial, sale detail/read-after-write, plus returns and reconciliation.
5. Record one exact reviewed SHA for both the Vercel Preview frontend and Render staging backend. Validate that preview environment variables point at staging. Confirm transaction/payment/stock/reporting totals reconcile before promoting.
6. Resolve Neon branch protection's plan quota or have the workspace owner explicitly accept the residual operational risk. RLS and runtime-role audit currently pass; branch protection remains a separate account/plan gate.

## Research notes

- Vercel deploys pushes to the configured production branch to Production; non-production branches receive Preview deployments. The present source extractor pushed the candidate to `main`, which explains why this candidate was deployed to production instead of a preview.
- Render Preview Environments require a Pro workspace or higher.
- Neon branch workflows copy schema and data, so isolated staging requires sanitization or synthetic data.
- Playwright documentation recommends isolated contexts/storage states and warns that authenticated state contains cookies and headers; do not commit QA storage-state files.

## Final disposition

**Vercel frontend build: pass. Neon RLS/runtime access: pass. Live old API readiness: pass. Same-commit Render deployment: fail. Local repair tests: pass. Node 24 clean install and authenticated isolated staging: pending.**

This is not an all-green release and should not be marked Phase 5 complete. Phase 6 stays blocked until the same-source deployment and authenticated staging gates pass.
