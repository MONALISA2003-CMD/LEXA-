# Phase 6 Entry Policy — authoritative as of 21 October 2026

## Permanent decisions

1. The six historical SQL files `010_phase2_catalog_intelligence`, `011_phase2_catalog_runtime_constraints`, `023_phase4_purchasing_core`, `024_phase4_purchasing_security`, `025_phase4_purchasing_permissions`, and `026_phase4_membership_branch_integrity` were declared lost and approved for permanent replacement in Phase 3. **Historical recovery is closed. Do not re-open searches or carry those six files as blockers.**
2. The files under `migrations/reconstructed/` remain labelled equivalent replacements, not recovered originals. Their hashes and approved mapping are maintained in `migrations/migration_dispositions.json`; clean replay and security validation remain a separate release gate.
3. Two additional live migration files, `029_phase3_runtime_privilege_surface.sql` and `031_phase3_auth_surface_rls.sql`, were recovered from the current GitHub `main` source and restored at their canonical paths. Their Git blob hashes, SHA-256 hashes, sizes and source identity are recorded in `migrations/source_gaps.json`.
4. Two distinct migrations share prefixes `023` and `029`. Full version identity—not an integer prefix—is the only valid identity. Never rename historical ledger entries to “fix” the collision.
5. `032_phase5_return_settlement_reconciliation` appeared on a prior QA branch, but is not in the canonical production ledger snapshot. Do not replay it as a production migration unless a separately reviewed forward migration explicitly adopts its scope.
6. `021_phase5_analytics_foundation.sql` remains a clearly labelled repair candidate, not historical-byte recovery.

## The only two migration questions

- **Historical disposition:** closed by the Phase 3 approval for the six files. This gate must not recur.
- **Forward semantic/release validation:** still pending until the exact current package successfully replays in disposable PostgreSQL and passes schema, RLS, role-permission, tenant-isolation, test, staging and deployment evidence.

## Phase 6 product scope

Canonical Phase 6 is **Inventory Intelligence**. This package's first vertical slice adds location-specific replenishment policy and deterministic, explainable advisory recommendations derived from completed sales/returns and current inventory facts. It does not create stock, transfer inventory, create or approve purchase orders, or post accounting. Purchasing is a later phase.

## Required gates for every future increment

- Python backend suite with Redis installed; required integration tests may not be skipped because CI dependencies are missing.
- Node 24 clean `npm ci`, typecheck, frontend contracts and production build.
- Fresh disposable PostgreSQL replay using the exact shipped source bundle; migration hashes and evidence tied to the exact source SHA.
- RLS enabled and forced on applicable public tables; least-privilege assertions and a runtime-role cross-tenant read/write probe with test fixtures rolled back.
- Authenticated Playwright E2E in sanitized isolated staging, with write safeguards enabled only for that environment.
- Render and Vercel same-SHA parity, readiness and critical-flow checks before release approval.
- Explicit migration plan/rollback and approval before production DDL.

## Status boundary

This is a full-source implementation candidate, not a deployment. Local tests and plan-only replay have passed, but clean SQL replay has not been run in this offline environment. Node 24 install/typecheck/build, sanitized authenticated browser acceptance, same-SHA deployment of this exact candidate, and production migration approval remain open. No production SQL or deployment changes were made in this increment.
