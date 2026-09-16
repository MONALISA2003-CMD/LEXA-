# LEXA migrations

Apply in order. Migration 005 is additive and introduces the inventory foundation.

1. `001_phase1_foundation.sql`
2. `002_identity_rbac_organization.sql`
3. `003_rbac_sessions_organization_completion.sql`
4. `004_catalog_and_rbac_hardening.sql`
5. `005_inventory_foundation.sql`

Do not rerun migrations against an already-provisioned database unless the statements are designed to be safely repeatable. Migration 005 uses `IF NOT EXISTS`, conflict-safe permission inserts and explicit tenant constraints/RLS. It contains no `DROP TABLE`, `TRUNCATE`, product deletion or database reset.
