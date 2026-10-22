# LEXA Security Audit — Confirmed Runtime Identity and Remediation

**Date:** 19 October 2026  
**Scope:** LEXA only — GitHub `MONALISA2003-CMD/LEXA-`, Neon project `wispy-mud-75323042`, canonical branch `lexa-live` (`br-soft-star-b1dj2m2w`), Render service `LEXA`.  
**Mode:** Read-only inspection. No production data, grants, roles, policies, environment variables, or deployments were changed.

## Executive summary

The supplied Render `DATABASE_URL` uses the login role `lexa_runtime`. Its hostname matches the active pooled read-write endpoint for LEXA's canonical Neon branch. This confirms the connection target and role identity **provided the supplied URI is the current Render value**; the Render connector itself does not expose secret environment-variable values, and no active Render connection was visible in the database activity snapshot.

`lexa_runtime` is a critical least-privilege risk. PostgreSQL reports it has `BYPASSRLS`, `CREATEROLE`, `CREATEDB`, and replication attributes; it is a member of `neon_superuser`, and inherits the `pg_read_all_data` and `pg_write_all_data` privileges through that membership chain. It can `SET ROLE` to `neon_superuser`, as confirmed by `pg_has_role(..., 'SET')`.

The application code does apply `SET LOCAL ROLE lexa_app` through SQLAlchemy's `Session.after_begin` hook. This reduces the effective role for ordinary ORM transactions. It does **not** make the powerful login safe: PostgreSQL role selection is authorized from the session login's membership chain, which remains `lexa_runtime`. Any successful arbitrary-SQL execution path could still attempt to switch to a role that the login is allowed to set. Also, `apps/api/app/health.py` uses `engine.connect()` directly, bypassing the session hook; those calls currently perform readiness/catalog checks, but execute as the elevated login.

## Confirmed findings

### P0 — Overprivileged runtime login

Observed catalog attributes for `lexa_runtime`:

- `rolcanlogin = true`
- `rolbypassrls = true`
- `rolcreaterole = true`
- `rolcreatedb = true`
- `rolreplication = true`
- `rolinherit = true`

Observed role memberships include `neon_superuser`, `lexa_app`, and inherited read/write-all-data roles. `pg_has_role('lexa_runtime', 'neon_superuser', 'SET')` returned true. An explicit database check as `lexa_runtime` confirmed `current_user = session_user = lexa_runtime` and showed it can delete from `public.schema_migrations` and read the `users` table.

**Risk:** if this credential is used or leaked outside the intended application wrapper, tenant RLS can be bypassed and data/role-level privileges are far broader than required for an API runtime.

### P1 — Five public tables have RLS disabled and broad `lexa_app` CRUD grants

All are owned by `neondb_owner`. `lexa_app` has `SELECT, INSERT, UPDATE, DELETE` on each:

| Table | Finding and proposed direction |
|---|---|
| `permissions` | Looks like a global permission catalogue. Application use appears to need reads; evaluate removing runtime write privileges after confirming no endpoint mutates it. |
| `registration_requests` | Registration requires idempotency insert/read/update; deletion does not appear required in the request flow. Retain only necessary operations and consider expiry cleanup via a separate controlled job. |
| `schema_migrations` | Read by readiness checking; application runtime should not be able to alter/delete the migration ledger. Restrict writes to migration/deployment tooling. |
| `tenants` | Used for pre-tenant registration and identity resolution; no RLS exists. Review every read/update path and add controlled tenant predicates/authorization before considering RLS. |
| `users` | Needed for pre-tenant login/registration, but global `SELECT/UPDATE/DELETE` under the app role is sensitive due to password hashes and account lifecycle. Tighten grants and verify every update/reset path before change. |

Do not simply enable RLS on all five. Registration and login intentionally access some of these objects before a tenant context is known. The remediation needs compatible policies or carefully scoped access paths and regression tests.

### P1 — Branch authorization helper can fail open with incomplete context

`public.lexa_can_access_branch(uuid)` is `SECURITY DEFINER`, owned by `neondb_owner`, has fixed `search_path = pg_catalog, public`, and is executable by `lexa_app` and the owner only (not `PUBLIC`). Its source determines active membership from `app.user_id` and `app.tenant_id`, then includes an `OR NOT EXISTS` branch-assignment predicate. If tenant context exists but user context is missing/invalid, the membership CTE is empty and this `NOT EXISTS` condition can evaluate true.

The helper is used by RLS policies on `branches`, `analytics_branch_daily_metrics`, `business_transactions`, `pos_terminals`, `price_contexts`, `sales`, and `warehouses`. Their policies also enforce tenant predicates; therefore this observation is a branch-level isolation concern within a tenant, not evidence of cross-tenant access by itself. Expected owner/admin/manager and unassigned-branch semantics should be preserved while making missing identity context deny access.

### Positive controls — four security-definer functions

The following functions have fixed search paths and explicit `EXECUTE` grants only to `lexa_app` and `neondb_owner`; no `PUBLIC EXECUTE` grant was found for these four:

