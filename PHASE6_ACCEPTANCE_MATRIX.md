# Phase 6 Increment 01 acceptance matrix — 21 October 2026

## Implemented in candidate source

| Requirement | Implementation | Local result |
|---|---|---|
| Permanent Phase 3 lost-source disposition | Machine-readable `migration_dispositions.json`, `source_gaps.json`, source checker and recovery-manifest checker | PASS |
| Prevent recurrence in operational documentation | Root README is Phase 6-current; older gate/checklist snapshots that mention source recovery carry explicit supersession notices | PASS |
| Recover newer applied sources from canonical repository | Recovered `029_phase3_runtime_privilege_surface.sql`, `031_phase3_auth_surface_rls.sql`; git blob hashes match | PASS |
| Refresh current canonical ledger baseline | 31 full identity rows in dated ledger snapshot | PASS (read-only provider query) |
| Track prefix collisions correctly | Exact collisions for `023` and `029`; full string identities | PASS |
| Strict source reconciliation | `python scripts/check_migration_sources.py --strict` | PASS (does not claim replay) |
| Recovery manifest and hash integrity | `python scripts/check_migration_recovery_manifest.py` | PASS |
| Replay source bundle | `python scripts/run_clean_migration_replay.py --plan-only` | PASS, 40 inputs hash-checked |
| Phase 6 recommendation math | Deterministic Decimal helper; validates inputs, returns and inbound/reserved stock | PASS in unit tests |
| Phase 6 API | Policy GET/PUT and advisory recommendations GET; role/tenant/location scoping, audit/event | Static contract and test suite pass; DB behavior awaits replay/E2E |
| Phase 6 database schema | Migration 036, composite tenant FKs, unique key, forced RLS, least-privilege grants | Static contract passes; SQL replay pending |
| Frontend | Inventory Replenishment tab, policy configuration and explainable recommendation list | 28 frontend contracts pass; Node 24 build pending |
| Backend suite | Python tests | 182 passed, 1 skipped locally because Redis Python package cannot be installed offline |
| Python syntax | `compileall` apps/api/app, tests and scripts | PASS |

## Release gates not yet proven

| Gate | Status | Evidence needed |
|---|---|---|
| Full backend CI including Redis test | PENDING CI | CI must install declared Redis dependency and run every required test without dependency-driven skips |
| Node 24 `npm ci`, typecheck and production build | PENDING CI | CI result on same source SHA; local runner uses Node 22 and registry DNS is unavailable |
| Clean semantic SQL replay | PENDING CI | The 40-step migration chain must apply successfully in empty disposable PostgreSQL, then pass postconditions |
| Runtime-role adversarial RLS probe | PENDING CLEAN REPLAY | Confirm cross-tenant settings are invisible/unwritable to `lexa_app`; all fixtures rolled back |
| Authenticated inventory browser E2E | NOT RUN | Requires sanitized isolated staging and explicit staging write enablement |
| Render/Vercel exact-SHA deployment parity for candidate | NOT RUN | This package is not committed/deployed; current healthy baseline is not this source candidate |
| Production database migration rollout | NOT APPLIED | Separate approval, backups, reviewed rollout/rollback, and successful candidate evidence required |

## Decisions that must not recur

- The six Phase 3 source recovery tasks are `PERMANENTLY_REPLACED`, with recovery closed. Their absence is not an open blocker.
- The separate QA-only 032 ledger entry is excluded from canonical production replay.
- Migration 021 is explicitly a repair candidate, not original historical SQL.

## Candidate acceptance boundary

This package makes Phase 6 non-destructive development possible. It is not a release acceptance certificate. A CI clean replay failure must fail the job and preserve the failure artifact; no one may override it by relabelling the historical-source decision.
