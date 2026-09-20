# LEXA — Inventory foundation v0.8.0

LEXA is being implemented as a real multi-purpose, multi-tenant SaaS business operating system. This package continues the existing implementation; it does not rebuild the application or reset business data.

## Phase 3 implemented

- Immutable inventory ledger
- Rebuildable inventory balances
- Weighted-average inventory cost by location
- Stock availability and inbound quantities
- Stock adjustments: DRAFT → APPROVED → POSTED
- Stock counts: COUNTING → SUBMITTED → APPROVED → POSTED
- Transfers: DRAFT → APPROVED → DISPATCHED → PARTIALLY_RECEIVED/RECEIVED → COMPLETED
- Idempotent command handling
- Audit + transactional outbox events
- Tenant consistency and RLS
- Inventory integrity check
- Live Inventory frontend workspace

## Frontend

The Inventory workspace is connected to real authenticated tenant APIs. It does not populate fake inventory records. It provides:

- Stock by location
- Immutable ledger history
- Controlled adjustments
- Physical counts and variance review
- Transfer workflow
- Location setup

The UI is intentionally business-facing. Infrastructure diagnostics remain limited to the small system-status area used during the implementation/deployment stage.

## Migration

`migrations/005_inventory_foundation.sql` is additive. It does not delete products, reset the database, truncate tables, or reseed existing business data.

## Validation

The package includes unit/contract checks for the inventory migration, API contract, domain invariants and live-data-only frontend behavior.
