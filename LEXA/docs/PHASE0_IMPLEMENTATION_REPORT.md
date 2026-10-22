> **Historical snapshot — superseded for current gate status by Phase 6 (21 October 2026).** Any statement here that requires recovering the six Phase 3-approved lost SQL files is retained only to describe the state at the time. Their historical recovery gate is permanently closed by `docs/decisions/ADR-DB-001-permanent-replacement-of-lost-migrations.md` and `migrations/migration_dispositions.json`. Do not treat this snapshot as the current release-gate register.

# Phase 0 implementation report — updated 15 October 2026

## Implemented in this source package

1. Fixed `migrations/022_phase6a_brain_foundation.sql` so generated policy SQL quotes tenant setting/empty-string literals with PostgreSQL `format(%L)` and policy identifiers with `%I`.
2. Executed the corrected policy-creation `DO` block against seven existing Brain tables on the disposable Neon validation branch `lexa-convergence-test-2026-10-08`; a follow-up read confirmed the generated policies contain the correct `NULLIF(current_setting('app.tenant_id', true), '')::uuid` predicate. Canonical `lexa-live` was not modified by that test.
3. Added `check_redis()` with bounded connect/read timeouts and sanitized logging. `/ready` reports ready only when canonical database/schema/auth readiness and Redis/Valkey are both healthy; `/health` stays dependency-independent process liveness.
4. Re-queried the canonical Neon ledger on 15 October 2026. It still contains 27 rows; migration 028, `public.lexa_find_session_by_refresh_hash(text)`, `lexa_app` EXECUTE privilege, and a SECURITY DEFINER owner with RLS bypass were all verified by read-only queries.
5. Recovered `019_phase4a_customer_credit_allocation.sql` byte-for-byte from historical GitHub commit `d850ce04c8930134f01a63cd65c5d1947a17b17d`; the blob SHA matches GitHub's value `caefc2e3b46c5a4bae2ff2592b787d3b4092dd61`.
6. Seven applied migration SQL sources remain unavailable from the inspected repository/history: 010, 011, 023 purchasing core, 024 purchasing security, 025 purchasing permissions, 026 membership/branch integrity, and 027 release convergence. No replacement SQL has been fabricated.
7. Added `scripts/smoke_phase0.py`, a credential-optional public smoke test and optional dedicated-account login/refresh rotation/identity/protected-read/logout-revocation journey.
8. Added an explicit source-deletion manifest applier, marked the stale unregistered `apps/api/app/routes/business_engine.py` for removal from existing checkouts, scoped pytest to canonical source tests (not archived package copies), and made routine CI run canonical tests. Strict replay is a manual release gate while exact historical sources remain missing.
9. Added the current read-only ledger snapshot `migrations/live_ledger_snapshot_2026-10-15.json` while retaining the 13 October snapshot as historical evidence.
10. Added `apps/web/package-lock.json` (34,536 bytes; lockfile v3) with root dependency declarations matching `apps/web/package.json`; CI uses `npm ci`. Render Blueprint remains named `LEXA` and declares `/ready`.

## Verification performed

- `python -m compileall -q apps/api/app apps/api/tests`: PASS.
- `python -m pytest -q -rs`: **104 passed, 1 skipped**. The single skip is `apps/api/tests/test_auth_refresh.py` because local offline Python does not have the `redis` runtime dependency. CI installs the declared `apps/api[dev]` dependencies, so this test module should execute in CI.
- `node --test apps/web/tests/*.test.mjs`: **2 passed, 0 failed**.
- `python scripts/check_migration_sources.py`: PASS with 7 documented missing historical sources.
- `python scripts/check_migration_sources.py --strict`: EXPECTED BLOCK/FAIL with 7 gaps; this is not a successful migration-replay validation.
- Lockfile validation: PASS; 62 package entries and `package-lock.json` root dependencies/devDependencies match `package.json`.
- Frontend: in a separate Vercel sandbox, `npm ci`, `npm run typecheck`, `npm test`, and `npm run build` all passed against the same frontend source files as this package.
- Neon: fixed Brain policy SQL passed on the disposable validation branch, and the generated policy definitions were verified. No SQL mutation was executed on canonical `lexa-live` during that test.
- Live HTTP probes (15 October): Render `/health` returned 200; `/ready` returned 200 but its current response includes only `dependencies.database` (the candidate cache-readiness handler is not deployed); the first bodyless `/api/v1/auth/refresh` attempt timed out at 30 seconds; after liveness/readiness warm-up, a retry returned 401 rather than 422 in 0.316 seconds; anonymous `/api/v1/auth/logout` returned 200. Vercel `/login` had previously returned HTTP 200.

## Still blocking full production acceptance

- GitHub branch creation again returned HTTP 403 `Resource not accessible by integration` on 15 October. The changes have not been pushed.
- Render's live `healthCheckPath` remains blank even though `render.yaml` declares `/ready`. The available Render connector does not expose a direct update for this service setting. No second Render service was created, no live environment variables were changed, and no application deploy was triggered.
- Live `/ready` is still the older database-only handler. The reviewed code's Redis/Valkey readiness check must be deployed and observed before readiness acceptance.
- Credentialed browser/API acceptance—login, cookie refresh rotation, authoritative `/auth/me`, protected product read, logout, refresh rejection and access-token rejection after logout—has not been run because a dedicated test account was not supplied. `scripts/smoke_phase0.py` now automates it safely when explicit environment variables are provided.
- Seven exact applied SQL sources are still unavailable. `--strict` replay remains blocked; do not reset Neon or replay partial history on production.

This ZIP is the updated Phase 0 implementation handoff, not a claim of complete production acceptance. The code package and tests are improved; deployment-setting reconciliation, GitHub write access, exact historical SQL recovery, and credentialed hosted acceptance remain release gates.
