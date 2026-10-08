# LEXA migrations

Apply migrations in order. This repository contains the complete LEXA migration history included in the current source package.

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

## Canonical live database for this release

- Neon project: `wispy-mud-75323042`
- Neon branch: `lexa-live` (`br-soft-star-b1dj2m2w`)
- Database: `neondb`

Migrations `015` through `021` are recorded on that canonical branch.

Do not run destructive or unrelated database changes. Phase 4A, Phase 4B and Phase 5 are additive, tenant-scoped, and RLS protected. The Universal Business Engine remains internal technical infrastructure and is not exposed as a product module.
