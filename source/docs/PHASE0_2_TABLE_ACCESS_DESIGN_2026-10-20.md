# LEXA Phase 0–2 — Live Table Access and Least-Privilege Design

**Date:** 20 October 2026 (Africa/Kampala)  
**Disposition:** Design evidence only. **Not a migration, not authorization, and not deployed.**  
**Canonical target inspected read-only:** Neon project `wispy-mud-75323042`, branch `br-soft-star-b1dj2m2w`, database `neondb`.

## Purpose

Close the ambiguity around five tables that were previously described simply as “tables without RLS.” These tables are structurally different from ordinary tenant-owned business records. A blanket `ENABLE ROW LEVEL SECURITY` or `FORCE ROW LEVEL SECURITY` action could block registration and login before the authenticated identity and trusted tenant context exist. This document records the observed live schema, grants, security-definer helpers and source call paths, then proposes a separately testable target design. No production writes were issued during this inspection.

## Live evidence observed 20 October 2026

A read-only catalog query against the canonical branch reported, for each of the following five tables: `relrowsecurity=false`, `relforcerowsecurity=false`, no policies in `pg_policies`, owner `neondb_owner`, and effective `lexa_app` privileges `SELECT=true`, `INSERT=true`, `UPDATE=true`, `DELETE=true`.

| Table | Key observed columns/shape | Why a naive tenant RLS policy is unsafe | Current issue |
|---|---|---|---|
| `public.permissions` | `id uuid`, globally unique `code varchar`, `description text`; no `tenant_id` | It is a global permission dictionary read during role/permission evaluation, not an ordinary tenant-owned row set | Runtime app role can modify/delete global permission records even though request handling appears to need only reads |
| `public.registration_requests` | Idempotency key (unique), email, request hash, response status/body, optional user and tenant IDs, created/expiry timestamps | New registration has no tenant yet; the route must look up the idempotency key, create user/tenant, and write replay status/body | Direct DML privileges are broad; replay and privacy semantics need dedicated tests and a narrower write boundary |
| `public.schema_migrations` | `version varchar` primary key and `applied_at timestamptz`; no source checksum or SQL body | It is a release ledger, not tenant data; health/readiness reads it before any tenant context exists | Runtime role can alter/delete/insert ledger records; history does not prove exact applied SQL bytes |
| `public.tenants` | `id uuid`, `name`, `status`, `created_at`; root tenant catalogue with no `tenant_id` | Registration creates a tenant before `app.tenant_id` is set; login/workspace choice needs membership-scoped discovery | Runtime app role has unrestricted table DML, so a caller path must be narrower even if ordinary reads are later gated |
| `public.users` | Global `id`, unique `email`, `password_hash`, `is_active`, `created_at`, optional `display_name`; no tenant foreign key on the user identity row | Login must find a user by email before tenant selection; initial registration creates a user before tenant context | Broad SELECT/DML on global credentials means cross-user exposure/alteration risk if any query path is misused |

`public.schema_migrations` was also described directly: its only columns are `version` and `applied_at`. There is no applied-source checksum. The ledger is version evidence, not byte-for-byte proof of executed migration SQL.

### Runtime-role evidence

A read-only `pg_roles` check returned:

| Role | LOGIN | SUPERUSER | INHERIT | CREATEDB | CREATEROLE | REPLICATION | BYPASSRLS | Member of `neon_superuser` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `lexa_app` | No | No | No | No | No | No | No | No |
| `lexa_runtime` | Yes | No | Yes | Yes | Yes | Yes | Yes | Yes |

`lexa_runtime_safe` was not returned on this production branch. The role catalog showed `lexa_runtime` can `SET ROLE lexa_app`, but also has elevated database/role/replication and RLS-bypass attributes inherited or assigned through its membership. This does **not** mean the app role itself is elevated; it means the login role requires a separately approved credential cutover. Do not alter it in place or remove its privileges until a replacement login and all flows are proven.

### Existing SECURITY DEFINER helper evidence

Read-only definition queries found these functions owned by `neondb_owner`, with `SECURITY DEFINER` and `search_path=pg_catalog, public`:

- `lexa_list_user_workspaces(p_user_id uuid)`: returns active memberships joined to active tenants and filtered by `p_user_id`.
- `lexa_find_session_by_refresh_hash(p_hash text)`: resolves a non-revoked, unexpired refresh session to session, tenant and user IDs.
- `lexa_get_invitation_by_token(p_token_hash varchar)`: resolves an invitation using the token hash.

These are possible narrow boundaries, not automatically safe just because the functions exist. Before relying on one, verify its exact argument provenance, EXECUTE grants, owner, search path, returned fields, rate limiting, and behavior for forged/unknown values. A `SECURITY DEFINER` function has to validate its own inputs and must not return broad directory data.

## Source-path observations

Current local candidate source inspection identified these relevant paths (route/source contracts, not an exhaustive runtime trace):

