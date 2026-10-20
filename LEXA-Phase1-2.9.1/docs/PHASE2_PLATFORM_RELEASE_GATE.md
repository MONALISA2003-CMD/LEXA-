# LEXA Phase 2 — Platform Release Gate

Use this checklist for every Phase 2 source package and release. A READY platform state, a passing static test, or a ZIP checksum alone is not a full release certification.

## Source archive completeness

- [ ] Run `python scripts/package_phase2_zip.py --output <path-outside-repo>.zip --increment <NN>`.
- [ ] Confirm the script reports ZIP CRC, exact source-file coverage, per-file byte match, SHA-256 match and secret-environment exclusion as passed.
- [ ] Keep the external `_Manifest.json` next to the ZIP; the archive also contains a per-file internal manifest.
- [ ] Unpack to a clean directory and confirm the project root contains README, app code, migrations, tests, deployment files, CI workflows and scripts.
- [ ] Treat `.env.example` templates as source files; never package real `.env`, `.env.local`, production secrets, dependency installs, caches or generated builds.

## Local and CI checks

- [ ] Use Node `24.x` for `apps/web`.
- [ ] Run `npm ci --no-audit --no-fund` in `apps/web`.
- [ ] Run `npm run typecheck` in `apps/web`.
- [ ] Run `node --test apps/web/tests/*.test.mjs`.
- [ ] Run `npm run build` in `apps/web`.
- [ ] Run `bash scripts/verify-phase1.sh` and `bash scripts/verify-phase3.sh`.
- [ ] Resolve all failures; do not downgrade or silently skip a failed assertion to make the suite appear green.
- [ ] Recover exact missing historical migration sources and pass `python scripts/check_migration_sources.py --strict` before a schema release.

## Render

- [ ] Confirm the intended service/repository/branch, exact deploy commit, build and start commands.
- [ ] Confirm Render's health-check setting matches the checked-in blueprint (`/ready` in the current source).
- [ ] Confirm `/health` returns HTTP 200 and `/ready` reports `status=ready` with both database and cache dependencies `ok`.
- [ ] Inspect deploy logs and recent runtime errors; check authenticated read flows and safe/idempotent write flows in a controlled test workspace.

## Neon

- [ ] Confirm the application points to the expected Neon project, branch and database; do not rely only on a branch name.
- [ ] Verify the required tables, migration ledger, refresh-session lookup function, execution grant and `SECURITY DEFINER` owner/RLS bypass contract using read-only checks.
- [ ] Perform destructive or schema-changing tests only on an isolated branch with explicit approval.
- [ ] Verify auth/session refresh and tenant/RLS behavior end to end using a restricted application role.

## Vercel

- [ ] Confirm the deployment is from the intended source commit and Node `24.x` is selected.
- [ ] Require `npm run typecheck` and `npm run build` to pass in the deployment logs.
- [ ] Test preview routes, auth redirect, session restore/refresh, API proxy, and browser console errors before production promotion.
- [ ] Confirm the newly successful deployment is the one serving the desired alias; a previously READY deployment does not validate a newer failed build.

## Final release decision

- [ ] Backend, frontend, migration, browser, and platform checks are recorded against the same source commit.
- [ ] Known skips and environmental blockers are named explicitly.
- [ ] No production promotion, Render settings change, or Neon mutation occurs without explicit authorization.
