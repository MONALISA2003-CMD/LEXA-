# LEXA Phase 1 — Business Kernel

## Implementation status

**Source implementation:** complete
**Source verification:** GREEN
**Neon migration validation:** GREEN on a temporary branch inside the LEXA project
**Live `lexa-live` migration:** pending explicit completion of the prepared Neon migration gate

## Purpose

Phase 1 turns the existing LEXA foundation into a reusable business operating kernel for unrelated business categories.

The existing organization, RBAC, catalog, inventory, audit, outbox and idempotency layers remain authoritative. This slice adds universal entities that can be composed by industry packs later.

## Universal kernel entities implemented

- Party
- Party Role
- Service
- Resource
- Asset
- Document metadata
- Business Transaction
- Payment
- Task
- Case
- Project
- Contract

`Location` already exists in the organization foundation and remains the authoritative location entity.

## Security

Every new table is tenant-owned, protected by PostgreSQL Row-Level Security, and forced into RLS. Protected API routes require `kernel.read` or `kernel.manage`.

The migration also adds composite tenant foreign-key guards where a kernel record references another tenant-owned kernel record, so tenant mismatches fail at the database boundary as well as in the service layer.

Critical create operations emit an audit record and transactional outbox event. The existing idempotency layer is used on supported create commands.

## API

Base prefix: `/api/v1/kernel`

- `GET /summary`
- `GET/POST /parties`
- `POST /parties/{party_id}/roles`
- `GET/POST /services`
- `GET/POST /resources`
- `GET/POST /assets`
- `GET/POST /documents`
- `GET/POST /transactions`
- `GET/POST /payments`
- `GET/POST /tasks`
- `GET/POST /cases`
- `GET/POST /projects`
- `GET/POST /contracts`

## Browser surface

The web application now includes a `/kernel` workspace for the first universal objects:

- Parties
- Services
- Resources
- Tasks

The existing workspace is linked to this surface without changing the Products or Inventory flows.

## Migration

`012_phase1_business_kernel.sql`

The migration is additive and contains no `DROP TABLE`, `TRUNCATE`, or bulk-delete operation.

## Neon validation record

Target project: `LEXA` (`wispy-mud-75323042`)

Target branch: `lexa-live` (`br-soft-star-b1dj2m2w`)

Target database: `neondb`

Prepared temporary migration branch: `br-silent-shape-b1lbvh7f`

Prepared migration: `3aaa4494-f9c9-4da3-b7f5-80629d16bef3`

Validation on the temporary branch confirmed:

- 12 kernel tables created
- 12 kernel tables have RLS enabled
- 12 kernel tenant policies present
- 2 kernel permissions present
- migration record `012_phase1_business_kernel` present
- migration execution completed successfully

A temporary tenant-scoped write probe also succeeded on the temporary branch. Neon MCP queries run as `neondb_owner`, which has `BYPASSRLS`; actual application RLS remains enforced through the existing `lexa_app` role (`rolbypassrls = false`).

## Release gate

Before the migration is promoted to `lexa-live`, the prepared migration must be explicitly completed through the Neon migration workflow. After promotion, rerun the same schema/readiness verification against `lexa-live`.
