# LEXA — Production Hardening v2.8.4

LEXA is a real multi-tenant business operating and intelligence system. The canonical business system of record is Neon PostgreSQL project `LEXA`, branch `lexa-live`, database `neondb`.

## Production hardening carried forward from v2.5.0

This release repairs the production weaknesses identified during the Phase 1 deep review:

- restricted `lexa_app` PostgreSQL role applied per transaction for PgBouncer-safe RLS
- bounded SQLAlchemy connection pooling and PostgreSQL timeouts
- production fail-closed environment validation
- Redis-backed login and registration rate limiting
- HttpOnly refresh-cookie rotation and memory-only access-token handling in the web app
- removal of the open-development workspace bootstrap from the shipped API and browser
- removal of the user-facing Business Engine route module
- production security response headers and generic 5xx browser responses
- migration `022_phase6a_brain_foundation` added to source convergence
- GitHub CI for backend/frontend contract verification
- direct Neon backup script using the unpooled migration/backup connection

## Phase 0 reliability increment

- Cookie refresh is single-flight, sends an explicit empty JSON body, and is accepted by the API even when the body is omitted.
- Protected business requests restore the session before loading; workspace pages are hidden while session verification is unresolved.
- Failure states no longer present dashboard request failures as zero-valued business metrics.
- Vercel runs the standard `npm run build` from `apps/web`; obsolete technical UI routes were removed.

## Canonical deployment

Vercel serves `apps/web`. Render serves `apps/api`. Neon PostgreSQL is the only authoritative LEXA business database. Do not create a second transactional database.

See `docs/MANUAL_DEPLOY_v2.5.0.md` for the exact manual handoff procedure.

## Phase 0 final auth/RLS increment (v2.8.4)

- Cookie refresh now resolves the session through an opaque-token hash lookup, establishes tenant/user context, and rotates under a row lock.
- `/api/v1/auth/me` is the authoritative identity contract used before the web workspace unlocks.
- Protected database requests establish both tenant and user context for branch-aware RLS.
- Migration 028 hardens empty RLS context and assigns a least-privilege Member role only to active memberships that currently have no role. Apply it only after checking the canonical Neon migration ledger.
- Full production build and live auth smoke test remain deployment gates.
