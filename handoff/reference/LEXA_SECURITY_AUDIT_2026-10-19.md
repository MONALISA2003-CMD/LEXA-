# LEXA Security Audit — Read-only findings

**Date:** 19 October 2026  
**Scope:** LEXA only — Neon project `LEXA`, canonical branch `lexa-live`, database `neondb`; Render service `LEXA`; GitHub repository `MONALISA2003-CMD/LEXA-`.  
**Change control:** No production data, database schema, grants, policies, environment variables, deployments, or service settings were modified. SQL checks were read-only `SELECT` queries against catalog metadata and function definitions.

## Executive summary

The main confirmed issue is an overprivileged PostgreSQL login role named `lexa_runtime`. Direct read-only role inspection shows `rolbypassrls=true`, `rolcreaterole=true`, `rolcreatedb=true`, `rolreplication=true`, `rolcanlogin=true`, and membership in `neon_superuser`, `pg_read_all_data`, and `pg_write_all_data`. PostgreSQL reports that this session user is allowed to `SET ROLE neon_superuser`. It can also delete from `public.schema_migrations`.

**Production impact is not yet conclusively confirmed:** the Render connector available in this session does not expose the `DATABASE_URL` value, and the `pg_stat_activity` sample did not show an application connection. The deployed source enforces `DATABASE_APP_ROLE=lexa_app` in production, but this validates the per-transaction target role, not the database login role. The Render service's actual `DATABASE_URL` username therefore remains unverified.

This should be treated as a **P0 verification item**. If Render's login username is `lexa_runtime`, the application is starting database connections from a powerful role. The intended `SET LOCAL ROLE lexa_app` narrows ordinary ORM transactions, but should not be treated as a substitute for a least-privilege login role. `health.py` uses `engine.connect()` directly, which does not trigger the `Session.after_begin` hook in `db.py`, so readiness queries run as the connection's login role unless some other connection-level setting changes it.

## Findings

### P0 — Overprivileged `lexa_runtime` role; verify Render identity

Confirmed from Neon `pg_roles`, `pg_auth_members`, and a read-only query executed as `lexa_runtime`:

- `rolbypassrls=true`
- `rolcreaterole=true`
- `rolcreatedb=true`
- `rolreplication=true`
- `rolcanlogin=true`
- The session user can set role to `neon_superuser` (`pg_has_role(session_user, 'neon_superuser', 'SET') = true`).
- It has effective access to `pg_read_all_data` and `pg_write_all_data`.
- `has_table_privilege('lexa_runtime', 'public.schema_migrations', 'DELETE') = true`.

`lexa_app` itself is materially safer: `NOLOGIN`, no superuser/create-role/create-database/replication attributes, and `rolbypassrls=false`. `apps/api/app/db.py` applies `SET LOCAL ROLE lexa_app` at the beginning of SQLAlchemy `Session` transactions. `apps/api/app/config.py` requires that configured target in production. However, `DATABASE_APP_ROLE` is not the same as the login identity in `DATABASE_URL`, and the elevated login can still create risk if the app or any direct engine-connection path runs without the intended role.

**Action to close verification:** in Render Dashboard → LEXA → Environment, inspect only the username component of `DATABASE_URL` (the text after `postgresql://` and before `:`). Do not copy or disclose the full URL/password. If it is `lexa_runtime`, move to a reviewed remediation plan before making changes. The service environment values are not readable through the connected Render tools in this session.

### P1 — Five tables are RLS-disabled and `lexa_app` has full CRUD

All five tables are owned by `neondb_owner`, have RLS disabled, and have no policies in `pg_policies`:

| Table | Current `lexa_app` grants | Assessment |
|---|---|---|
| `permissions` | SELECT, INSERT, UPDATE, DELETE | Permission definitions are shared reference data; runtime should normally need read access, while changes should be controlled through migrations/admin tooling. |
| `registration_requests` | SELECT, INSERT, UPDATE, DELETE | Pre-tenant idempotency records need registration-flow access; unrestricted table CRUD gives the runtime broad cross-request visibility and mutation capability. Review whether deletion belongs only to cleanup/admin code. |
| `schema_migrations` | SELECT, INSERT, UPDATE, DELETE | Runtime readiness reads the ledger; ordinary application requests should not need to alter or delete migration history. This is the clearest grant-reduction candidate. |
| `tenants` | SELECT, INSERT, UPDATE, DELETE | Login/registration and identity flows need some global lookup/write behavior; global cross-tenant access is by design at the table level, so constrain which operations and code paths can use it. |
| `users` | SELECT, INSERT, UPDATE, DELETE | Email-based login and initial registration require global identity lookup/creation. Password hashes and active flags make blanket CRUD sensitive; use the smallest operations/columns or controlled authentication functions feasible. |

`PUBLIC` has `USAGE` on schema `public` but not `CREATE`; no direct `PUBLIC` table grants were returned for these five tables. This is not evidence of unauthenticated internet database access. It is a least-privilege and defense-in-depth issue for database principals that already connect.

### P1 — Default privileges grant broad CRUD on future tables

PostgreSQL default privileges for objects created by `neondb_owner` in `public` grant `lexa_app` table privileges `SELECT, INSERT, UPDATE, DELETE` (`arwd`) and sequence `SELECT, USAGE` (`rU`). This can be intentional for tenant tables guarded by RLS, but it increases the risk that a newly introduced table without RLS/policy setup becomes reachable by the app role. Add a migration/CI gate that requires new tenant-owned tables to have RLS enabled and forced, an appropriate fail-closed policy, and reviewed grants before release.

### P1 — Branch access helper is permissive with incomplete identity context

