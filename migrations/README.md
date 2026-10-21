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

Six exact source gaps remain tracked in `source_gaps.json`: `010`, `011`, and the historical purchasing/security/permissions/branch-integrity versions `023_phase4_purchasing_core` through `026_phase4_membership_branch_integrity`. `019_phase4a_customer_credit_allocation` and `027_release_convergence` have been recovered from tracked GitHub source artifacts with their blob hashes verified; see `SOURCE_RECOVERY.md`. The 027 recovery narrows the gap count but does not prove full replay or provide a database-side checksum of previously applied bytes. Do not infer missing SQL from version names or current schema. In the live ledger, two distinct migrations share numeric prefix `023`; migration identity must always use the full version string.

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

`022_phase6a_brain_foundation.sql` now contains corrected dynamic policy naming and quoted empty-string handling. This fixes the source defect for future validation; it is **not** proof that a fresh full migration replay succeeds. The corrected policy-creation block was validated against the seven existing Brain tables on the disposable `lexa-convergence-test-2026-10-08` branch. This verifies that dynamic SQL block, not a full from-zero migration replay; validate the complete chain only after the six remaining exact historical migration sources are recovered.

## Phase 5 Increment 03 — settlement/returns candidate (21 October 2026)

The working tree adds three additive candidate migrations after the current production baseline:

- `033_phase5_refund_settlement_consistency.sql` — derives net collected value from gross recorded allocations less recorded refunds, refreshes sale totals when refund ledger rows change, and makes analytics use the authoritative `sales.amount_due` value.
- `034_phase5_return_accounting_journals.sql` — posts idempotent return settlement and returned-inventory COGS journals, maps account `2210` as the customer store-credit liability, and creates a pending EFRIS credit note/event for active registered tenants.
- `035_phase5_none_return_receivable_guard.sql` — protects both direct database callers and the API path from a no-refund/no-credit return whose value exceeds the outstanding receivable.

These sources are **new additive candidates**, not recovered historical byte sources. Their functions/triggers and account mapping were installed and inspected on Neon QA branch `br-young-base-b1mi15fs`; RLS disabled/not-forced counts were zero and the branch had zero sales/journal-entry rows after the DDL review. This QA branch is a parented copy, not a sanitized staging database. The production `lexa-live` branch remains at migration 031; migrations 033–035 have not been promoted to production.

A previous QA branch ledger contains a `032_phase5_return_settlement_reconciliation` record, but the corresponding SQL file is not present in this repository. This report does not treat that version as a production-applied source or claim historical byte parity. The increment 03 migrations supply the reviewed replacement function behavior. The historical six-source gap list is preserved as exactly six items in `source_gaps.json`; full from-zero replay still cannot be claimed.

`021_phase5_analytics_foundation.sql` is also a clearly-labelled repair candidate: the inspected GitHub-read copy had malformed escaped newlines and an appended non-SQL trailer. The package's version has a clean SQL shape and uses `sales.amount_due` for authoritative receivable projections, but is not the original historical bytes and must not be represented as recovered source parity.
