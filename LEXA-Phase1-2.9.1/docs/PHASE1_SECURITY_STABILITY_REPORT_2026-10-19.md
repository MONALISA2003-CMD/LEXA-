# LEXA Phase 1 Security and Stability — Implementation Report

**Date:** 19 October 2026  
**Source baseline:** LEXA source package aligned with the `main` release handoff, commit `63a62b4fa8b9a4b95431fa9c6c49888b4057c35c` identified in connected GitHub.  
**Release state:** Source-only candidate; not deployed.

## Summary

Phase 1 implements the source-side security and stability changes that can be safely validated without touching production. It introduces a configurable expected database login role, tighter production DSN checks, consistent transaction-local application-role switching for health checks, a separate least-privilege runtime-role migration, regression tests, and a repeatable local verification script.

## Changes

### Backend

- `apply_application_role()` centralizes the identifier-validated `SET LOCAL ROLE` behavior.
- The SQLAlchemy session hook and direct database readiness check use the same helper.
- Production settings validate `DATABASE_LOGIN_ROLE`, the URL username match, Neon pooled hostname, TLS mode, application role, JWT secret length, and explicit production CORS origins.

### Database

- Added migration `029_phase1_runtime_role_least_privilege.sql`.
- It creates `lexa_runtime_safe` with constrained role attributes, gives it non-inheriting `SET` membership in `lexa_app`, removes direct object grants defensively, and fails closed if administrator membership or direct sensitive-table access remains.
- The migration does not alter the existing `lexa_runtime` role and does not run automatically.
- The migration was executed and verified on an isolated Neon branch. The live branch and production branch were not modified.

### Infrastructure and operations

- Added `DATABASE_LOGIN_ROLE` to `.env.example` and the Render manifest as an explicit configuration field.
- Added `scripts/verify-phase1.sh` and the Phase 1 runbook.
- GitHub branch creation returned HTTP 403 `Resource not accessible by integration`; no GitHub write was attempted after that denial. Render auto-deploys from `main`, so no deploy was triggered.

## Test evidence

- Backend and existing source tests: **109 passed, 1 skipped**.
- Frontend static contract tests: **4 passed**.
- Frontend TypeScript syntax transpilation: **27 files passed** using the globally available TypeScript compiler.
- New Phase 1 security regression tests: **5 passed**.
- Python/shell syntax checks passed.
- Migration source reconciliation reports **7 unresolved historical migration sources** and correctly blocks strict replay.

The skipped test requires the missing `redis` package in this runner. The full frontend install/typecheck/build was not run successfully: `npm ci --offline` failed because `undici-types@6.21.0` was not cached and registry DNS was unavailable. Run the full install/typecheck/test/build in CI or a Node 24 environment with dependencies available.

## Open release gates

1. Run `npm ci`, `npm run typecheck`, `npm test`, and `npm run build` on Node 24.
2. Recover the exact SQL for migrations 010, 011, 023 purchasing-core, 024, 025, 026, and 027 from authoritative history. Do not synthesize them.
3. Set the safe role password through approved secret management and coordinate the Render environment switch only after explicit production authorization.
4. Reconcile Render's live health check (`/ready` is in source; current service setting was observed blank).
5. Complete credentialed hosted auth acceptance using a dedicated test account.
6. Review and disable/remove the old elevated runtime login only after the new role has passed release acceptance.

## Production safety statement

No production database/schema/role, Render environment variable, Render deployment, Vercel deployment, or GitHub branch was changed during this Phase 1 implementation. The only Neon changes occurred on the isolated test branch named in the runbook.
