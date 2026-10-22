# LEXA 2.8.6 — Phase 0 reliability implementation candidate

Date: 13 October 2026

## Included

- Dependency-aware `/ready` checks for canonical Neon identity/schema/auth readiness and Redis/Valkey ping; `/health` remains process liveness.
- Bounded Redis checks, sanitized error detail, and stable production failure response.
- Corrected dynamic SQL in migration `022_phase6a_brain_foundation.sql`.
- Migration `019_phase4a_customer_credit_allocation.sql` recovered byte-for-byte from historical GitHub commit `d850ce04c8930134f01a63cd65c5d1947a17b17d`; Git blob SHA verified.
- Complete `apps/web/package-lock.json`; frontend CI uses `npm ci`.
- Machine-readable migration source reconciliation and provenance notes; seven exact historical SQL sources remain unresolved and strict source replay is blocked.
- Render Blueprint is explicitly named `LEXA` and declares `/ready`.

## Tests and probes

- Python: 102 passed, 1 skipped in local environment.
- Backend compile: passed.
- Frontend contract tests: 2 passed.
- Frontend install/typecheck/test/build: passed in a Vercel sandbox against matching source hashes for the current repository frontend.
- Read-only live probes: Render `/health` HTTP 200 after warm; Render `/ready` HTTP 200 with legacy database-only readiness payload; Vercel `/login` HTTP 200.

## Not complete / do not claim production acceptance

- GitHub refused branch creation with HTTP 403; package is not pushed.
- Live Render health-check configuration is blank and the new Redis-aware readiness implementation is not deployed.
- Seven exact applied migration SQL files are absent from the inspectable repository history; do not invent their contents and do not run strict replay against production.
- Authenticated browser E2E remains pending.

No production data was reset, no production database migration was executed during this package build, no Render service was created, and no deployment was triggered.
