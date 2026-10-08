> **Release status:** Phase 3 Inventory Foundation is implemented in source, validated on an isolated LEXA Neon branch, and the additive migration is now applied to canonical `lexa-live` in LEXA PostgreSQL.

# LEXA Phase 3 — Inventory Foundation

This phase adds the operational inventory execution layer to the existing LEXA catalog and Universal Business Engine.

## Scope

- immutable inventory ledger
- rebuildable materialized balances
- weighted-average cost per inventory location
- stock availability and inbound quantities
- controlled stock adjustments with DRAFT → APPROVED → POSTED
- stock counts with DRAFT/COUNTING → SUBMITTED → APPROVED → POSTED
- location-to-location transfers with DRAFT → APPROVED → DISPATCHED → PARTIALLY_RECEIVED/RECEIVED → COMPLETED
- command idempotency
- audit and transactional outbox records
- tenant isolation and tenant-consistency foreign keys
- read-only ledger/balance integrity checking
- controlled balance rebuild command
- visible frontend inventory workspace

## Accounting/inventory behavior

`inventory_transactions` is the immutable historical source of truth. `inventory_balances` is a rebuildable materialized projection.

Inbound stock uses weighted-average cost. Outbound movements use the location's current average cost at the time of issue. Transfer cost is captured at dispatch and reused at destination receipt.

Committed negative stock is blocked. Reserved quantity remains a separate projection field for future reservation workflows.

## Database security

All nine Phase 3 tables use forced tenant RLS. Tenant-consistency composite foreign keys prevent cross-tenant location and product-variant references. The inventory ledger is append-only through both privilege revocation and a database trigger.

## Commands

Every state-changing inventory command accepts `Idempotency-Key`. Reusing a key with a different request is rejected.

## Frontend

The Inventory workspace uses authenticated tenant APIs and live database data. It does not fabricate stock quantities, movements or products.

## Migration

Current live-series migration: `014_phase3_inventory_foundation.sql`. It is additive and does not reset, truncate, reseed or delete existing business data.
