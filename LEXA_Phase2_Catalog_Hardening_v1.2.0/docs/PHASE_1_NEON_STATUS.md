# LEXA Phase 1 — Neon Foundation Status

## Scope

This status document applies only to the Neon project named **LEXA**.
No other Neon project is part of this implementation.

## Target

- Neon project: `LEXA`
- Project ID: `wispy-mud-75323042`
- Database: `neondb`
- Production branch: `production` (`br-wild-river-b11wn8sg`)
- Phase 1 validation branch: `lexa-phase1-dev` (`br-soft-star-b1dj2m2w`)
- PostgreSQL: 18.6

Production was not modified during this phase.

## Implemented on the LEXA development branch

- `pgcrypto` enabled
- `pgvector` enabled
- tenants and users
- tenant memberships
- organizations, branches, warehouses and locations
- POS terminals
- roles and permissions
- membership roles
- sessions and devices
- audit log foundation
- `role_permissions`
- transactional `outbox_events`
- `event_consumptions`
- `idempotency_records`
- schema migration registry
- forced RLS on all Phase 1 tenant-owned tables
- restricted `lexa_app` database role
- append-only audit trigger
- cross-tenant membership/role validation trigger

## Security verification

The LEXA application role is deliberately **not** a database owner and does
not have `BYPASSRLS`.

RLS was tested using `lexa_app`:

- tenant A could see its own outbox row;
- tenant B could not see tenant A's outbox row;
- test rows were removed after verification.

The Neon branch currently contains zero business/test tenants, users or
outbox rows.

## Application integration

The API now supports an optional `DATABASE_APP_ROLE` setting. When configured
as `lexa_app`, new SQLAlchemy connections execute `SET ROLE lexa_app`, so
ordinary application requests do not run as the unrestricted Neon owner.

The tenant request boundary continues to set `app.tenant_id` transactionally.

## Verification

Repository Python tests: **29 passed**.

Neon development branch verification:

- 19 Phase 1 tables present;
- 15 Phase 1 tenant-owned tables have forced RLS;
- `pgvector` 0.8.6 available/enabled;
- `pgcrypto` 1.4 available/enabled;
- 4 migration records registered;
- zero test/business tenants remain.

## Production gate

Do **not** apply Phase 1 migrations to `production` until the application
branch, migration set, RLS tests, and production migration procedure have
been reviewed together.
