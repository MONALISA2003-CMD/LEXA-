# LEXA migrations and source-of-truth controls

## Important safety boundary

This directory is **not yet a complete from-zero replay bundle**. Do not reset Neon, blindly replay the SQL files, or reconstruct missing migrations from table names. The canonical live database contains historical migrations whose exact SQL is not present in this package. Unknown applied SQL must be recovered from an authoritative commit/artifact or formally documented as unrecoverable before schema-changing work.

The historical read-only ledger snapshot in `live_ledger_snapshot_2026-10-13.json` records the 13 October state. The current snapshot, `live_ledger_snapshot_2026-10-15.json`, was refreshed from canonical Neon `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`, on 15 October 2026. Both are audit evidence, not live database credentials or deployment instructions; re-query before any migration action.

## Source coverage

Run:

```bash
python scripts/check_migration_sources.py
```

The checker verifies that every observed ledger version either has a matching `*.sql` source or a documented source-gap entry. Use `--strict` to fail while any source gap remains. CI should run the non-strict reconciliation check to ensure the gaps stay visible; production readiness remains blocked until the strict check passes in a disposable database/replay environment.

The current seven source gaps are tracked in `source_gaps.json`: migration versions `010`, `011`, the purchasing/security versions under the `023`–`026` prefix, and `027_release_convergence`. Version `019_phase4a_customer_credit_allocation` has been recovered byte-for-byte from historical GitHub commit `d850ce04c8930134f01a63cd65c5d1947a17b17d`; see `SOURCE_RECOVERY.md`. Do not infer missing SQL from version names or current schema. In the live ledger, two distinct migrations share numeric prefix `023`; migration identity must always use the full version string.

## Safe validation sequence

1. Re-query `public.schema_migrations` on the canonical branch and compare it with the checked-in snapshot.
2. Recover missing SQL from the exact historical source/package that was applied; verify checksums or reviewed diffs where available.
3. Resolve the duplicate numeric prefix in migration tooling without renaming historical ledger records on the live database.
4. Run the complete ordered chain against a disposable Neon branch/database and verify tables, functions, grants, RLS policies, indexes, and constraints.
5. Only after review and explicit approval should a separate planned migration be applied to canonical Neon. Phase 0 UX/auth code changes do not need to mutate the live schema.

## Canonical live database for this release

- Neon project: `wispy-mud-75323042` (`LEXA`)
- Neon branch: `lexa-live` (`br-soft-star-b1dj2m2w`)
- Database: `neondb`

## Phase 0 authentication migration

`028_phase0_auth_rls_runtime_hardening.sql` is the additive Phase 0 hardening migration. It creates the narrowly scoped SECURITY DEFINER lookup for opaque refresh-token hashes, hardens known empty tenant-context RLS predicates, assigns the least-privilege `Member` role only to already-active memberships that have no role, and records its migration version. The live ledger and function/grant/owner properties were re-verified read-only on 15 October 2026. Do not rerun it on production as a substitute for deployment verification.

`022_phase6a_brain_foundation.sql` now contains corrected dynamic policy naming and quoted empty-string handling. This fixes the source defect for future validation; it is **not** proof that a fresh full migration replay succeeds. The corrected policy-creation block was validated against the seven existing Brain tables on the disposable `lexa-convergence-test-2026-10-08` branch. This verifies that dynamic SQL block, not a full from-zero migration replay; validate the complete chain only after exact historical migration sources are recovered.
