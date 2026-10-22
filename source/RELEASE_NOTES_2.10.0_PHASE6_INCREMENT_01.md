# Release notes — LEXA 2.10.0 Phase 6 Increment 01

## Added
- Permanent Phase 3 dispositions for the six lost historical migration sources, enforced in strict migration source reconciliation without claiming byte recovery.
- Restored canonical migrations 029 (runtime privilege surface) and 031 (auth-surface RLS) from GitHub main with verified Git blob hashes.
- Refreshed canonical Neon ledger snapshot dated 21 October 2026, recording 31 full migration identities and the `023`/`029` prefix collisions.
- Added guarded 40-step disposable PostgreSQL semantic replay with current commit/hash-bound evidence, schema/RLS/least-privilege assertions and rollback-only cross-tenant RLS probes.
- Added Phase 6 migration 036 for tenant-scoped, per-location replenishment policies with forced RLS and least-privilege grants.
- Added deterministic demand and reorder calculations, three API endpoints and Inventory Replenishment UI.
- Updated CI for Redis-backed backend tests, Node 24 clean install/typecheck/contracts/build, disposable PostgreSQL replay and exact-source evidence validation.

## Validation
- 181 Python tests passed; one Redis-dependent auth-refresh test skipped locally because the Redis Python package could not be installed in the offline runner.
- 27 frontend contract tests passed on Node 22.16.0.
- Python compileall, replacement-manifest validation, strict source reconciliation and replay plan-only verification passed.
- Node 24 build, actual clean SQL replay, authenticated staging E2E and candidate deployment remain pending CI/staging; this is not a production release certificate.

## Safety
- No production SQL was executed and no production deployment was triggered.
- The six originals remain unrecovered; their approved permanent replacement disposition is final. Semantic replacement validation remains separately testable.
- Recommendations are advisory only and never post stock or purchasing actions.
