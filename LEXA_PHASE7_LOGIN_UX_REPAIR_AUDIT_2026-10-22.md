# LEXA Phase 7 Login and UX Repair — Audit Report
**Date:** 22 October 2026  
**Candidate:** Phase 7 login, copy and frontend polish repair  
**Release decision:** **NOT READY FOR PRODUCTION / PHASE 8**

## What was repaired in the candidate source

- Fixed the sign-in query order for the database's existing row-level security rules: the initial user lookup now sets the limited pre-login email context; after password verification, the code sets the user context, clears the pre-login context, and only then looks up available workspaces.
- Added a distinct, friendly response when credentials are valid but the account has no active workspace.
- Added route and source-contract regression tests for sign-in context order and the no-workspace response.
- Replaced the Settings roadmap placeholder with a real business-profile form that loads, validates, saves and refreshes saved details.
- Replaced the Business insights placeholder with real monthly sales figures, inventory indicators and advisory restock suggestions, with partial-load, error and empty states.
- Simplified visible wording across Settings, navigation, reporting, inventory, compliance and purchasing. Removed explicit phase labels and the stale app-version display from the active interface.
- Updated relevant frontend contract assertions to match the customer-facing wording.

**Important:** these changes exist in this candidate package only. They have not been published to the live website or API.

## Checks completed against the candidate

| Check | Result |
|---|---|
| Backend tests (`python -m pytest -q tests apps/api/tests`) | **219 passed** |
| Backend compile check | **Passed** |
| Frontend contract tests (`node --test apps/web/tests/*.test.mjs`) | **43 passed, 0 failed** |
| Frontend action/destination audit | **Passed:** 28 TS/TSX files, 157 button-like controls, 36 forms, 42 links |
| TypeScript syntax parse of modified pages and API module | **Passed** for 11 modified TS/TSX files |
| Migration recovery manifest/checksums | **Passed** |
| Strict migration source reconciliation | **Passed with approved historical replacement dispositions**; exact historical byte parity is not claimed |
| Migration clean-replay plan-only check | **Passed:** 43 SQL inputs present and hashed; no database connected and no SQL executed by this local check |
| Full web typecheck | **Blocked / not validated:** `npm run typecheck` reports missing React/Next modules and JSX types because the local dependency installation is incomplete; these errors do not prove the candidate itself typechecks |
| Full web production build | **Blocked:** `npm run build` exits because the `next` executable is unavailable in this environment |
| Authenticated Phase 7 browser end-to-end tests | **Not run:** no isolated staging API, staging cache and QA browser session/fixture are available |

The local backend suite reports one Starlette cookie deprecation warning. In this offline environment, the new mocked route test provides import-only fallbacks only when runtime packages (Redis, pwdlib, or psycopg) are missing; the connected CI must install the full API test dependencies and run against the real packages.

## Confirmed live state (read-only inspection)

- Live Vercel frontend is READY on commit `9476c09ce4ee736f56b4ca07f073ee4b853b1c08`.
- Live Render API is deployed on commit `311c9b73e42042956abc148cc7e40a80c93c503`. The SHAs differ; this has not yet been signed off as a matched release pair.
- Live API `/health` and `/ready` responded successfully when checked; `/ready` reported database and cache healthy. The Render service's configured health-check path is still blank.
- Vercel's aggregate runtime-error view reported no runtime errors for the last 24 hours. This is not proof that every request or sign-in succeeds.
- The affected sign-in account exists and has an active membership/workspace in production. Read-only database checks reproduced the bug: the workspace lookup returns no rows before `app.user_id` is set, and returns the active workspace when that transaction-local context is set. Source inspection additionally confirmed that the initial user read needs the limited pre-login email context required by the existing RLS policy.
- Production database remains unchanged at `031_phase3_auth_surface_rls`; **zero Phase 7 tables are present in production**.
- The separate replay database remains at `039_phase7_supplier_ledger_landed_costs`, with 126 public tables, all 126 under forced row-level security, 134 policies, and seven Phase 7 tables present.

## Blockers to a green release

