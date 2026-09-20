# LEXA Phase 2 — Catalog Hardening Status

## Target

LEXA Neon development branch `lexa-phase1-dev` only. Production remains untouched.

## Implemented

- Tenant-scoped Categories, Brands, Units, Products, Product Variants/SKUs, Barcodes, Attribute Definitions/Values, Price Lists and Product Prices.
- Composite tenant-consistency foreign keys for catalog relationships.
- Partial active-record uniqueness for reusable soft-deleted identities.
- Database-level category cycle protection.
- Database-level variant/base-unit fractional quantity protection.
- Database-level price interval overlap protection with PostgreSQL exclusion constraints.
- Forced RLS across all tenant-owned catalog tables.
- Global system units readable by tenants but not writable as system data.
- Catalog permissions bound through the Phase 1 role-permission model.
- Catalog idempotency foundation and product/variant mutation integration.
- Catalog outbox emission corrected to the deployed Phase 1 outbox schema rather than introducing a second outbox contract.
- Real Products workspace connected to tenant catalog APIs; no fabricated catalog records.

## Verification

- Phase 2 migration recorded as `007_phase2_catalog_hardening` on the LEXA development branch.
- Production branch verified to have zero application tables after Phase 2 work.
- RLS and forced-RLS flags verified on all ten catalog tables.
- Cross-tenant read isolation verified using the restricted `lexa_app` role.
- Cross-tenant foreign-key rejection verified.
- Fractional-unit invariant verified.
- Category-cycle invariant verified.
- Overlapping-price invariant verified.
- System units verified.
- Local Python test suite: 29 passed for the Phase 2 verification set.
- Frontend production build could not be executed in this environment because the package's Node dependencies were not installed and `npm install` timed out; source-level product contract checks remain included.

## Explicitly not applied

Inventory migration `005_inventory_foundation.sql` was not applied by Phase 2. Inventory remains the next domain layer and must build on the hardened catalog identity.
