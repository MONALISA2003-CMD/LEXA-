# LEXA — Infrastructure and Phase Status

**Audit date:** 19 October 2026  
**Scope:** LEXA only  
**Production changes made during this audit:** None

## Executive status

LEXA is at the **Phase 1 UX foundation** source baseline. The supplied first-increment source package includes a Command Centre resilience change, and its available local regression tests pass. That increment is **not on GitHub `main`** and is not deployed. Production acceptance remains blocked by access/readiness validation, incomplete frontend build evidence, and seven missing historical migration SQL source files.

## Resource inventory

| System | Existing LEXA resource | Observed state |
|---|---|---|
| GitHub | `MONALISA2003-CMD/LEXA-`, default branch `main` | Latest commit `63a62b4fa8b9a4b95431fa9c6c49888b4057c35c` (15 Oct 2026). [Commit](https://github.com/MONALISA2003-CMD/LEXA-/commit/63a62b4fa8b9a4b95431fa9c6c49888b4057c35c) |
| Neon | Project `LEXA` (`wispy-mud-75323042`), branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb` | Branch `ready` and marked default. Read-only query returned 27 migration-ledger versions, through `028_phase0_auth_rls_runtime_hardening`. No SQL changes made. |
| Render | Service `LEXA` (`srv-dakm8k95efls73egg9a0`) | Repo `MONALISA2003-CMD/LEXA-`, branch `main`, root `apps/api`, auto-deploy on, region Frankfurt, service URL `https://lexa-n10e.onrender.com`. Latest deployment is `live` on commit `63a62b4`, deployed 15 Oct. [Service dashboard](https://dashboard.render.com/web/srv-dakm8k95efls73egg9a0) |
| Vercel | Project `lexa` (`prj_QicfCnse8LU6hnq4ik9liHc289VW`) | Latest listed production deployment is `READY`, built from commit `63a62b4`. Domain alias includes `https://lexa-green.vercel.app`. No deployment was triggered by this audit. |

## Phase and evidence

### Completed source-level evidence

- The supplied ZIP already contains the first-increment change: Command Centre resources have independent loading/success/error states so a failed API request does not blank unrelated panels.
- `bash scripts/verify-phase0.sh`: **104 passed, 1 skipped, 4 frontend Node contract tests passed**.
- The skipped Python test needs the local `redis` package, which is not installed in this execution environment.
- A read-only Neon query confirmed all 27 migration versions in the canonical branch ledger, including the seven versions whose exact SQL source files remain missing from the reviewed source package.
- The latest Vercel production deployment and latest Render live deployment both reference commit `63a62b4`.

### Still not verified

- GitHub `main` still contains the former single `loadError` Command Centre path. The first-increment files are absent from GitHub `main`.
- GitHub branch creation was rejected with `403 Resource not accessible by integration`, despite repository metadata reporting push permission. No branch, commit, or pull request was created. No direct-to-`main` workaround was attempted.
- The most recent visible GitHub Actions runs are **LEXA ZIP Extractor** runs; the latest one shown is for `fcd39b2`, not `63a62b4`. The latest commit's combined status reports a Vercel success context, not application test results.
- Render's live `healthCheckPath` is blank, while `render.yaml` declares `/ready`. The deployed source exposes `/health` for liveness and `/ready` for dependency-aware readiness, including the Redis-compatible cache check. The live response could not be probed from this execution environment because outbound DNS resolution failed; this does **not** establish that the public service itself is down.
- Frontend dependency installation, TypeScript typecheck, production build, responsive visual review at 360/390/430/768/1280 CSS pixels, and credentialed hosted auth acceptance are still pending. The local runtime is Node 22.16.0 while the Vercel project specifies Node 24.x; dependencies are not installed here.
- Strict migration source verification exits nonzero until exact historical SQL is recovered for these seven ledger entries: `010_phase2_catalog_intelligence`, `011_phase2_catalog_runtime_constraints`, `023_phase4_purchasing_core`, `024_phase4_purchasing_security`, `025_phase4_purchasing_permissions`, `026_phase4_membership_branch_integrity`, and `027_release_convergence`. Their SQL must not be inferred or reconstructed from the current schema.
- No open pull request was returned by the scoped GitHub query.

## Recommended next sequence

1. Restore GitHub integration write access to create a feature branch and commit the supplied first increment. Keep `main` and production untouched until review and tests pass.
2. Run `npm ci`, typecheck, frontend contract tests, and `next build` using Node 24.x; verify a preview deployment against the new branch.
3. Reconcile Render's live health-check path with the readiness contract after checking the actual live endpoint and required cache environment.
4. Recover the seven historical migration sources from authoritative Git history/release artifacts. Do not perform strict migration replay or production schema changes until the source gaps are resolved.
5. Run hosted auth acceptance with a dedicated test account and complete the real Product → stock/location → sale → payment/receipt → accounting/report workflow, including tenant/branch, permission, retry, and reconciliation tests.
6. Record responsive visual review and hosted smoke evidence before describing the increment as production verified.

## Change log for this audit

- Read-only GitHub, Neon, Render, and Vercel inspection performed.
- Read-only SQL query against `public.schema_migrations` on Neon `lexa-live` / `neondb` performed.
- Source-package local verification run.
- **No production database changes, environment changes, service-setting changes, commits, pushes, or deployments were made.**
