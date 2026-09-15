# LEXA Migrations

Migrations are version-controlled, deterministic, reviewed, additive/non-destructive by default, and tested against representative data.

## Order

1. `001_phase1_foundation.sql`
2. `002_identity_rbac_organization.sql`
3. `003_rbac_sessions_organization_completion.sql`
4. `004_catalog_and_rbac_hardening.sql`

`004` introduces Catalog and repairs the original Phase 1 permission model by adding the explicit `role_permissions` relation.

For Neon production, use the direct/unpooled database connection for schema migrations. Test the migration on a Neon branch before promotion.
