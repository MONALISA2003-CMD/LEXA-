# Release notes — LEXA 2.12.0 Phase 7 Increment 02 (finalization candidate)

## Fixed

- Supplied the business currency when rendering inventory ledger unit costs.
- Added the business-currency fallback for supplier return value formatting when a return record lacks `currency_code`.
- Added two frontend regression contracts covering these type-safe currency arguments.

## Release-evidence refresh

- Captured current GitHub, Vercel, Render and canonical Neon read-only evidence in `PHASE7_INCREMENT_02_FINALIZATION_REPORT_2026-10-22.md`.
- Recorded the failed Vercel TypeScript build, missing workflow file on current `main`, empty Render health-check path and canonical `lexa-live` migration gap.
- Added machine-readable release gate statuses for Increment 02.

## Validation status

- Backend: 206 passed, 1 skipped (Redis-dependent auth-refresh test unavailable in the local environment).
- Frontend contracts: 38 passed.
- Python compilation and strict migration source reconciliation: passed.
- 43-input migration replay plan: plan-only pass; SQL was not executed.
- Full Node 24 `npm ci`/typecheck/production build is not verified. The available local install could not reach the npm registry. The current Vercel deployment for baseline SHA `dd4069109d5c94143f5c5e28e758128b90dee55a` failed with two TypeScript errors, which this increment addresses but has not yet reverified.
- Authenticated disposable staging E2E, real clean PostgreSQL replay, candidate Render/Vercel parity and production rollout are not run/approved.
- GitHub branch creation was denied with HTTP 403; this archive is an uncommitted source handoff.

**This increment is not production-accepted. No production SQL or deployment was performed.** The six Phase 3 historical SQL source replacements remain permanently dispositioned; do not reopen historical byte recovery.
