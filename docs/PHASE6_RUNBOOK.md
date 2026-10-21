# Phase 6 Increment 01 runbook

## Local read-only validation

Run from repository root:

```bash
python -m compileall -q apps/api/app apps/api/tests tests scripts
python scripts/check_migration_recovery_manifest.py
python scripts/check_migration_sources.py --strict
python scripts/run_clean_migration_replay.py --plan-only
```

The first three commands validate source integrity and the Phase 3 permanent disposition. Plan-only replay validates all 40 ordered SQL inputs and their hashes without connecting to a database.

## Required CI flow

On the exact candidate commit, CI installs Python test dependencies and Redis, runs all backend tests, validates source disposition and input hashes, installs Node 24 dependencies with `npm ci`, runs typecheck/frontend contracts/build, and applies the 42-step candidate replay against the workflow's disposable `pgvector/pgvector:pg16` database. The replay emits `artifacts/phase6-replay-evidence.json` plus a SHA-256 sidecar. `check_phase6_replay_evidence.py` rejects evidence from a different commit, changed SQL bundle, incomplete step list, missing RLS/permission checks or missing rollback-only runtime tenant-isolation assertions.

The `ci-gate-evidence` job emits a second exact-SHA CI summary. Even a `PASS_CI_CANDIDATE_GATES` record explicitly leaves production release acceptance false; it does not cover authenticated staging E2E, deployment parity or production rollout approval.

## Hosted staging acceptance

Before write-enabled Playwright acceptance, provision an isolated, sanitized non-production stack. It must have its own disposable PostgreSQL database and Redis/cache, no production credentials/data, an authenticated test tenant, and deterministic seeded inventory/product/sales/returns fixtures. Set the staging-write flag only for this environment and supply the storage state using the existing E2E safety contract. Never point these tests at the production Render origin or Neon production branch.

Required journey: set a replenishment policy → read advisory recommendations → adjust source sales/returns fixture → confirm recalculated net demand → verify location/tenant scoping → verify inventory balances and ledger are unchanged by recommendation reads. Also run sales/return integration acceptance from the Phase 5 suite.

## Promotion

Only after all required CI jobs and sanitized staging acceptance pass:

1. Capture source commit, ZIP checksum, replay artifact checksum and test artifacts.
2. Review migrations 033–036 against the exact replay-tested source SHA; prepare rollback/backout instructions and backup evidence.
3. Obtain explicit production migration approval. Apply only the approved forward SQL migrations to production—never run the clean-replay script against Neon.
4. Deploy that exact SHA to Render and Vercel using CI-controlled promotion. Verify SHA parity, `/health`, `/ready`, and protected business-flow smoke tests.
5. Archive the resulting evidence and update the generated release-gate record. If a candidate gate fails, fix forward and rerun against the new source SHA; never carry a green result across commits.
