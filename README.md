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

## Deployment fix v0.5.2 — SQLAlchemy/psycopg3 audit

- PostgreSQL runtime is standardized on psycopg 3.
- SQLAlchemy's reserved Declarative attribute `metadata` is not used as a Python ORM attribute.
- The existing PostgreSQL column name `metadata` is preserved for products and product variants.
- Product ORM attribute: `product_metadata` → database column `metadata`.
- Product variant ORM attribute: `variant_metadata` → database column `metadata`.
- Public API request/response field remains `metadata`.
- Render root/build/start/health contract remains unchanged.
- No database reset, destructive migration, or data deletion is introduced.

### Pre-zip audit

The package must pass the complete local test suite, Python compilation, deployment contract checks, and static reserved-name/dependency audit before packaging.


## v0.6.2 deployment correction

This package corrects the v0.6.1 startup import contract: `app.main` imports only the health helper that actually exists (`check_database`). Redis is not probed by the readiness endpoint until a concrete Redis health implementation is introduced.
