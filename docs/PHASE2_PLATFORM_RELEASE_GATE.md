# LEXA Phase 2 — Platform Release Gate

Use this checklist for every Phase 2 source package and release. A READY platform state, a passing static test, or a ZIP checksum alone is not a full release certification.

## Source archive completeness

- [ ] Run `python scripts/package_phase2_zip.py --output <path-outside-repo>.zip --increment <NN>`.
- [ ] Confirm the script reports ZIP CRC, exact source-file coverage, per-file byte match, SHA-256 match and secret-environment exclusion as passed.
- [ ] Keep the external `_Manifest.json` next to the ZIP; the archive also contains a per-file internal manifest.
- [ ] Unpack to a clean directory and confirm the project root contains README, app code, migrations, tests, deployment files, CI workflows and scripts.
- [ ] Confirm every ZIP path is repository-root-relative: `apps/web/...`, `apps/api/...`, `.github/...`, `migrations/...`; **no** enclosing `LEXA-Phase1-2.9.1/` directory is allowed.
- [ ] Run a ZIP layout assertion before upload and after extraction; verify the active files changed at exactly the paths Vercel and Render are configured to build from.
- [ ] Compare the deployed Git commit and modified paths with the ZIP manifest; never accept “deployment created” as proof the service consumed the intended source.
- [ ] Treat `.env.example` templates as source files; never package real `.env`, `.env.local`, production secrets, dependency installs, caches or generated builds.

## Local and CI checks

- [ ] Use Node `24.x` for `apps/web`.
- [ ] Run `npm ci --no-audit --no-fund` in `apps/web`.
- [ ] Run `npm run typecheck` in `apps/web`.
- [ ] Run `node --test apps/web/tests/*.test.mjs`.
- [ ] Run `npm run build` in `apps/web`.
- [ ] Run `bash scripts/verify-phase1.sh` and `bash scripts/verify-phase3.sh`.
- [ ] Resolve all failures; do not downgrade or silently skip a failed assertion to make the suite appear green.
- [ ] Test RowMapping (`.mappings()`) and Row serialization wherever shared API serializers accept SQLAlchemy results.
- [ ] Protect `main` with required green build, typecheck, tests and migration-source checks; verify branch rules are effective.
- [ ] Recover exact missing historical migration sources and pass `python scripts/check_migration_sources.py --strict` before a schema release.

## Render

- [ ] Confirm the intended service/repository/branch, exact deploy commit, build and start commands.
- [ ] Confirm Render's hosted health-check setting matches the checked-in blueprint (`/ready` in current source), and inspect it from the service metadata after deployment.
- [ ] Test dashboard/commerce endpoints for HTTP 5xx independently of `/ready`; readiness alone is not functional health.
- [ ] Confirm `/health` returns HTTP 200 and `/ready` reports `status=ready` with both database and cache dependencies `ok`.
- [ ] Inspect deploy logs and recent runtime errors; check authenticated read flows and safe/idempotent write flows in a controlled test workspace.

## Neon

- [ ] Confirm the application points to the expected Neon project, branch and database; do not rely only on a branch name.
- [ ] Verify the required tables, migration ledger, refresh-session lookup function, execution grant and `SECURITY DEFINER` owner/RLS bypass contract using read-only checks.
- [ ] Perform destructive or schema-changing tests only on an isolated branch with explicit approval.
- [ ] Verify auth/session refresh and tenant/RLS behavior end to end using a restricted application role.
- [ ] Confirm runtime login lacks `CREATEDB`, `CREATEROLE`, `REPLICATION` and `BYPASSRLS`; review role membership and credential rollout before promoting the least-privilege migration.
- [ ] Review `registration_requests` (tenant_id exists but current metadata shows RLS disabled and no policies) and document intentional global access or harden it with tested policy behavior.

## Vercel

- [ ] Confirm the deployment is from the intended source commit and Node `24.x` is selected.
- [ ] Require `npm run typecheck` and `npm run build` to pass in the deployment logs.
- [ ] Ensure the build uses changes under active root `apps/web/...`, not a nested copy of the full source folder.
- [ ] Keep `main` unpromotable while the latest Vercel status check is red.
- [ ] Test preview routes, auth redirect, session restore/refresh, API proxy, and browser console errors before production promotion.
- [ ] Confirm the newly successful deployment is the one serving the desired alias; a previously READY deployment does not validate a newer failed build.

## Final release decision

- [ ] Backend, frontend, migration, browser, and platform checks are recorded against the same source commit.
- [ ] Known skips and environmental blockers are named explicitly.
- [ ] No production promotion, Render settings change, or Neon mutation occurs without explicit authorization.

## Dated final audit status — 20 October 2026

See `docs/PHASE0_2_CLOSURE_AUDIT_2026-10-20.md` for the current Increment 06 test counts, migration recovery evidence, hosted probes, database findings and go/no-go criteria. The earlier `docs/PHASE0_2_FINAL_READINESS_AUDIT_2026-10-20.md` preserves the prior audit snapshot. See `docs/PHASE3_ENTRY_CHECKLIST.md` for the Phase 3 entry gate.

Latest Vercel and Render deployments are green on GitHub commit `2cbfda1b24864d7cc03ad2cbb3972639545fe28d`, and read-only `/health`, `/ready`, frontend login, and API-proxy probes pass. This does **not** close release acceptance: GitHub Actions has no run for that commit, root workflow path/branch protection need repair, the runtime DB login remains overprivileged, five public tables have RLS disabled, six exact migration sources remain missing, credentialed hosted E2E is pending, and full local Node 24 build/responsive QA is not recorded. Phase 3 schema-changing work remains **NO-GO** until the required gates in the audit are evidenced.
