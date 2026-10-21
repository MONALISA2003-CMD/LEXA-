# Migration source-loss decision and accepted replacements — 2026-10-21

The project owner has declared the original historical SQL bytes for six already-applied migration identities lost and has approved labelled equivalents as the forward source of record. No replacement is represented as byte-identical to the original SQL.

| Full migration identity | Replacement source | Status |
|---|---|---|
| `010_phase2_catalog_intelligence` | `migrations/010_phase2_catalog_intelligence.sql` | Accepted labelled replacement; SHA-256 pinned in `migrations/source_gaps.json` |
| `011_phase2_catalog_runtime_constraints` | `migrations/011_phase2_catalog_runtime_constraints.sql` | Accepted labelled replacement; SHA-256 pinned in `migrations/source_gaps.json` |
| `023_phase4_purchasing_core` | `migrations/023_phase4_purchasing_core.sql` | Accepted labelled replacement; SHA-256 pinned in `migrations/source_gaps.json` |
| `024_phase4_purchasing_security` | `migrations/024_phase4_purchasing_security.sql` | Accepted labelled replacement; SHA-256 pinned in `migrations/source_gaps.json` |
| `025_phase4_purchasing_permissions` | `migrations/025_phase4_purchasing_permissions.sql` | Accepted labelled replacement; SHA-256 pinned in `migrations/source_gaps.json` |
| `026_phase4_membership_branch_integrity` | `migrations/026_phase4_membership_branch_integrity.sql` | Accepted labelled replacement; SHA-256 pinned in `migrations/source_gaps.json` |

## Release rule

The six missing-path gaps are closed by the accepted replacement files. Historical byte provenance is permanently recorded as lost. The strict source checker verifies path coverage, explicit banners, and replacement checksums. Release still requires a clean-database replay and schema parity comparison against the live Neon schema; source presence alone is not proof of parity.