- `lexa_can_access_branch(uuid)`
- `lexa_find_session_by_refresh_hash(text)`
- `lexa_get_invitation_by_token(character varying)`
- `lexa_list_user_workspaces(uuid)`

`lexa_find_session_by_refresh_hash` returns only session, tenant and user identifiers for a non-revoked, unexpired token hash. `lexa_list_user_workspaces` accepts a user ID and returns that user's active workspace list; current source calls it during login after password verification. These functions still warrant regression tests for unauthenticated invocation and cross-user arguments.

A wider catalog scan also showed `PUBLIC EXECUTE` on several ordinary `SECURITY INVOKER` business functions, including accounting posting/reversal and reconciliation functions. That is not automatically an exploit because invoker functions still run under caller privileges/RLS, but the public function grants should be inventoried and reduced to explicit roles where appropriate, with trigger functions handled separately.

### Authentication and transaction context

Positive source evidence:

- Production configuration validation requires `DATABASE_APP_ROLE=lexa_app`, a sufficiently long JWT secret, explicit production CORS origins, and a pooled Neon endpoint.
- The session hook applies `SET LOCAL ROLE lexa_app` and transaction-local timeouts.
- Auth endpoints establish `app.tenant_id` and `app.user_id` transaction-locally in the current source, and verify session validity, active membership, user status and tenant status.
- Refresh tokens are stored as hashes and rotated during refresh; logout sets `revoked_at`.
- The refresh-token lookup function is explicitly granted to `lexa_app` and its result is revalidated under tenant/user context.

Remaining verification:

- Render's `DATABASE_APP_ROLE` current value is not visible through the available Render connector. Source validation strongly constrains it but does not prove the live environment value.
- Live authenticated login, refresh replay, logout revocation, workspace switching and cross-tenant/branch denial were not run because no dedicated test account was supplied and the production API couldn't be independently probed through the available public-fetch tool.
- A `SET LOCAL ROLE` hook exists only for SQLAlchemy `Session` transactions. `health.py` calls `engine.connect()` directly for readiness and that path executes as `lexa_runtime`; current statements are readiness and catalog checks, but it is a privileged code path that should be isolated.

## Recommended remediation order (not executed)

1. **Replace the Render database login with a dedicated login role that has no `BYPASSRLS`, no `CREATEDB`/`CREATEROLE`/replication powers, and no membership in `neon_superuser`, `pg_read_all_data`, or `pg_write_all_data`.** Keep `lexa_app` as the least-privileged transaction role, or connect directly as an appropriately provisioned least-privilege login. Do not just rotate the password for `lexa_runtime`; the role's memberships/attributes need correcting through a reviewed migration.
2. Make database readiness use a least-privilege connection/role and keep it read-only. Avoid making `engine.connect()` the route to an elevated database role.
3. Revoke unnecessary `INSERT/UPDATE/DELETE` from `lexa_app` on `schema_migrations` and `permissions`; review exact operation needs for `registration_requests`, `tenants`, and `users` before drafting DDL.
4. Make `lexa_can_access_branch` fail closed when `app.user_id` or `app.tenant_id` is missing/invalid; preserve documented unassigned-branch behavior only for an authenticated active membership.
5. Inventory `PUBLIC EXECUTE` on all application-owned routines; revoke from `PUBLIC` and grant to `lexa_app` or a narrower role where appropriate, after distinguishing triggers and documented caller needs.
6. Implement and verify changes first against an isolated Neon branch, add tests for RLS/no-context/cross-tenant/cross-branch/role switching, then plan a reviewed migration and rollback. Production changes are outside this report's execution.

## Verification facts

- Current LEXA branch's active pooled endpoint matches the hostname in the supplied URI: `ep-fragrant-grass-b1n0moer-pooler.c-5.eu-central-1.aws.neon.tech`.
- 114 public tables have RLS enabled and `FORCE ROW LEVEL SECURITY`; the five named tables are the only public base tables observed with RLS disabled in the catalog snapshot.
- 114 enabled-RLS tables had at least one policy. Tenant and branch policy expressions were inspected without reading business records.
- No production settings, roles, grants, policies, schemas, rows or deployments were modified.

## Source references

- LEXA DB transaction role hook: https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/db.py
- LEXA production settings validation: https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/config.py
- LEXA RLS context and auth dependency: https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/dependencies.py
- LEXA readiness direct connection: https://github.com/MONALISA2003-CMD/LEXA-/blob/main/apps/api/app/health.py
- LEXA Phase 0 hardening migration: https://github.com/MONALISA2003-CMD/LEXA-/blob/main/migrations/028_phase0_auth_rls_runtime_hardening.sql
- PostgreSQL `SET ROLE` semantics: https://www.postgresql.org/docs/16/sql-set-role.html
- PostgreSQL row security behavior: https://www.postgresql.org/docs/15/ddl-rowsecurity.html
