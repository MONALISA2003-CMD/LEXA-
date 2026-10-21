# LEXA Phase 6 Increment 01 — implementation and gate report

**Assessment date:** 21 October 2026  
**Package:** 2.10.0 / Phase 6 Increment 01  
**Status:** LOCAL SOURCE CANDIDATE — local checks pass; cloud replay, Node 24 build, authenticated staging and deployment acceptance are pending.

## Summary

This increment implements both sides of the Phase 6 request: (1) it makes the previously approved Phase 3 SQL replacement disposition authoritative in the actual gate logic, and (2) it begins Inventory Intelligence with a concrete, tenant-scoped replenishment-policy and explainable-recommendation vertical slice.

## Permanent blocker resolution

- The six source gaps from Phase 3 are formally `PERMANENTLY_REPLACED`. No additional recovery search is required by the current process. The checker verifies the exactly six full identifiers, each replacement path and SHA-256, the isolated reconstructed source manifest, and the recorded ledger identities.
- `python scripts/check_migration_sources.py --strict` passes. It explicitly reports that historical recovery is closed and replacement semantic replay is pending. The result does not claim original bytes were recovered.
- `029_phase3_runtime_privilege_surface.sql` and `031_phase3_auth_surface_rls.sql` were recovered from current GitHub `main`; bytes were verified against Git blob SHAs and SHA-256. The current read-only Neon ledger snapshot is refreshed to 31 unique full migration identity strings.
- Numeric version collisions for prefix `023` and `029` are explicitly documented. Historical ledger rows are not rewritten. Older gate checklists/reports that still describe the six files as recoverable blockers now carry an explicit supersession banner; the root README and current gate register point to the Phase 3 permanent decision.
- QA-only migration 032 is not added to canonical production replay. Migration 021 remains labelled a repair candidate, not historical-byte recovery.

## Phase 6 product implementation

- Migration `036_phase6_inventory_intelligence.sql` creates one replenishment policy per tenant/location/product variant; enforces numeric bounds, composite tenant foreign keys, forced RLS, unique scope, and least-privilege application grants.
- `apps/api/app/inventory_intelligence.py` computes the recommendation deterministically using Decimal arithmetic: available = on-hand minus reserved; net demand = max(completed sales minus completed returns, 0); daily demand = net demand/lookback; target = max(minimum available, safety stock + daily demand × (lead time + review period)); suggestion = max(target − available − inbound, 0).
- Three API endpoints configure/list policies and list advisory recommendations. They use existing inventory permissions, tenant and location scope, tracked-variant validation, audit/event records and a clear methodology string. They do not create stock movements or purchase orders.
- The Inventory workspace now includes a Replenishment tab to configure policy and read the per-location recommendation output.

## Release-gate engineering

- The replay plan validates all 40 SQL inputs and computes a canonical bundle SHA without opening a database.
- Actual replay is guarded to empty loopback databases explicitly named `replay`, `test` or `ci`; remote hosts are forbidden.
- The CI replay job applies migrations against disposable `pgvector/pgvector:pg16`, checks exact current input hashes/source SHA, all public-table RLS enabled/forced status, required Phase 5 routines, Phase 6 policy/RLS, `lexa_app` inability to mutate permissions or the ledger, and adversarial runtime-role cross-tenant read/write behavior with rollback-only fixtures.
- CI is set to use Node 24 with `npm ci`, typecheck, 28 frontend contract tests and production build. Python CI installs the declared API dev/test dependencies and provisions Redis so the auth-refresh integration cannot be skipped merely because Redis is missing.

## Local validation performed

- `python -m compileall -q apps/api/app apps/api/tests scripts`: PASS.
- `python scripts/check_migration_recovery_manifest.py`: PASS.
- `python scripts/check_migration_sources.py --strict`: PASS; 31 ledger identities, 25 canonical SQL sources, six permanent replacement decisions.
- `python scripts/run_clean_migration_replay.py --plan-only`: PASS; 40 migration input paths exist and hash cleanly; bundle SHA-256 is computed by the runner.
- Python test suites (`../../tests` and `apps/api/tests` from `apps/api`): **182 passed, 1 skipped**. The local skip is auth-refresh test collection because this offline environment lacks the installed `redis` Python package; CI provisions/install Redis and must run it.
- Frontend contract tests: **28 passed, 0 failed** under Node 22.16.0.
- `npm run typecheck`/production build not verified locally: `node_modules` and the Node 24 dependency tree are absent and npm registry DNS is unavailable. CI is required to establish Node 24 proof.

## Not performed / open release acceptance

- Clean SQL `--apply` was not performed in this offline local runtime because PostgreSQL client/server and disposable local Postgres are unavailable. CI must run it in its disposable PostgreSQL service.
- Authenticated browser E2E has not run against a sanitized isolated staging environment.
- Candidate is not committed or deployed; the current healthy Render/Vercel SHA is not evidence for this candidate.
- Production migrations 033–036 are not applied. No production SQL mutation or production deployment was performed.

## Result

Historical retrieval work for the six approved sources is closed permanently. Phase 6 Increment 01 is implemented locally and the local source/contract tests pass. Production release acceptance remains gated on successful candidate-specific cloud replay, Node 24 CI/build, staging E2E, exact-SHA deployment verification and separately approved database rollout.
