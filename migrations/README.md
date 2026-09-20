# LEXA migrations

Apply migrations in order. This repository contains the complete LEXA migration history; the release status below distinguishes source artifacts from the database branch actually updated for this package.

1. `001_phase1_foundation.sql`
2. `002_identity_rbac_organization.sql`
3. `003_rbac_sessions_organization_completion.sql`
4. `004_catalog_and_rbac_hardening.sql`
5. `005_inventory_foundation.sql` — existing inventory implementation; not deployed as part of the v1.4.0 experience release
6. `006_phase1_security_reliability.sql`
7. `007_phase2_catalog_hardening.sql`
8. `008_workspace_registration_hardening.sql`
9. `009_auth_workspace_picker.sql`

Migrations 008 and 009 are additive and have been applied to the LEXA development branch `lexa-phase1-dev`. The LEXA production branch remains untouched.

Do not rerun migrations against an already-provisioned database unless the statements are designed to be safely repeatable.
