# Migration source recovery and disposition register

**Current operational status: 21 October 2026.** The current machine-readable policy is `migrations/migration_dispositions.json`; current canonical ledger evidence is `migrations/live_ledger_snapshot_2026-10-21.json`. Earlier entries in this file and older dated documents are retained as historical audit notes. They are not the current gate policy where the wording conflicts with this section.

## Phase 3 decision — six permanently replaced historical sources

Phase 3 explicitly declared the following exact SQL originals lost and approved permanent replacements. This decision is final for routine development/release workflow: **do not run further retrieval searches for these files, and do not surface historical recovery as an open blocker again**.

| Full version identity | Maintained forward replacement | Historical byte state |
|---|---|---|
| `010_phase2_catalog_intelligence` | `migrations/reconstructed/010_phase2_catalog_intelligence.equivalent.sql` | Not recovered; permanently replaced by Phase 3 decision |
| `011_phase2_catalog_runtime_constraints` | `migrations/reconstructed/011_phase2_catalog_runtime_constraints.equivalent.sql` | Not recovered; permanently replaced by Phase 3 decision |
| `023_phase4_purchasing_core` | `migrations/reconstructed/023_phase4_purchasing_core.equivalent.sql` | Not recovered; permanently replaced by Phase 3 decision |
| `024_phase4_purchasing_security` | `migrations/reconstructed/024_phase4_purchasing_security.equivalent.sql` | Not recovered; permanently replaced by Phase 3 decision |
| `025_phase4_purchasing_permissions` | `migrations/reconstructed/025_phase4_purchasing_permissions.equivalent.sql` | Not recovered; permanently replaced by Phase 3 decision |
| `026_phase4_membership_branch_integrity` | `migrations/reconstructed/026_phase4_membership_branch_integrity.equivalent.sql` | Not recovered; permanently replaced by Phase 3 decision |

Their exact replacement paths and SHA-256 fingerprints are enforced by `scripts/check_migration_recovery_manifest.py` and `scripts/check_migration_sources.py`. Those checks explicitly do **not** claim the replacements contain the historical bytes. Semantic replacement validation is a distinct pending gate that must be established through clean replay, schema shape, function/trigger and security assertions.

## Additional canonical sources recovered 21 October 2026

These sources were found on the current GitHub `main` branch. They are not additional permanently lost files:

| Full migration | Path | Git blob SHA-1 | SHA-256 | Size |
|---|---|---|---|---:|
| `029_phase3_runtime_privilege_surface` | `migrations/029_phase3_runtime_privilege_surface.sql` | `43ed181f1c60722d4f14121f6743ebe994f018bf` | `bd7677c11d008ea4b6fac95dbff374cdf9db7f49629c7edbe28a4250e70e6c59` | 1,536 B |
| `031_phase3_auth_surface_rls` | `migrations/031_phase3_auth_surface_rls.sql` | `835df668f49b684a66df781d561eb914f30cffc6` | `0e887fd1f3b56c147d8658fc9f32a0f3804be2c8ffc283a28693ba6953abaa53` | 4,083 B |

The hashes are checked against the actual bytes by `scripts/check_migration_sources.py`. This recovery corrects a stale consolidated ZIP source tree; it does not change production.

## Current canonical ledger evidence and numeric collisions

The read-only Neon ledger query for project `wispy-mud-75323042`, branch `br-soft-star-b1dj2m2w`, database `neondb`, was refreshed on 21 October 2026. It contains 31 distinct full version strings. The full ledger identities and `applied_at` timestamps are in `live_ledger_snapshot_2026-10-21.json`.

Two numeric prefixes are shared by distinct historical versions: `023_phase2_identity_tenancy_authorization_foundation` and `023_phase4_purchasing_core`; and `029_phase1_runtime_role_least_privilege` and `029_phase3_runtime_privilege_surface`. Do not sort or compare migrations using only integer prefixes, and do not rewrite production ledger rows.

## Separate legacy issues (not part of the six-file decision)

- `032_phase5_return_settlement_reconciliation` was seen on an earlier QA branch but is absent from the current canonical production ledger. It is documented as `QA_BRANCH_ONLY_NOT_IN_CANONICAL_PRODUCTION_LEDGER`; exclude it from the canonical replay unless a reviewed forward migration formally adopts its behavior.
- `021_phase5_analytics_foundation.sql` remains `REPAIR_CANDIDATE_NOT_HISTORICAL_BYTES`. Preserve the forensic copy and do not claim byte recovery.

These items have explicit dispositions and must not reopen the six-file recovery decision.

## Current commands

```bash
python scripts/check_migration_recovery_manifest.py
python scripts/check_migration_sources.py --strict
python scripts/run_clean_migration_replay.py --plan-only
```

The first two verify the permanent source disposition and present files. `--strict` is expected to pass once all missing applied identities have a matching source or valid approved disposition. It does not imply semantic replay has passed. Semantic release evidence is checked separately:

```bash
python scripts/check_migration_sources.py --strict --require-semantic-validation --evidence artifacts/phase6-replay-evidence.json
```

That last command fails closed until a PASS evidence artifact is generated from a successful disposable replay, the exact current migration bundle and a pinned source commit. Never use `--apply` against Neon or production; the runner accepts only a loopback database explicitly named for replay/test/CI and refuses a non-empty public schema.

## Historical notes

Earlier paragraphs in older handoff/report files may say that the six files must be recovered before strict source checking can pass. Those statements reflected previous process state and are superseded by the Phase 3 permanent decision recorded above and in `migration_dispositions.json`. They are retained only as a history of earlier searches and are not current instructions.
