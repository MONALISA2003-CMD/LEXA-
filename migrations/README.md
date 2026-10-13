# LEXA migrations

Apply migrations in order. This directory contains the historical SQL migration files included in this source package; it is **not a complete from-zero replay bundle**. The live ledger includes several historical versions whose SQL files are not present here. Always verify `public.schema_migrations` and the canonical branch before any change; do not replay every file against an existing production database.

1. `001_phase1_foundation.sql`
2. `002_identity_rbac_organization.sql`
3. `003_rbac_sessions_organization_completion.sql`
4. `004_catalog_and_rbac_hardening.sql`
5. `005_inventory_foundation.sql`
6. `006_phase1_security_reliability.sql`
7. `007_phase2_catalog_hardening.sql`
8. `008_workspace_registration_hardening.sql`
9. `009_auth_workspace_picker.sql`
10. `012_phase1_business_kernel.sql`
11. `013_phase2_universal_business_engine.sql`
12. `014_phase3_inventory_foundation.sql`
13. `015_financial_architecture_lock.sql`
14. `016_phase4a_sales_payments_reconciliation.sql`
15. `017_phase4a_reconciliation_engine.sql`
16. `018_phase4a_application_integrity.sql`
17. `019_phase4a_customer_credit_allocation.sql`
18. `020_phase4b_accounting_efris_foundation.sql`
19. `021_phase5_analytics_foundation.sql`
20. `022_phase6a_brain_foundation.sql`
21. `028_phase0_auth_rls_runtime_hardening.sql`

## Canonical live database for this release

- Neon project: `wispy-mud-75323042`
- Neon branch: `lexa-live` (`br-soft-star-b1dj2m2w`)
- Database: `neondb`

Migrations through `027_release_convergence` were recorded on that canonical branch at the 2026-10-13 audit. Migration `028_phase0_auth_rls_runtime_hardening` was absent and has been tested on a temporary branch only; it has not been applied to the canonical branch.

Do not run destructive or unrelated database changes. Phase 4A, Phase 4B and Phase 5 are additive, tenant-scoped, and RLS protected. The Universal Business Engine remains internal technical infrastructure and is not exposed as a product module.


## Phase 0 final hardening (migration 028)

`028_phase0_auth_rls_runtime_hardening.sql` adds a narrowly scoped security-definer lookup for opaque refresh-token hashes, makes tenant/user RLS predicates fail closed for empty transaction-local settings, and assigns a least-privilege read-only `Member` role only to already-active memberships that have no role. It does not attach users to tenants, grant Owner/Admin privileges, reset data, or change secrets. The API now checks that migration 028, its SECURITY DEFINER function, the `lexa_app` execute grant, and an RLS-bypassing function owner are present before `/ready` reports success. Review the live ledger and apply this migration once to the canonical Neon branch before deploying the backend that calls the new function.
