# LEXA Phase 4 closeout candidate

**Target base:** the accepted `LEXA_PHASE3_FINAL_CUTOVER_2026-10-21.zip` or a newer reconciled copy of that source.

## Important source-alignment warning

This package is a candidate source overlay, not a safely rebased drop-in for arbitrary `main`. The three API route files (`commerce.py`, `inventory.py`, `analytics.py`) include preserved API source-overlay code in addition to Phase 4 changes and do not byte-match the GitHub `main` blobs currently available to the connected reader. Compare/merge those paths against the exact accepted Phase 3 final-cutover ZIP before committing. `apps/api/app/main.py` and schema migrations are intentionally not part of this package: keep the accepted Phase 3 router mounts and migration `031_phase3_auth_surface_rls.sql` intact.

## ZIP contents and constraints

- Entries use repo-relative paths with no enclosing top-level folder.
- No `.env`, production secrets, GitHub workflow files or migration files are included.
- The package includes Phase 4 dashboard/analytics UI, inventory summary, product-summary aggregation, regression contracts, KPI definitions, source reconciliation and closeout status.

## Run gates before deployment

Use an authorized Node 24 environment:

```bash
cd apps/web
node --version                 # must report v24.x
npm ci
npm run typecheck
npm test
npm run build
```

Then install Playwright as a direct dev dependency through an authorized lockfile update; run the opt-in authenticated acceptance test with a non-production QA storage state against a preview URL. Complete the acceptance matrix before promoting any release.

**Disposition:** Phase 4 code candidate prepared; source merge, clean Node 24 build and authenticated preview acceptance remain pending. No deployment has been made.
