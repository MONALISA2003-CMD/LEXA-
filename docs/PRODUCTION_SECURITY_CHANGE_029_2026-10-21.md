# Production security change 029 — 2026-10-21

Applied to Neon LEXA live branch `br-soft-star-b1dj2m2w` (`neondb`) and recorded in `schema_migrations` as `029_phase3_runtime_privilege_surface`.

- Render service `LEXA` now has `DATABASE_APP_ROLE=lexa_app`; deploy `dep-dbc5elui0phs73af6k90` reached `live`.
- `lexa_app` is the transaction-local effective application role and has no superuser, database-create, role-create, replication, or RLS-bypass attributes.
- `permissions` now has forced RLS and a read-only SELECT policy for `lexa_app`; writes were revoked.
- `schema_migrations` now has forced RLS and a read-only SELECT policy for `lexa_app`; writes were revoked. SELECT remains available because the production readiness check verifies auth migration presence from this table.
- Live verification after this change: `/ready` returned HTTP 200 with database and cache `ok`; app-role probe confirmed `98` reference permissions readable, no write privilege on `permissions`, and no write privilege on the migration ledger.
- The three remaining RLS-disabled tables are `users`, `tenants`, and `registration_requests`. These participate in pre-authentication, tenant bootstrap, and registration workflows; they need a separately designed policy migration plus authenticated integration tests before enabling RLS, to avoid locking users out.
- The database login role `lexa_runtime` still inherits membership in Neon’s `neon_superuser` role. Application transactions now set `lexa_app`, but removing that inherited capability requires Neon administrator role-management authority unavailable to the SQL role used here. Treat this as a remaining credential-containment action, not as closed.
