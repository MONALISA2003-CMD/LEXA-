# LEXA — Production Hardening v2.8.7 Phase 0 Handoff

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


## Phase 0 reliability handoff (15 October 2026)

This package includes additional source-side hardening and release gates:

- Corrected the dynamic Brain RLS policy SQL in migration 022 using `format(%I, %L)` and verified the generated policy expressions on a disposable Neon validation branch.
- Added refreshed read-only canonical Neon ledger evidence dated 15 October 2026 and an explicit manifest of unrecovered historical migration SQL sources.
- Added `scripts/check_migration_sources.py`; normal mode ensures all gaps remain documented, while `--strict` fails until the exact migration sources are recovered.
- Corrected deployment documentation to treat `/health` as liveness and `/ready` as dependency-aware database/cache readiness. The readiness check now verifies Redis/Valkey using bounded timeouts.
- Recovered `019_phase4a_customer_credit_allocation.sql` byte-for-byte from historical GitHub commit `d850ce04c8930134f01a63cd65c5d1947a17b17d` (verified Git blob SHA documented in `migrations/SOURCE_RECOVERY.md`).
- Added `scripts/smoke_phase0.py` for public liveness/readiness/bodyless-auth probes and optional credentialed login/refresh/me/protected-read/logout acceptance.
- Added `pytest.ini` to exclude archived package copies from canonical test collection, fixed API test import paths, and separated the strict migration replay gate from ordinary code CI.
- Added `scripts/apply-deletion-manifest.sh` and marked the obsolete unregistered backend Business Engine route module for removal from existing checkouts.
- Added a complete `apps/web/package-lock.json` and changed CI to use `npm ci` for deterministic frontend dependency installation.
- Aligned `render.yaml`'s blueprint service name to the existing Render service `LEXA` so this package does not imply creating a second `lexa-api` service. The blueprint declares `/ready`; the live Render service setting still needs reconciliation.

**This is not a claim that Phase 0 is fully accepted.** Current local checks report 104 passed and 1 skipped (the local offline environment lacks the `redis` dependency); frontend contract tests pass. A disposable-branch SQL check confirms the corrected Brain policy block compiles. On 15 October, live Render `/health` returned 200, `/ready` returned 200 with the older database-only payload, bodyless refresh returned 401 instead of 422 on retry, and anonymous logout returned 200. Seven applied migration SQL sources remain absent from the inspected repository history: 010, 011, 023 purchasing core, 024 purchasing security, 025 purchasing permissions, 026 membership/branch integrity, and 027 release convergence. Their SQL was not reconstructed from schema inference. The strict migration source check intentionally remains blocked until authoritative source files are recovered. GitHub branch creation was denied, so this is a local source package rather than a pushed commit. Live Render still returns the older readiness payload (database only), the live health-check path is blank, and credentialed browser sign-in/refresh/logout acceptance remains pending.


For execution order and dedicated-account smoke acceptance, see `docs/PHASE0_RUNBOOK.md`. The current detailed acceptance status is `docs/PHASE0_IMPLEMENTATION_REPORT.md`.
