# Applying the Phase 4 closeout overlay

**Target base:** `LEXA_PHASE3_FINAL_CUTOVER_2026-10-21.zip` (or a newer reconciled copy of that Phase 3 final-cutover source).  
**Do not apply to:** an older raw project ZIP while discarding the accepted Phase 3 final-cutover files.

## Phone-friendly ZIP extraction workflow

1. Keep a backup copy of the accepted Phase 3 final-cutover ZIP.
2. Upload/extract this Phase 4 overlay ZIP **into the same repository root** using the existing LEXA ZIP extractor workflow. ZIP entries are repo-relative paths; there is no enclosing top-level folder.
3. The overlay replaces only the listed Phase 4 source/test/doc paths. It intentionally contains no `.env`, production secrets, schema migration files or GitHub workflow paths. Unlisted Phase 3 files—including migration `031_phase3_auth_surface_rls.sql`—are not removed.
4. After the overlay lands, run clean Node 24 install, typecheck, contract tests and production build in CI/preview; see `PHASE4_RELEASE_ACCEPTANCE_MATRIX.md`.
5. Do not promote to production until authenticated non-production browser acceptance passes against the same candidate and frontend/backend source revisions are aligned.

## What changed

- Added a currency-aware sales dashboard response: completed sales and credit are separated from payments recorded for the business date.
- Added `/api/v1/inventory/summary`, which aggregates every inventory balance in the user's authorized locations and returns a small, bounded low/out-of-stock attention list.
- Added range-aggregated product metrics and dashboard charts with an accessible SVG title/description and tabular data alternative.
- Added regression contracts, KPI definitions, source reconciliation, release acceptance and closeout documentation.

The overlay is a controlled-release candidate, not a claim that the not-yet-run Node 24 build, authenticated browser E2E or deployment gates passed.
