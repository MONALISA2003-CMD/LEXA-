# Phase 7 release unblock checklist (22 October 2026)

This note explains the exact external actions that remain blocked by connector permissions or platform configuration; it is not a production migration authorization.

## 1. Restore CI on GitHub

The currently observed `main` tree at `b920c8719079741ed3c2fb2288de67c7de8a0d37` has no `.github/workflows/lexa-ci.yml`. GitHub Actions only showed the ZIP-extractor workflow for the upload. A write attempt to add the CI workflow returned HTTP 403 `Resource not accessible by integration`. The workflow file is in this archive under `.github/workflows/lexa-ci.yml`; the ZIP extractor appears to protect `.github/workflows/` from replacement, so re-uploading the ZIP alone does not install that workflow.

A repository maintainer with repository write/workflow permission must restore the workflow through the GitHub UI or an authorized git push. Verify the file is present in the commit, then ensure GitHub Actions runs that commit. Required gates include Node 24 `npm ci`, typecheck, frontend contracts/build, full backend tests with Redis (no dependency skip), actual clean disposable PostgreSQL replay/evidence, tenant/branch authorization tests, and source integrity checks. Do not dispatch or mark CI successful based on the extractor job.

## 2. Publish the Increment 03 API fix

`apps/api/app/routes/purchasing.py` contained duplicate Pydantic methods named `validate_allocations`; the active class method also called a shared rule that was not imported. Render emitted the duplicate-validator warning on consecutive deployments. Increment 03 fixes the import and keeps a single validator; regression tests cover valid, duplicate-bill, and over-allocation cases. The fix is not in current GitHub `main` or the current Render deployment. Commit this archive through an authorized source path and deploy only after exact-SHA CI passes.

## 3. Render

Current Render live SHA: `dd4069109d5c94143f5c5e28e758128b90dee55a`. Vercel frontend SHA: `b920c8719079741ed3c2fb2288de67c7de8a0d37`. They do not match. Render's connected service has an empty health-check path while `render.yaml` has `/ready`; update Settings → Health Check to `/ready` or sync the approved Blueprint, then confirm `/ready` is 2xx and the deployment metadata matches the approved SHA. Render documentation describes HTTP health checks and permits configuring this path in the dashboard or Blueprint: https://render.com/docs/health-checks .

Do not point a staging service at `lexa-live` or production secrets. A separate staging service and temporary DB/Redis credentials require approved secret setup; the connected create-service path was blocked and the account's only Free Redis instance is already in use.

## 4. Neon database, backup, and restore

The service configuration points at project `wispy-mud-75323042`, branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`. Read-only inspection found 31 migration rows through 031 and none of the six Phase 7 supplier-finance tables. Do not run migrations 033–039 yet.

The project currently has no snapshots or snapshot schedule in the connected API. Direct snapshot creation on the application branch fails with `not allowed to snapshot non-root branch`; creating another canonical branch fails at the current branch limit. The fastest safe route is to run a `pg_dump`/restore rehearsal through an owner-controlled secure operations runner using the actual application branch's DATABASE_URL, save an encrypted backup outside the database project, checksum it, and restore to an independent disposable database. Never paste connection strings, passwords, auth cookies or storage-state JSON into the repository or reports. After restore is demonstrated, configure the paid/available backup option appropriate to the canonical branch and capture the settings. A root-branch snapshot alone is not proof of a backup for `lexa-live`.

Neon official references: branch behavior https://neon.com/docs/manage/branches ; snapshot API https://api-docs.neon.tech/reference/createsnapshot .

## 5. Rollback and rollout gates

Migration 039 is forward-oriented and includes backfills/constraints/indexes; do not assume a destructive `down` migration will restore original data. Before application: archive the exact starting migration ledger/schema; measure lock and duration behavior on representative restored data; verify backup integrity and a restore drill; use `lock_timeout`/`statement_timeout` appropriate to the reviewed window; stage and verify the migration; prepare a tested forward-fix and application rollback plan; set a maintenance/stop condition; require an explicitly approved rollout window. Never apply migration 039 on a branch merely to make the version count look correct.

## 6. Authenticated staging E2E

Configure a non-production HTTPS frontend/API pair, a disposable tenant fixture and reset/cleanup strategy, separate auth state, and explicit host allow-list. Keep the workflow's E2E input false until these exist. Then run the real Phase 7 purchasing acceptance journey (supplier → purchase order → partial receipt → landed-cost allocation → supplier return → bill-match exception/review → payment allocation/balance) and retain its report. No real supplier, stock or financial records should be touched in this test.

## Production decision

Do not release until exact-commit CI, real replay, authenticated isolated staging E2E, Render/Vercel parity, backup/restore, rollback plan, and explicit approval all pass. No production migration or deployment change was performed by the Increment 03 repair pass.