- `apps/api/app/routes/auth.py`: registration idempotency lookup and writes to `RegistrationRequest`; registration creates `Tenant` and `User` before setting tenant context; login looks up `User` by email; workspace choice calls `lexa_list_user_workspaces`; session refresh uses the refresh-hash helper; authenticated profile flows read user/tenant details.
- `apps/api/app/dependencies.py`: `require_permission` reads permission codes from the global `permissions` dictionary.
- `apps/api/app/health.py`: readiness checks the migration ledger without a tenant context.

A proper implementation must trace every SQL query, all SQLAlchemy ORM flushes, transaction/commit points, retry behavior and raw SQL function grants on an isolated branch before changing access. Source grep by itself is not enough to certify this design.

## Recommended target policy by table

### `permissions`

Treat it as an application-owned global reference dictionary. The runtime application should receive only `SELECT` (and only any additional operation proven necessary by a traced code path). Inserts/updates/deletes belong to an explicit migration/operator role. RLS is not required merely to make a global dictionary safe if least-privilege grants are correctly applied; if RLS is used, keep the global read policy explicit and test fail-closed behavior. Never grant arbitrary tenant/runtime write access to permission definitions.

### `schema_migrations`

Grant the application `SELECT` only if readiness continues to read the ledger directly. All insert/update/delete/DDL capability belongs to a separate migration/operator role. A narrow read-only readiness function may be considered if a clean privilege boundary is needed. Do not add tenant RLS to this global release ledger.

### `registration_requests`

Preferred end state: route idempotency reads/writes through a narrow database function or tightly scoped data-access helper with a deliberate anonymous/pre-tenant trust contract. The operation must validate request-key format, bind the key to a canonical request hash, protect replay payloads, expire old rows without exposing them, and prevent a supplied key from reading another registration response. Decide whether rate limiting and address/email normalization are part of the same request transaction. Current evidence does not justify blindly removing DML or inventing a policy: registration presently requires insert/select/update behavior before tenant context exists. Do not grant DELETE unless an actual runtime path requires it; archival/expiry cleanup should be operator-controlled or narrowly delegated.

### `tenants`

Tenant creation should occur only as part of an atomic, authorized registration/bootstrap operation. After authentication, tenant reads should be driven by the validated membership/workspace function or the trusted tenant context—not caller-supplied tenant IDs. Consider a narrow SECURITY DEFINER registration/workspace API or a separate control-plane role for pre-tenant create and membership discovery, then restrict ordinary runtime direct access. Do not create a generic policy that allows a logged-out request to read the entire tenant catalogue.

### `users`

Split pre-identity authentication from normal user-scoped access. Login needs a narrow identity lookup by normalized email to verify a hash; registration needs to create the identity before tenant context exists; ordinary authenticated requests should only read/update the current user and authorized membership surfaces. Prefer narrowly scoped functions for identity lookup and registration or a separate identity access role. Do not assume `app.tenant_id` can scope the global identity row: `users` has no `tenant_id`, and a user may have multiple memberships/workspaces. Password hashes and status must never be returned through general lookups. Verify uniqueness/race behavior and generic errors for missing/disabled/invalid accounts.

## Required design and tests before any implementation

1. **Build a call graph:** enumerate SQL/ORM operations on all five tables, including exception/retry paths, signup, login, multiple workspace selection, `/me`, refresh/logout, invitation acceptance, health/readiness, migrations and cleanup jobs.
2. **Specify allowed principals and operations:** unauthenticated, authenticated/no tenant selected, tenant member, cross-tenant member, branch-limited member, owner/admin, runtime application role and migration/operator role.
3. **Specify helper contract:** arguments, normalization, authorization authority, return fields, error behavior, EXECUTE rights, `search_path`, function owner and SQL-injection protections.
4. **Implement on a disposable Neon branch only:** test login/registration before tenant context, duplicate registration retries, mismatched idempotency hashes, multiple memberships, disabled users/tenants, refresh rotation/reuse, invitation expiry/revocation, health/readiness and migration tooling.
5. **Prove negative cases:** User A cannot enumerate user B, tenant A cannot resolve tenant B absent membership, caller cannot forge a user/tenant selector, anonymous replay key cannot disclose a response to a different request, regular app role cannot mutate permission dictionary/migration ledger, and runtime login itself cannot bypass RLS or acquire broad role membership.
6. **Inspect resulting state:** verify exact grants, policies, role attributes/membership, security-definer owner/settings, function EXECUTE grants, and transaction-local tenant context after tests.
7. **Only after tests:** prepare a migration and rollback script, obtain explicit approval, choose a cutover window, back up, run production changes using operator credentials, and observe authentication/readiness. Do not use the app runtime login as a migration administrator.

## Release decision

The absence of RLS on these five tables is a real security-control gap, compounded by excessive DML grants and the elevated `lexa_runtime` login. But the right fix is **not** to add a tenant policy blindly. The table-specific target above is design-only and does not close the production blocker until the implementation and its negative tests are run and reviewed. Phase 3 schema-changing work remains **NO-GO** pending the release gates in `PHASE0_2_REMAINING_GATE_REGISTER_2026-10-20.md`.
