# LEXA deployment fixes — 13 October 2026

## Changes in this package

- Removed PostgreSQL timeout GUCs from SQLAlchemy connection startup options. Neon PgBouncer can reject these startup options. Transaction-local `SET LOCAL` settings now apply statement, lock, and idle-in-transaction limits after a transaction begins.
- Updated the database hardening regression test to prevent the startup-options regression.
- Removed the incorrect npm cache dependency on `package.json` in root GitHub Actions CI; npm caching requires a lockfile.
- Made malformed/corrupt legacy password hashes fail closed rather than raising a server error during verification.

## Before production deployment

1. Review `git diff --check` and the source diff.
2. Run backend tests and the frontend typecheck/build in CI.
3. Push to GitHub; wait for Vercel and Render deployments to finish.
4. Verify `/health` and `/ready` on the actual Render service, then test login and core workflows.

This package does not claim that production has already been deployed. Environment secrets and live service settings are not included.
