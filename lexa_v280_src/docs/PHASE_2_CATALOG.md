# LEXA Phase 2 — Catalog

## Scope

This slice implements the first production catalog layer required by the LEXA specification:

- categories with hierarchy;
- brands;
- units of measure;
- products;
- product variants and unique tenant SKUs;
- barcodes and deterministic lookup;
- extensible attribute definitions/values;
- price lists and product prices;
- audit records;
- catalog events through the transactional outbox.

The product model deliberately separates Product → Category/Brand/Attributes → Variants → SKU/Barcode/Pricing, allowing unrelated industries to use different attributes without schema changes.

## Security correction

Phase 2 also hardens the Phase 1 RBAC implementation. Permission checks now require an explicit `role_permissions` binding rather than merely finding a role and a permission code. Existing `Owner` roles are backfilled to all currently defined permissions.

## Critical invariants

- SKU uniqueness is tenant-scoped.
- Active barcode lookup must resolve to one tenant variant.
- Multiple barcodes can point to one variant.
- Fractional quantity is only allowed when the base unit allows fractions.
- Product/category/brand/variant references are tenant-checked.
- Reference data is soft-deleted where historical references may remain.
- Catalog changes generate audit entries and outbox events in the same transaction.
- Global system units are readable by tenants but are not tenant-owned.

## API groups

`/api/v1/catalog/categories`
`/api/v1/catalog/brands`
`/api/v1/catalog/units`
`/api/v1/catalog/products`
`/api/v1/catalog/variants`
`/api/v1/catalog/barcodes/{barcode}`
`/api/v1/catalog/attribute-definitions`
`/api/v1/catalog/attribute-values`
`/api/v1/catalog/price-lists`
`/api/v1/catalog/prices`

## Next

Inventory is the next major domain. It must build on this catalog identity, with the immutable inventory ledger remaining historical truth and balances remaining rebuildable projections.
