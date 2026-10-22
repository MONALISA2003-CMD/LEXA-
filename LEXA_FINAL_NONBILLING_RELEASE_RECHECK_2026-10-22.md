# LEXA Phase 7 — current non-billing release recheck
**Checked:** 22 October 2026 (UTC)

## Verified in this recheck

### Candidate source checks
- Backend and repository Python tests: **219 passed, 1 warning** (`PYTHONPATH=apps/api pytest -q`).
- Frontend contract tests: **43 passed, 0 failed** (`npm test`).
- Python source compilation: **passed** (`python -m compileall -q apps/api/app`).
- Frontend typecheck: **not passed in this environment**. TypeScript reports missing `node`, `react`, and `react-dom` type definition files (`TS2688`).
- Dependency repair/build: **blocked locally**. Offline `npm ci` cannot fetch uncached `undici-types@6.21.0` (`ENOTCACHED`); the local runtime is Node `22.16.0`, while the frontend package requires Node `24.x`. A clean Node 24 typecheck and production build remain open.

These are candidate-source tests, not a claim that the candidate is deployed or that authenticated end-to-end tests passed.

### Database safety and replay
- Production branch `br-soft-star-b1dj2m2w`, database `neondb`: latest migration **`031_phase3_auth_surface_rls`**; current query found **zero** schema-migration rows matching Phase 7 migration numbering (`032`–`039`). No production migrations were applied during this work.
- Isolated replay branch `br-jolly-mode-b966dwys`, database `lexa_replay_ci`: latest migration **`039_phase7_supplier_ledger_landed_costs`**; **126** public tables, **126** with forced row-level security, **134** policies, **478** indexes, and all seven Phase 7 purchasing/supplier tables are present.
- Existing one-time selective backup/snapshot remains the only checked recovery copy. It intentionally omitted 57 ephemeral rows and is not a native full clone or recurring backup.

### Repository and deployment state
- GitHub `main` HEAD checked: `e87754837107adb5fa001830b959d5a978024826`. The latest commit added/updated handoff documentation; it did **not** promote the candidate source into the top-level deployed paths.
- The candidate repair file is present under the nested path `source/apps/api/app/routes/auth.py`; the top-level `apps/api/app/routes/auth.py` differs. The Render API service is configured with root directory `apps/api`, so the nested `source/` copy is not the deployed API path.
- Latest Render deploy record: commit `311c9b73e42042956abc148cc7e40a80c93c503`, status `live`.
- Latest Vercel production deployment record: state `READY`, commit `e87754837107adb5fa001830b959d5a978024826`. That GitHub commit is documentation-only relative to the candidate source repair.
- A fresh GitHub branch-create attempt returned HTTP `403 Resource not accessible by integration`. The candidate still cannot be published into a proper release branch through this connection. No direct push to `main` was attempted.
- The Render service health-check path remains blank. `/health` and `/ready` had previously been observed returning 200, but a fresh endpoint response was not independently confirmed in this recheck.

## Work intentionally on hold for the final production phase
- Paid isolated staging cache, if the free allowance cannot support it.
- Paid/automatic Neon backup scheduling and other billing-dependent backup features.
- Any other paid staging/production capacity.

No paid resource was created or enabled. Staging must not share the production Redis/cache.

## Release decision
**NO-GO for Phase 8 / production migration.** Keep production at migration `031` until the candidate is properly published to a release branch, Node 24 typecheck/build pass, an isolated staging API and separate cache are available, authenticated supplier bill/payment/ledger/landed-cost/permission/workspace-isolation tests pass, frontend and backend are approved as one matched release, health monitoring is configured, and backup/rollback readiness is confirmed.

## Safe next steps requiring no billing
1. Restore GitHub integration write permission or manually publish the source into a dedicated release branch and open a pull request. Do not place the candidate only beneath `source/`, and do not push the candidate directly to `main`.
2. Run the official Node 24 install, typecheck, build, and CI checks once a network-enabled runner is available.
3. Deploy and verify an isolated, non-production API with staging-only credentials. The separate cache and any paid backup configuration remain deferred until the final production phase.
4. Run authenticated Phase 7 end-to-end coverage and complete the release/rollback review before any production migration approval.
