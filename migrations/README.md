# LEXA migrations — current operating policy (21 October 2026)

## Historical source recovery is not the release gate

Phase 3 formally declared six source files lost and permanently approved equivalents. The decision is now authoritative in `migration_dispositions.json`, and the strict source reconciler validates that decision. **Do not reopen retrieval searches or mark those six historical sources as release blockers.** The replacements remain distinct artifacts and must never be mislabeled as original bytes.

The updated canonical ledger snapshot is `live_ledger_snapshot_2026-10-21.json` (31 unique full migration identities). Two additional source files, migrations `029_phase3_runtime_privilege_surface` and `031_phase3_auth_surface_rls`, were recovered from GitHub `main` and restored at their canonical paths. See `SOURCE_RECOVERY.md` for checksums and provenance. Prefixes `023` and `029` each occur twice; use the full version string, never just the prefix.

## Safe commands

From repository root:

```bash
python scripts/check_migration_recovery_manifest.py
python scripts/check_migration_sources.py --strict
python scripts/run_clean_migration_replay.py --plan-only
```

These checks validate the decision register, replacement hashes, ledger coverage, current source byte hashes and the replay input manifest. `--strict` closes the historical source-reconciliation gate; it is **not** a clean replay result.

The independent clean semantic gate runs inside CI using a disposable PostgreSQL database:

```bash
python scripts/run_clean_migration_replay.py --apply
python scripts/check_phase6_replay_evidence.py --evidence artifacts/phase6-replay-evidence.json --expected-commit "$GITHUB_SHA"
python scripts/check_migration_sources.py --strict --require-semantic-validation --evidence artifacts/phase6-replay-evidence.json
```

`--apply` requires `LEXA_ALLOW_DISPOSABLE_REPLAY=1`, a loopback-only connection string, a database name containing `replay`, `test` or `ci`, and an empty public schema. It explicitly rejects remote Neon/production targets. Each SQL file is hash-bound to the generated replay evidence. Runtime tests assert RLS enabled/forced, key Phase 5 routines, `lexa_app` reference-table least privilege, and cross-tenant read/write denial with fixtures rolled back.

## Migration identity and ledger rules

- Never delete/edit applied `schema_migrations` rows to make source history match a ZIP.
- Never edit applied migrations to silently replace their history. Use new forward migrations for approved corrections.
- Every approved equivalent or compatibility delta must be labelled, hashed and isolated under `migrations/reconstructed/`.
- `032_phase5_return_settlement_reconciliation` is documented as QA-branch-only and is not in the current canonical production ledger. Do not include it in production replay without a separate reviewed adoption decision.
- `021_phase5_analytics_foundation.sql` remains a repair candidate, not historical bytes.
- Production migrations require reviewed clean replay, security evidence, rollout/rollback steps, and explicit approval.

## Phase 6 Increment 01 — Inventory Intelligence

`036_phase6_inventory_intelligence.sql` adds per-tenant, per-location, per-variant replenishment policies with forced RLS and least-privilege grants. The advisory API computes demand from completed product sales less completed returns received at the location; it subtracts reserved and inbound quantities from availability/shortfall and shows the formula. It never posts inventory or creates/approves purchase orders. See `PHASE6_IMPLEMENTATION_REPORT_2026-10-21.md` and `PHASE6_ACCEPTANCE_MATRIX.md`.

The policy table's migration is not deployed to production in this package. Local replay plan verification has passed; execution and semantic validation remain required in CI on the exact uploaded source SHA.
