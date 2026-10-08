# LEXA migrations

Apply migrations in order. The repository and production database are converged through the release-contract migration below.

- 001–022: existing foundation, inventory, commerce, accounting, analytics and Brain migrations
- 023: identity, tenancy, invitation and branch-authorization foundation
- 023_phase4_purchasing_core: historical live purchasing lineage retained as a recorded migration marker
- 024_phase4_purchasing_security: historical live purchasing lineage marker
- 025_phase4_purchasing_permissions: historical live purchasing lineage marker
- 026_phase4_membership_branch_integrity: historical live branch-integrity lineage marker
- 027_release_convergence: additive schema parity, readiness contract and analytics correctness patch

## Canonical live database

- Neon project: `wispy-mud-75323042`
- Neon branch: `lexa-live` (`br-soft-star-b1dj2m2w`)
- Database: `neondb`

The live branch contains both the repository identity migration marker (`023_phase2_identity_tenancy_authorization_foundation`) and the historical purchasing markers `023_phase4_purchasing_core` through `026_phase4_membership_branch_integrity`. Migration numbers were never reused in-place; `027_release_convergence.sql` is the canonical additive convergence point.

All convergence changes are non-destructive, tenant-scoped and RLS protected.
