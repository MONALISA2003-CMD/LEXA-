# LEXA — Phase 2 Catalog Slice

This package continues the existing LEXA Phase 1 foundation. It does **not** reset a database, delete business data, or reseed the whole system.

## Implemented

- Real role → permission binding (`role_permissions`)
- Owner permission backfill for existing Owner roles
- Owner receives current permissions at registration time
- Categories with hierarchy and soft delete
- Brands
- Units of measure, including global system units
- Products
- Product variants / tenant-unique SKUs
- Barcodes and deterministic lookup
- Extensible product attribute definitions and values
- Price lists
- Effective-dated product prices with overlap protection at the application boundary
- Fast catalog lookup for POS/search flows
- Catalog audit records
- Catalog transactional outbox events
- Tenant-safe composite foreign keys where practical
- Catalog RLS

## API

All endpoints are under `/api/v1/catalog` and require `catalog.read` or `catalog.manage` as appropriate.

## Production safety

Catalog mutations create their audit record and outbox event in the same SQL transaction as the catalog change. Historical catalog references use soft deletion rather than destructive deletion.

## Workflow package extraction

The included `.github/workflows/lexa-zip-extract.yml` expects future implementation ZIPs under `incoming/`. It safely extracts them, optionally deletes explicitly listed obsolete paths from `DELETE.txt` or `.lexa-delete`, removes the processed ZIP, and commits the result.
