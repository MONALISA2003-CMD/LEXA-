# LEXA v2.5.0 — Production Hardening & Convergence

This release hardens the existing LEXA Phase 5 foundation for controlled production deployment and repairs source/runtime drift identified during the Phase 1 deep review.

## Security and runtime

- Removed the user-facing Business Engine route module.
- Removed the open-development `/api/v1/auth/dev-session` path from the production package.
- Removed browser `sessionStorage` persistence of access tokens.
- Added HttpOnly refresh-cookie rotation with Secure/SameSite protection in production.
- Added Redis-backed login and registration rate limits.
- Added production fail-closed configuration validation.
- Applied the restricted `lexa_app` PostgreSQL role per transaction with `SET LOCAL ROLE` for PgBouncer transaction pooling.
- Added bounded SQLAlchemy connection pooling, statement timeout, lock timeout and idle-transaction timeout.
- Added security response headers and generic 5xx responses.

## Source/deployment convergence

- Added migration `022_phase6a_brain_foundation`, reconstructed from the verified canonical Neon schema.
- Added production-oriented `render.yaml` configuration, including direct migration URL support.
- Added GitHub CI for the backend suite, backend compilation, frontend typecheck and customer-facing contract tests.
- Added `scripts/backup-neon.sh` using the direct Neon connection endpoint.
- Retired deployment-repair logic that could reintroduce obsolete Business Engine/open-development behavior.

## Verification

Fresh final verification produced 94/94 passing Python tests, frontend contract tests passing, backend compilation passing, and TypeScript contract compilation passing.

## Operational limitation

The connected Neon free plan does not permit automatic snapshot schedules for this non-root branch, so this package provides a direct `pg_dump` backup script as an operational fallback. This does not replace a plan-level point-in-time recovery policy.
