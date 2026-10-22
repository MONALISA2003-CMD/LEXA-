# ADR-DB-001: Permanent replacement disposition for six unrecoverable SQL sources

- **Status:** Accepted / immutable decision
- **Approved in:** Phase 3 (user-confirmed project decision; encoded in the Phase 6 gate register on 21 October 2026)
- **Decision class:** Historical provenance disposition; forward schema safety still mandatory

## Context

The exact historical SQL byte sources for six ledger identities were repeatedly searched across available project ZIPs, the connected source library and the inspected GitHub source/history. No authoritative copies were found. The project explicitly decided in Phase 3 that the six files were lost, should be permanently replaced and should no longer consume recovery effort. Later phase reports continued to describe them as blockers, which caused avoidable rework and conflicting release status.

## Decision

The six sources are formally `PERMANENTLY_REPLACED`:

- `010_phase2_catalog_intelligence` → `migrations/reconstructed/010_phase2_catalog_intelligence.equivalent.sql`
- `011_phase2_catalog_runtime_constraints` → `migrations/reconstructed/011_phase2_catalog_runtime_constraints.equivalent.sql`
- `023_phase4_purchasing_core` → `migrations/reconstructed/023_phase4_purchasing_core.equivalent.sql`
- `024_phase4_purchasing_security` → `migrations/reconstructed/024_phase4_purchasing_security.equivalent.sql`
- `025_phase4_purchasing_permissions` → `migrations/reconstructed/025_phase4_purchasing_permissions.equivalent.sql`
- `026_phase4_membership_branch_integrity` → `migrations/reconstructed/026_phase4_membership_branch_integrity.equivalent.sql`

The decision closes routine historical recovery and removes these identities as source-reconciliation blockers. The maintained replacement files remain clearly labelled as equivalents, with exact current hashes recorded and checked. The project never asserts the originals' byte contents were recovered.

## Consequences and controls

1. The `historical_recovery_gate` is `CLOSED_BY_PERMANENT_DISPOSITION` in `migrations/migration_dispositions.json`.
2. Strict source reconciliation (`python scripts/check_migration_sources.py --strict`) verifies each ledger identity has either its canonical source or a valid permanent disposition and matching replacement hash. It must not require more retrieval attempts for these six.
3. Replacement semantic validation is a separate gate. The replacement chain still must replay against an empty, disposable database and pass schema, functions/triggers, RLS, role permissions and runtime isolation tests before a candidate release qualifies.
4. New changes use new forward migrations. Applied ledger rows and migration history must not be rewritten to disguise source provenance.
5. This decision is immutable unless the project owner explicitly reverses it with a new dated ADR. Routine code review or a later phase cannot silently re-open it.

## Verification

Run `scripts/check_migration_recovery_manifest.py` and `scripts/check_migration_sources.py --strict`. Their successful result closes the historical gate only; `scripts/check_migration_sources.py --strict --require-semantic-validation --evidence ...` remains the independent semantic-release gate.
