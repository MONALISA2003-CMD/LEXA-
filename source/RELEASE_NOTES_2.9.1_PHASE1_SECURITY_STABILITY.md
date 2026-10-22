# LEXA 2.9.1 — Phase 1 Security and Stability

Date: 19 October 2026

## Included

- Shared transaction-local application-role helper for ORM sessions and direct health/readiness connections.
- Production validation for `DATABASE_LOGIN_ROLE`, pooled Neon endpoint, TLS mode, application role, JWT secret strength, and explicit CORS.
- Migration 029 to provision `lexa_runtime_safe` with constrained attributes and SET-only membership in `lexa_app`.
- Runtime security regression tests and `scripts/verify-phase1.sh`.
- Isolated Neon branch validation and production rollout instructions.

## Verification

- Python: 109 passed, 1 skipped because the offline runner lacks `redis`.
- Frontend contract tests: 4 passed.
- TypeScript syntax transpilation: 27 files passed.
- Full frontend typecheck/build remains unverified because the local npm cache lacks `undici-types` and registry DNS is unavailable.
- Seven authoritative historical migration sources remain missing, so strict from-zero replay is blocked.

## Release status

Source-only candidate. No production database, role, Render environment, deployment, Vercel deployment, or GitHub branch was changed. See `docs/PHASE1_SECURITY_STABILITY_RUNBOOK.md`.
