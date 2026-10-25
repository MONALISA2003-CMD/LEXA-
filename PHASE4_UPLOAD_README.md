# LEXA Phase 4 — GitHub upload source overlay

**Base:** `main` at `ecba17f2fd1c5c9ca30253d203f5de92bb0e52fb`.

## Phase 4 deliverables

- Reporting periods: today, yesterday, this week, last 7 days, last 30 days, this month, last month, year-to-date and custom ranges (inclusive dates, validated, maximum 366 days).
- Reporting date from LEXA's tenant-timezone-aware `public.lexa_business_date(now(), tenant_id)`.
- Period-scoped sales, payment entries and gross profit, with gross profit sourced from saved product-margin metrics. Missing margin history remains unavailable, not a fabricated zero.
- Connected intelligence panels for top products, branch performance, customer purchase frequency, customer receivables, supplier payables/credits, current stock risk and existing restock recommendations.
- Existing links to the deterministic daily brief and demand forecast.
- Regression tests for calendar ranges, year/leap boundaries, read-only summaries, branch assignment access, gross-profit data provenance and tenant business date.

## Safety and scope

- Branch summaries require `analytics.read`, filter to active assigned branches, are tenant- and currency-scoped, read-only, and bounded to 366 days.
- Workspace-wide insights retain their full-branch-scope guard. Customer and supplier balances call existing APIs whose server handlers enforce membership/branch scope.
- No migrations, production database writes, payment gateway/mobile-money API, EFRIS submission, external AI calls, or automatic business actions were added.
- The existing 56-day forecast readiness gate is unchanged.

## Upload instructions

Upload this single ZIP at the repository root on **`main`**. The existing LEXA ZIP Extractor can recognize these canonical file paths, extract the overlay, remove the uploaded archive and invoke Main Build CI.

The three unchanged marker files are included for the extractor only: `apps/web/package.json`, `apps/api/app/main.py`, and `migrations/047_analytics_forecast_history_backfill.sql`.

Fast checks completed in the isolated source checkout: 4 frontend period/UI contract tests passed; Python compile passed; 3 API source-contract assertions passed; `git diff --check` passed; archive integrity is verified. Full pytest could not be run because pytest is absent from this temporary sandbox. Full frontend typecheck, complete test suites, production build and production smoke checks are intentionally deferred to the production checkout as requested.
