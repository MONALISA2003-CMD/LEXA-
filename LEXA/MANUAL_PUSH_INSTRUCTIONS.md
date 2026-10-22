# LEXA Phase 7 candidate — safe publication runbook
**Updated:** 2026-10-22 UTC

## Important package layout
This handoff ZIP has two layers: root-level handoff documents, and the actual project tree under `source/`. Do not upload or extract the whole handoff archive straight into the repository root. That would leave the repair under `source/apps/...`, while deployment uses the top-level application paths.

## Publish only after GitHub write access is restored
1. Create a dedicated release branch from the latest `main`; do not push candidate code directly to `main`. The connected GitHub integration returned HTTP 403 when branch creation was attempted.
2. Extract the ZIP to a temporary folder. On the release branch, review and copy the **contents of `source/`** into the repository root so `apps/api`, `apps/web`, and `.github/workflows/lexa-ci.yml` land at their intended top-level paths. Do not copy the outer handoff documents into the application tree as source code.
3. Carefully review the `DELETE.txt` manifest before staging any listed removals. Keep local `.env` files, credentials, database dumps, and the handoff ZIP out of Git.
4. Inspect `git status --short` and the complete diff. Do not use `git add -A` blindly. Run `git diff --check`, install API development dependencies, run the full Python suite, and run the frontend tests. On Node `24.x`, run `npm ci`, `npm run typecheck`, and `npm run build` from `apps/web`.
5. Open a pull request and merge only after CI and code review pass. Render auto-deploys from `main`, so merging can trigger a live API deployment. Verify frontend and backend correspond to the reviewed release and are healthy before calling it released.

## Database and staging safety
- Do not apply Phase 7 migrations to production as part of source publication. Production was checked at migration `031_phase3_auth_surface_rls` with zero Phase 7 migration rows.
- First use isolated replay/staging. Authenticated supplier, bill, payment, ledger, landed-cost, permissions, and tenant-isolation tests must pass before any production migration approval.
- Never share the production Redis/cache with staging. Paid cache, automatic backup scheduling, and any other billing-dependent infrastructure remain deferred until the final production phase.
- Set Render's health-check path to `/ready` in service settings; the current service setting is blank. Confirm `/ready`, login, refresh, protected routes, and logout after deployment.

## Current release gate
The candidate code tests passed in this environment (219 Python tests and 43 frontend contracts), but the Node 24 typecheck/production build and authenticated staging end-to-end gate are not complete. Current status and deployment SHAs are documented in `FINAL_RELEASE_GATE_STATUS.md` at the handoff ZIP root.