1. **Source publishing is blocked:** the connected GitHub integration rejects branch creation with HTTP 403 `Resource not accessible by integration`. No candidate commit has been pushed; the current production code still has the reported login defect.
2. **Isolated staging API is not ready:** Render has only one Free Key Value/Redis instance, `lexa-redis`, already used by production. Creating a second Free instance was rejected by the account limit. Staging has not been pointed at production Redis and no paid resource was created.
3. **Staging tests cannot run yet:** no isolated Render staging API, separate cache, QA-only authenticated browser state or disposable tenant fixture is available. Phase 7 authenticated E2E is still a release gate.
4. **Web production build/typecheck must run in Node 24 with the project's pinned dependencies.** The local environment has Node 22 and incomplete offline npm cache; syntax checks and source tests do not substitute for the official build.
5. **Render health monitoring:** `/ready` works, but the service health-check path is unconfigured and could not be changed with the available Render actions.
6. **Recurring backups:** one selective recovery copy and a manual snapshot exist, but recurring backups are not configured. Neon reported that automatic snapshot scheduling is not enabled for this project. The selective copy intentionally omitted 57 ephemeral rows (38 sessions, 16 outbox events, 3 idempotency records); it is not a byte-identical clone.
7. **Production Phase 7 migrations:** do not apply migrations 033–039 until the staging test gate passes, restore readiness is proven, and the production migration/rollback plan is approved.

## Phase 8 decision

**Do not mark Phase 7 green and do not begin Phase 8 yet.** First publish the candidate on an isolated release branch, complete a clean Node 24 install/typecheck/build, deploy a separate API with separate cache and the replay database, run the authenticated Phase 7 end-to-end and tenant-isolation tests, configure monitoring/backups, then review the production migration plan. Keep production database unchanged until those gates pass.


---

# LEXA Phase 7 — release gate status
**Checked:** 22 October 2026 (UTC)

## Completed and independently checked
- Candidate backend test suite: **219 passed**; one Starlette deprecation warning.
- Candidate frontend contract suite: **43 passed, 0 failed**.
- Python compile check: **passed**.
- Candidate sign-in code contract: pre-login email context is set before the user lookup; verified user context is set before the workspace lookup; no-workspace responses are distinct.
- Phase 7 replay database: latest migration `039_phase7_supplier_ledger_landed_costs`; 126 public tables; 126 tables with forced RLS; 134 policies; 478 indexes; seven Phase 7 tables present.
- Production database safety check: latest migration remains `031_phase3_auth_surface_rls`; zero Phase 7 migration rows. No production migrations were applied.
- Existing live API `/health` and `/ready` were previously observed returning 200; readiness reported database and cache healthy.

## Not complete — blockers
1. **Candidate is not published to the repository branch visible to deployment tools.** The current `main` login route still has the earlier implementation. GitHub branch creation returns HTTP 403 `Resource not accessible by integration`; current `.github/workflows/lexa-ci.yml` path is absent.
2. **No isolated staging API has been deployed.** The only existing Render Key Value instance is production's cache. Creating a second free instance was refused by account limits. Creating a dedicated paid 256 MB instance was refused with HTTP 402 because billing information is required; no paid resource was created.
3. **Authenticated Phase 7 browser tests have not run.** No isolated running API/cache plus staging-only authenticated browser state and disposable fixture currently exists. Unit/source checks are not substitutes for those tests.
4. **Candidate frontend typecheck and production build have not been validated.** The local environment has Node 22, while the project targets Node 24. `npm ci` did not complete in this environment. The current production Vercel build success is for the older deployed source, not this candidate.
5. **Render health monitoring is still not enabled on the live service.** `/ready` exists and returned 200, but the service's configured health-check path is blank and the connected Render tool does not expose a service-settings update action.
6. **Recurring backups remain disabled.** Neon rejected the snapshot-schedule request because automatic scheduling is not enabled for the project; its documented schedule API requires a paid plan. One manual selective recovery copy/snapshot exists, with 57 ephemeral rows deliberately excluded; it is not a complete native clone or an automatic backup schedule.
7. **Frontend/backend release gate remains open.** Current frontend and backend are on different commit SHAs, although the latest frontend-only commit appears workflow-related. The new repair candidate has not been deployed as an approved matched pair.

## Decision
**NO-GO for Phase 8.** Do not apply Phase 7 migrations to production until the candidate is published, a dedicated staging cache and API are available, the Node 24 build passes, authenticated supplier/payment/ledger/landed-cost/permissions/tenant-isolation tests pass, and backup/rollback readiness is confirmed.
