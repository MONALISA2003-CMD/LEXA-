# LEXA Phase 1 — Complete source ZIP

Release candidate: 2.9.1, 19 October 2026.

This archive contains the complete LEXA repository source from the supplied source package, plus the Phase 1 security/stability implementation, migration 029, regression tests, verification script, release notes, and runbooks.

## Start here
1. Read `docs/PHASE1_SECURITY_STABILITY_REPORT_2026-10-19.md`.
2. Read `docs/PHASE1_SECURITY_STABILITY_RUNBOOK.md` before any database or deployment action.
3. Run `bash scripts/verify-phase1.sh` from the repository root.
4. In `apps/web`, use Node 24 and run `npm ci`, `npm run typecheck`, `npm test`, and `npm run build`.

## Important release gates
- No production database, Render setting, Render deployment, Vercel deployment, or GitHub branch was changed during this work.
- Migration 029 was validated only on the isolated Neon test branch `lexa-phase1-security-test-2026-10-19`.
- The safe login is created without a password; the operator must set a unique password through the Neon SQL editor/secret workflow before any approved application cutover.
- The old elevated `lexa_runtime` role is not changed by this source package.
- Seven exact historical migration sources remain missing. Do not fabricate them or claim from-zero migration replay is complete.
- The local runner could not install the missing npm package `undici-types@6.21.0`; frontend syntax transpilation passed, but full typecheck and production build remain unverified.
- The GitHub integration denied feature-branch creation (HTTP 403), so this ZIP is the handoff artifact. It has not been pushed or deployed.

The ZIP contains source and instructions, not production credentials.
