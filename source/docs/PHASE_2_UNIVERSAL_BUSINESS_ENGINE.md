# LEXA Strategic Phase 2 — Universal Business Engine

This implementation builds the universal business engine on top of the existing LEXA Business Kernel, Catalog and Inventory layers.

## Scope

- business capabilities and tenant configuration;
- universal party relationships;
- configurable transaction types and status transitions;
- transaction lines and immutable status history;
- reusable workflow definitions, steps, instances and step runs;
- authorized business context assembled from transactional truth;
- explicit permissions, RLS, audit and outbox integration;
- mobile-friendly operations workspace at `/business-engine`.

## Key rules

1. PostgreSQL transactional records remain authoritative.
2. Every new table is tenant-scoped and forced through RLS.
3. Transaction status transitions must be defined by the transaction type.
4. Status history is append-only.
5. Transaction line references are tenant-safe through composite foreign keys.
6. Workflow runs create auditable work items for task/approval steps.
7. Context is a read model over authorized records, not a second source of truth.
8. New workspace registrations receive the seeded capability/configuration/transaction type layer through the same database defaults.

## API

`/api/v1/business-engine/capabilities`

`/api/v1/business-engine/configuration`

`/api/v1/business-engine/relationships`

`/api/v1/business-engine/transaction-types`

`/api/v1/business-engine/transactions`

`/api/v1/business-engine/workflows/definitions`

`/api/v1/business-engine/workflows/instances`

`/api/v1/business-engine/context/{entity_type}/{entity_id}`

## Exit criteria

- a tenant can enable/configure capabilities without schema changes;
- parties can be related without duplicate identities;
- universal transactions support lines, lifecycle transitions and history;
- workflows can be defined, started and advanced with durable records;
- the context endpoint can reconstruct authorized business context from the kernel;
- cross-tenant references are rejected at database level;
- all Phase 1 and earlier tests remain green.
