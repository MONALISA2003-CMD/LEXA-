# LEXA v2.8.7 — Phase 0 reliability handoff (15 October 2026)

## Source-package changes

- Corrected migration 022 Brain RLS policy SQL by using PostgreSQL `format(%I, %L)` for identifiers and string literals. This avoids nested quote ambiguity.
- Verified the exact corrected `DO` policy-creation block against the seven existing Brain tables on the disposable `lexa-convergence-test-2026-10-08` Neon validation branch. Re-read `pg_policies` and confirmed each policy contains `NULLIF(current_setting('app.tenant_id', true), '')::uuid`. No SQL was run on canonical `lexa-live` during this validation.
- Re-queried canonical Neon `public.schema_migrations` on 15 October: 27 rows observed. Migration 028, the refresh lookup function, `lexa_app` EXECUTE grant, and a SECURITY DEFINER owner with RLS bypass are present.
- Kept the seven unavailable applied SQL sources as explicit blockers; no inferred migration SQL was fabricated.
- Added a standard-library Phase 0 HTTP smoke runner, including an optional credentialed login → cookie rotation → `/auth/me` → protected catalog read → logout/revocation journey.
- Fixed test discovery paths, added `pytest.ini` to exclude archived snapshots from routine collection, and made ordinary CI run only the canonical test suites. Exact migration replay is now a manual release gate so routine code CI is not permanently red while historical sources are missing.
- Added an explicit deletion-manifest applier and listed the obsolete, unregistered `apps/api/app/routes/business_engine.py` module for removal in existing checkouts.
- Updated the ledger snapshot to 15 October and added tests for the smoke runner contract.

## Verification

- Local Python suite: **104 passed, 1 skipped**. The only skip is the API refresh module because this offline container lacks the `redis` Python package; the checked-in CI installs `apps/api[dev]`, including runtime dependencies.
- Python compile check: passed.
- Frontend contract tests: **2 passed, 0 failed**.
- Migration checker normal mode: passed with **7 documented source gaps**; `--strict` correctly remains blocked.
- `apps/web/package-lock.json`: 34,536 bytes, lockfile v3, 62 package entries; root dependencies/devDependencies match `package.json`.
- A separate Vercel sandbox run using the same frontend source completed `npm ci`, `npm run typecheck`, `npm test`, and `npm run build` successfully.
- Live probes on 15 October: Render `/health` 200; `/ready` 200 but its response still reports only `dependencies.database`; the first bodyless `/api/v1/auth/refresh` probe timed out at 30 seconds; after warm-up, a retry returned 401 (not 422) in 0.316 seconds; anonymous `/api/v1/auth/logout` returned 200. The Vercel login page was previously observed at HTTP 200.

## Outstanding production gates

This is a reviewed ZIP handoff, not a pushed or production-accepted release. GitHub branch creation remains denied with HTTP 403. The connected Render service's live `healthCheckPath` is blank, and its running `/ready` handler has not yet been updated to report the cache dependency. The current connector does not expose a direct health-check setting update. No production deployment was triggered.

The complete credentialed browser/API journey has not been run because no dedicated test-account credentials were supplied. Run `python scripts/smoke_phase0.py` first for anonymous probes, then provide `LEXA_SMOKE_EMAIL`, `LEXA_SMOKE_PASSWORD`, and (if needed) `LEXA_SMOKE_TENANT_ID` for the dedicated test account.

The exact historical SQL files for versions 010, 011, 023 purchasing core, 024 purchasing security, 025 purchasing permissions, 026 membership/branch integrity, and 027 release convergence remain missing. Full fresh-database replay is not proven and must not be attempted against production until these are recovered from authoritative artifacts.
