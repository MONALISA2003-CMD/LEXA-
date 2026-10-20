# LEXA Deep-Dive Status — 19 October 2026

## Scope and safety

Reviewed only the supplied LEXA source package and connected LEXA GitHub, Neon, Render and Vercel resources. No business records were read, no production data/schema/settings were changed, and no deployment was triggered.

## Source and deployment baseline

- GitHub repository: `MONALISA2003-CMD/LEXA-`
- `main`: `63a62b4fa8b9a4b95431fa9c6c49888b4057c35c` (15 October 2026)
- Render service: LEXA, root `apps/api`, branch `main`; latest listed deployment live from the same commit.
- Vercel project: `lexa`; latest listed production deployment READY from the same commit.
- Prepared source package includes the first-increment dashboard resilience implementation and report; it is not merged/deployed.
- A separate patch file is stale relative to the ZIP and fails `git apply --check` because the package already contains added files and its source has diverged.
- GitHub feature-branch creation returned HTTP 403 `Resource not accessible by integration`. Do not work around this by writing to `main`.

## Tests reproduced locally

- `bash scripts/verify-phase0.sh`: exit 0. 104 passed, 1 skipped, 4 frontend Node contract tests passed; utility syntax/config checks passed. It explicitly prints that full Phase 0 acceptance remains blocked.
- `bash scripts/verify-phase1.sh`: exit 2. Python tests passed (104 passed, 1 skipped), visible product frontend contract passed, then TypeScript contract check failed because real Next.js/React types were unavailable in this environment.
- `python scripts/check_migration_sources.py --strict`: exit 1 due to seven documented missing historical sources.
- `npm ci --no-audit --no-fund --fetch-retries=1 --fetch-timeout=15000` timed out and left incomplete `node_modules`.
- `npm test`: 4 passed, 0 failed.
- `npm run typecheck`: blocked by incomplete dependency install (missing type definition files for `node`, `react`, `react-dom`).
- `npm run build`: could not start because `next` executable was absent.

## Missing migration sources

- `010_phase2_catalog_intelligence`
- `011_phase2_catalog_runtime_constraints`
- `023_phase4_purchasing_core`
- `024_phase4_purchasing_security`
- `025_phase4_purchasing_permissions`
- `026_phase4_membership_branch_integrity`
- `027_release_convergence`

The canonical Neon ledger has 27 rows. The migration checker validates the snapshot against tracked source/gap records; strict mode must stay blocked until exact sources are recovered and reviewed. Do not reconstruct historical migrations from the live schema.

## Neon schema and security observations

- The canonical database contains substantive tables for products, variants/prices, inventory balances and transactions, sales/transaction lines, payments/allocations, journal entries/lines, purchase orders/receipts, tenant memberships, branch assignments and many supporting modules.
- Read-only catalog metadata reported 114 public base tables with RLS enabled and forced; all 114 had at least one policy. Five tables were reported with RLS disabled: `permissions`, `registration_requests`, `schema_migrations`, `tenants`, and `users`. This is an observation, not by itself a vulnerability finding: access grants, intended policy model, and application roles must be evaluated before changing it.
- No row-level business data was queried.

## Render and authentication readiness

- Source `apps/api/app/main.py` implements `/health` as process liveness and `/ready` as readiness requiring database and Redis/cache checks; readiness returns 503 when dependencies fail.
- Package `render.yaml` declares `/ready`; connected live Render service metadata showed blank `healthCheckPath`.
- Historical source report states that on 15 October the live `/ready` payload only reported database readiness, meaning the newer cache-readiness implementation was not deployed at that point. This needs a fresh authenticated/anonymous HTTP probe after the correct deployment is available.
- Public Vercel `/login` returned HTTP 200. Public home HTML renders a session-check state before client resolution; this alone is not proof of an auth defect.
- No dedicated test account was supplied, so login, refresh rotation, `/auth/me`, protected product reads, logout revocation and post-logout token rejection remain unverified.

## Dashboard increment

- Prepared source contains independent loading/success/error state for dashboard panels, avoiding a single `Promise.all` failure blanking all business panels.
- Four static frontend contract tests pass, including the dashboard resilience test.
- This source is not yet on GitHub `main` or deployed. Branch creation is blocked by GitHub integration permission.

## Recommended implementation sequence

1. Restore GitHub feature-branch write permission; keep `main` protected from direct writes.
2. Prepare a clean, dependency-complete Node 24 frontend install; run typecheck, tests, production build and responsive screenshots.
3. Recover the seven historical migration files from authoritative Git history/artifacts and verify exact bytes; keep strict migration replay blocked until then.
4. Reconcile Render's health-check setting with `/ready`, deploy only through an approved preview/release path, then verify `/health` and `/ready` payloads and dependency behavior.
5. Run credentialed acceptance with a dedicated non-production test account: login → session refresh/rotation → authoritative identity → protected product read → logout → refresh and access-token rejection.
6. Validate one end-to-end business workflow: product/price → stock → sale → payment/receipt → accounting/reconciliation, including tenant/branch isolation, idempotency and failure recovery.
7. Promote only after evidence from CI, hosted acceptance and responsive review. Do not change canonical Neon data or schema until historical migration source integrity is resolved.
