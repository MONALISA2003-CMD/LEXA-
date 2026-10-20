# LEXA Phase 0–3 Closure Bundle — 20 October 2026

## Delivery state

This archive consolidates the Phase 0–2 forensic closure/evidence and a guarded Phase 3 Increment 01–03 candidate overlay. It is **not a production release**. No changes in this package have been applied to a production database or deployed service, and no remote feature branch, commit, PR or CI run was created.

## Current Phase 3 validation snapshot

The final candidate DDL was reapplied idempotently on the isolated Neon replay database `lexa_phase0_3_cleanbridge` (project `wispy-mud-75323042`, branch `br-purple-art-b1horduo`). Observed schema: 119 tables, 0 views, 1,300 columns, 446 indexes, 1,799 constraints, 116 RLS policies, 460 public functions, and 36 user triggers. Under `lexa_app`, tenant-A could read its own invitation and branch assignment but could not insert tenant-B invitation/assignment rows; temporary fixtures were deleted. This is selected isolated SQL/RLS evidence, not canonical schema parity or full application acceptance.

The Phase 3 package’s final validation ran 26 Python tests, 4 Node source-contract tests, Python compilation and TypeScript contract fixtures successfully. The pinned Node 24 base checkout (without the overlay) passed `npm ci`, typecheck, 23 existing frontend tests and production build. The **full application overlay has not yet been typechecked/built/tested as installed**, and authenticated browser E2E remains outstanding.

## Historical provenance blockers remain open

The exact historical SQL for migrations 010, 011, 023 purchasing core, 024 purchasing security, 025 purchasing permissions, and 026 membership-branch integrity remains unrecovered. Reconstructed equivalents are explicitly labelled and kept out of the expected-original file paths. The original migration 021 is malformed and is preserved untouched; a separately generated hash-guarded repair candidate requires review. The isolated replay used documented reconstructed equivalents and replay-only compatibility steps, so it does not prove exact applied-byte provenance or canonical schema parity.

## Release gates before production use

1. Recover exact original migration bytes or formally approve a reviewed forward-migration strategy that replaces the need for those original bytes; keep the strict source checker failing until that decision is evidenced.
2. Review the 004 replay-equivalent, 021 repair candidate, six reconstructed equivalents, and 005a/025a replay-only compatibility steps.
3. Run the final full migration chain from a brand-new isolated database and classify all differences against the canonical snapshot.
4. Install overlay in a clean checkout; run the dependency-complete backend suite (including Redis), full frontend Node 24 typecheck/tests/build, and authenticated browser E2E against a dedicated isolated/staging LEXA environment.
5. Implement and verify branch authorization across every branch-scoped endpoint; current candidate persists and exposes branch assignments but does not claim universal enforcement.
6. Review the least-privilege runtime-role/connection cutover, same-SHA hosted CI/PR, rollback and release approvals separately.

## Contents

- `phase3-increments-01-03/`: current guarded source-only candidate, scripts, tests, provenance manifest, validation record, and closure/acceptance matrices.
- `phase0-2-evidence/`: Phase 0–2 closure report and previous recovery/replay packages and evidence.
