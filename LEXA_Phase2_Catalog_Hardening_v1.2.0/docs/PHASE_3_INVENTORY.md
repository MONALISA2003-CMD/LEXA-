# LEXA Phase 3 — Inventory Foundation

This phase adds the real inventory transaction layer to the existing LEXA implementation.

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
- visible frontend inventory workspace

## Accounting/inventory behavior

The balance is not the historical source of truth. `inventory_transactions` is the immutable history. `inventory_balances` is a rebuildable projection.

Inbound stock uses weighted-average cost. Outbound movements use the location's current average cost at the time of issue. Transfer cost is captured on dispatch and reused at destination receipt.

Committed negative stock is blocked. Reserved quantity is retained as a separate field for future reservation workflows; the current inventory foundation does not silently create reservations.

## Commands

Every state-changing command accepts `Idempotency-Key`. Reusing a key with a different request is rejected. Successful command results are stored so a retry can return the original result without repeating the business mutation.

## Frontend

The Inventory workspace is intentionally connected to live authenticated tenant APIs. It does not generate placeholder products, quantities, balances or movements.

Tabs:

- Stock
- Ledger
- Adjustments
- Counts
- Transfers
- Locations

The UI exposes operational state and workflow actions while keeping infrastructure details out of normal business screens.

## Migration

Apply `migrations/005_inventory_foundation.sql` after the existing catalog migration. It is additive and contains no data reset, table drop, truncate, or reseed operation.
