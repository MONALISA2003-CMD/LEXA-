# LEXA Phase 1 — Security and stability runbook

Date: 19 October 2026
Scope: LEXA only. This runbook does not authorize production changes.

## What changed in this source package

- `DATABASE_LOGIN_ROLE` can select the expected database login independently of `DATABASE_APP_ROLE`.
- Production validation requires a pooled Neon endpoint, TLS (`sslmode=require` or stronger), a configured login-role match, `DATABASE_APP_ROLE=lexa_app`, an explicit CORS allow-list, and a sufficiently long JWT secret.
- Direct engine health checks now apply `SET LOCAL ROLE lexa_app` before querying the schema. ORM sessions continue applying the same role per transaction.
- `migrations/029_phase1_runtime_role_least_privilege.sql` provisions a separate `lexa_runtime_safe` login with no role creation, database creation, replication, RLS bypass, or inherited privileges. It gives the login only `SET` membership in `lexa_app` and checks that direct table privileges and Neon administrator membership are absent.
- Regression tests cover login-role/TLS/pooler validation, transaction-local role switching, health-check ordering, and migration safeguards.

## Why the safe login is separate

The existing `lexa_runtime` role is connected to elevated Neon-managed role membership. The connected database owner cannot alter that role's elevated attributes or revoke its `neon_superuser` membership; Neon rejects those operations even on the isolated test branch. The safe remediation is to create a separate login using SQL role attributes, validate it, and switch the application to it only in an approved release. The existing login is not modified by migration 029.

## Isolated-branch validation completed

Test branch: `lexa-phase1-security-test-2026-10-19` (`br-red-voice-b16z9b0i`), created from `lexa-live`.

The migration's SQL was executed on that isolated branch. The resulting `lexa_runtime_safe` role was verified as:

- LOGIN enabled; not superuser
- `NOINHERIT`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS`
- not a member of `neon_superuser`
- can `SET ROLE lexa_app`
- cannot directly `SELECT` from `public.users` or `DELETE` from `public.schema_migrations`

A prior isolated test iteration using the same safe role attributes and a test-only password confirmed the intended split: `session_user=lexa_runtime_safe`, `current_user=lexa_app` after the transaction-local role switch, application-role access succeeds, and the login role itself cannot read `public.users` or delete migration history. The final migration-created role has no password until the operator sets one separately; the current branch role cannot authenticate until then.

No SQL was executed against the canonical `lexa-live` or `production` branches. No Render environment variables, deployments, Vercel deployments, or GitHub branches were changed.

## Approved production rollout — do not run without explicit approval

1. Recover/confirm the current source and review this complete ZIP.
2. Take a Neon backup and verify a recovery path.
3. Apply migration 029 to an isolated branch first; verify all checks and the full API acceptance suite.
4. Set a password for `lexa_runtime_safe` in the Neon SQL editor as the role creator, using a unique secret (for example, `ALTER ROLE lexa_runtime_safe WITH PASSWORD '<unique-secret>';`). The role-management password-reset action cannot initialize a password for a role that has none. Do not commit the secret or place it in this repository.
5. In Render, set `DATABASE_LOGIN_ROLE=lexa_runtime_safe` and update `DATABASE_URL` to the same pooled endpoint with the new role credentials. Keep `DATABASE_APP_ROLE=lexa_app`.
6. Deploy through the existing approved release process only. Confirm `/ready`, login, refresh rotation, `/auth/me`, and a protected tenant-scoped read using a dedicated test account.
7. Only after successful acceptance, separately plan disabling/deleting the old elevated `lexa_runtime` login. Do not assume the old role is safe merely because the new login works.

## Verification

From the repository root:

```bash
bash scripts/verify-phase1.sh
```

Expected local result at package assembly: 109 Python tests passed, one auth-refresh test skipped because `redis` is not installed in this runner; four frontend contract tests and TypeScript syntax transpilation for 27 files passed. Frontend `npm ci`, full typecheck, and Next.js production build still require a dependency-equipped Node 24 environment because `undici-types@6.21.0` is not cached and registry DNS is unavailable. Six exact historical migration SQL files remain missing after recovering `027_release_convergence.sql`; strict migration replay is blocked until authoritative sources are recovered.
