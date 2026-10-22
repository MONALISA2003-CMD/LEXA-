# LEXA v2.8.5 — End-to-end auth readiness and live repair verification

## Production repair completed

Render logs tied the screenshot's session-verification failure to a specific `POST /api/v1/auth/refresh` 500 at `2026-10-13T10:15:30Z`: PostgreSQL reported that `public.lexa_find_session_by_refresh_hash(unknown)` did not exist.

After explicit user approval, migration `028_phase0_auth_rls_runtime_hardening` was promoted to Neon project `LEXA`, branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`. Post-migration checks confirm the ledger row, function, `lexa_app` execute privilege, SECURITY DEFINER, RLS-bypassing owner, zero raw tenant-context predicates and no match for an invalid token. The refresh hash from the previously failed request resolves to one currently valid session through the new lookup function.

## Source package contents

- Fail-closed readiness check for canonical Neon identity, migration 028, function/privileges and owner security properties.
- Migration 028 aligned with the exact policy alterations successfully applied to `lexa-live`.
- Hardened refresh rotation, `/api/v1/auth/me`, tenant/user RLS context, error correlation and cookie forwarding from the previous patch.
- Render source configuration declares `/ready` as a health-check route.
- Added full forensic audit detailing confirmed cause, verification evidence, deployment drift and remaining acceptance checks.

## Tests

- Python: 97 passed, 1 skipped.
- Frontend contract tests: 2 passed.
- Python compilation: passed.
- TypeScript/TSX parse: 26 frontend files, no syntax errors.
- Live DB post-migration checks: passed.
- Full Next.js production build and authenticated browser smoke test: not yet run.

## Important remaining work

The live Render service's actual `healthCheckPath` is blank even though the source `render.yaml` declares `/ready`. GitHub `main` also still has the older health check implementation and a generic policy-rewrite block in migration 028; the corrected source is in this ZIP, but no repository write or deployment was made here. Vercel read-only checks confirm the `lexa-green.vercel.app` alias and latest production deployment are `READY` on the same commit as Render (`fd59d989a8c4ecc3c6a3689dbc2ece315376f34b`); both API-origin variables target `https://lexa-n10e.onrender.com`. Vercel runtime-error reads still returned 403, so no post-fix runtime success record is claimed. Deploy the reviewed ZIP to the LEXA pipeline, reconcile Render's health-check configuration, verify the Vercel deployment and perform an authenticated production smoke test before declaring Phase 0 complete.

No unrelated projects, services or databases were changed.