`public.lexa_can_access_branch(uuid)` is `SECURITY DEFINER`, owned by `neondb_owner`, uses `search_path=pg_catalog, public`, and its `EXECUTE` grant is restricted to `lexa_app` and the owner. Its function body allows access if the active membership is Owner/Administrator/Manager, if the active membership has no branch-assignment rows, or if the branch is explicitly assigned.

Because the “no branch assignments” condition evaluates true when the membership CTE is empty, the function returns `true` when the user/tenant context is absent or the user has no active membership. The existing branch table policy also checks `tenant_id` against `app.tenant_id`, and the normal API dependency validates a signed token, session and active membership; this finding alone does not prove a data leak. Still, a security helper used in RLS should explicitly return `false` when `app.user_id` or `app.tenant_id` is missing, then apply the “no assignments means all branches” rule only to an established active membership if that is the intended product rule.

### P2 — Other security-definer functions have good execution boundaries; validate invitation checks

Catalog ACL checks show these functions are `SECURITY DEFINER`, owned by `neondb_owner`, set a fixed `search_path`, and have explicit execute privileges for `lexa_app` and the owner; `PUBLIC` does not have `EXECUTE`:

- `lexa_can_access_branch(uuid)`
- `lexa_find_session_by_refresh_hash(text)`
- `lexa_get_invitation_by_token(character varying)`
- `lexa_list_user_workspaces(uuid)`

`lexa_find_session_by_refresh_hash` returns only identifiers for a matching refresh-token hash where the session is unrevoked and unexpired. `lexa_list_user_workspaces` returns workspaces for the supplied user ID where membership and tenant are active; the login code calls it after verifying the password and separately checks membership for the selected tenant. `lexa_get_invitation_by_token` performs a hash lookup and returns status/expiry fields but does not filter by expiry/status in the function body; confirm that the caller rejects expired, revoked, or already-used invitations before accepting them.

### Positive authentication controls found in source

- Access tokens use HS256 with expiry, issuer and audience validation.
- Password hashes are produced and verified with `pwdlib`'s recommended password hash implementation.
- Login/registration rate limiting fails closed with HTTP 503 if Redis is unavailable.
- Refresh tokens are generated with `secrets.token_urlsafe(48)`; only SHA-256 hashes are persisted.
- Refresh lookup requires unrevoked and unexpired session state; refresh locks the session row and rotates the token hash.
- Refresh cookie is `HttpOnly`, `Secure` when `APP_ENV=production`, `SameSite=Lax`, and path `/`.
- `/auth/me` checks access-token identity against session expiry/revocation and active user, tenant and membership.
- `tenant_db` sets transaction-local `app.tenant_id` and `app.user_id`, checks the session and active membership before a protected endpoint proceeds.
- Production configuration validates `DATABASE_APP_ROLE=lexa_app`, a nontrivial JWT secret, explicit CORS origins, and a pooled Neon `DATABASE_URL`.

These source-level controls are positive evidence but do not substitute for authenticated hosted acceptance tests.

## Authentication and production identity acceptance still pending

The Render service configuration shows a blank health-check path while repository `render.yaml` declares `/ready`. The source readiness function checks canonical Neon project/branch/database, required schema, migration 028, the refresh lookup function's execute privilege and security-definer owner, plus Redis availability. Direct HTTP probes of Render could not be completed from this execution environment (host resolution was unavailable), Render request logs returned no matching `/ready`, `/health` or `/api/v1/auth/me` entries, and `pg_stat_activity` did not show a Render application connection during the audit.

Therefore the audit has not established the live `DATABASE_URL` login username or completed a credentialed login/refresh/logout round trip. No user passwords, refresh-token values, complete connection strings, or business rows were queried or exposed.

## Recommended remediation order (proposal only; not applied)

1. Verify the Render `DATABASE_URL` username and `DATABASE_APP_ROLE` setting without sharing any secret values.
2. If the login role is `lexa_runtime`, prepare a branch-first role/grant migration and rollback plan. Create/choose a genuinely least-privilege login role and ensure it cannot inherit or `SET ROLE` to `neon_superuser`, `pg_read_all_data`, or `pg_write_all_data`. Keep the application target role non-login and RLS-bound. Do not mutate production until the intended Render/Neon role path has been tested on an isolated clone.
3. Remove runtime `INSERT/UPDATE/DELETE` on `schema_migrations`; likely make `permissions` runtime read-only; determine operation/column requirements for `tenants`, `users`, and `registration_requests` from all code paths before changing those grants.
4. Decide whether to revise the `neondb_owner` default ACL and add CI validation so RLS and grants are reviewed for every new table.
5. Update `lexa_can_access_branch` to fail closed for missing tenant/user identity, test in an isolated branch, and preserve the intended branch-access semantics for active memberships with no explicit assignments.
6. Test authentication lifecycle and tenant isolation with two dedicated test tenants/users on an isolated environment, including refresh-token replay, revoked session, expired session, disabled user/tenant, invalid invitation, no context/empty context, and cross-tenant reads.
7. Only after tests and review, prepare a reviewed production migration/rollout with rollback and post-deploy checks.

## Source references

- [Database session role hook](https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/db.py)
- [Production environment validation](https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/config.py)
- [Tenant/session context and permission checks](https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/dependencies.py)
- [Authentication routes](https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/routes/auth.py)
- [Readiness implementation](https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/health.py)
- [Canonical readiness / environment declaration](https://github.com/MONALISA2003-CMD/LEXA-/blob/main/render.yaml)
- [Migration 028 refresh-lookup privilege boundary](https://github.com/MONALISA2003-CMD/LEXA-/blob/main/migrations/028_phase0_auth_rls_runtime_hardening.sql)
