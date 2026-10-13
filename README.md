# LEXA — Production Hardening v2.8.5

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

## Phase 0 final auth/RLS increment (v2.8.5)

- Cookie refresh now resolves the session through an opaque-token hash lookup, establishes tenant/user context, and rotates under a row lock.
- `/api/v1/auth/me` is the authoritative identity contract used before the web workspace unlocks.
- Protected database requests establish both tenant and user context for branch-aware RLS.
- Migration 028 hardens empty RLS context and assigns a least-privilege Member role only to active memberships that currently have no role. Apply it only after checking the canonical Neon migration ledger.
- Readiness in this source package verifies migration 028 and its SECURITY DEFINER refresh lookup before reporting healthy.
- Migration 028 was promoted to canonical Neon branch `lexa-live` after explicit approval. The live ledger row, lookup function, `lexa_app` grant, SECURITY DEFINER/RLS owner properties, and safe tenant policy expressions were verified after promotion.
- Render logs confirmed the screenshot path: `/api/v1/auth/refresh` returned 500 because the lookup function was missing before migration 028. The previously failed refresh hash now resolves to one unrevoked, unexpired session through the new function.
- Full browser/API acceptance is still pending. Render’s live `healthCheckPath` is blank while `render.yaml` declares `/ready`, and GitHub `main` still has the older health-readiness check. The Vercel `lexa-green.vercel.app` production deployment and both API-origin variables match the Render API and same commit, but the newly added readiness guard is not yet deployed. No repo write or application deployment was performed here; deploy this reviewed ZIP and verify the live browser/API flow before declaring Phase 0 complete.
- See `LEXA_E2E_FORENSIC_AUDIT_2026-10-13.md` for the full evidence trail and exact acceptance checklist.
