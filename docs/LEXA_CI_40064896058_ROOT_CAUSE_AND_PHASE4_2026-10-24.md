# CI run 40064896058: permanent source-level contract fix and next intelligence increment

**Repository:** `MONALISA2003-CMD/LEXA-`  
**Target:** `main`  
**Incident:** https://github.com/MONALISA2003-CMD/LEXA-/actions/runs/40064896058

## Evidence from the failed run

- The Python API unit/contract job passed in the inspected run.
- The frontend `Typecheck` step passed.
- The frontend contract step failed before the production build, so the Next production build was skipped.
- The two failing source-contract files were `apps/web/tests/phase5-sales-cockpit.test.mjs` and `apps/web/tests/phase7-purchasing-contract.test.mjs`.

## Root cause

The tests required `run_phase345_staging_e2e`, `run_phase7_staging_e2e`, staging URL variables and clean-database replay phrases in `.github/workflows/lexa-ci.yml`. The current canonical workflow is intentionally the low-cost baseline: `api-unit-contracts`, `web-build` (typecheck, `npm test`, production build), and `compose-config`. It excludes authenticated, write-enabled staging E2E and disposable database replay by design. Therefore the tests were coupled to an optional workflow layout that is not deployed.

## Fix

The two contracts now assert the actual baseline workflow jobs and the ordinary web test command. They keep detailed checks against the sales and purchasing Playwright specs/config/global setup for disposable-scope opt-in, staging-only URLs, production-host rejection, readiness checks, branch/session safeguards and isolated authenticated storage. Tests are not deleted, and the workflow is not made dependent on staging secrets or an external environment. Release E2E and clean replay remain separate, explicit gates.

This distinction is intentional: a pull request/push should be able to run the lightweight CI safely, while release owners must separately authorize any write-enabled staging acceptance and provide disposable resources.

## Previous CI errors remain fixed

The bundle also retains:

- Null-safe missing business profile/currency handling in the daily brief client.
- Explicit provider key/model fields in Pydantic `Settings`, with provider keys empty by default.
- Order-relative assertions for old migrations 042–044, followed by candidate 045/046.

## Phase 4 feature included in this overlay

`GET /api/v1/intelligence/demand-forecast` and `/demand-forecast` add a read-only weekday-seasonal baseline:

- A recent successful analytics refresh must cover all 56 history days and finish within 72 hours. Otherwise, the route returns `unavailable` with no forecasts.
- The API requires full authorized branch scope and reads existing product daily analytics; it does not create or alter domain records.
- It needs at least six active demand days per series and caps work to the 30 highest-volume variants.
- Each series uses the median recorded units for the same weekday in the prior eight weeks. A 14-day rolling-origin holdout reports MAE/WAPE and compares against last-week-same-weekday.
- If holdout actual demand is zero, WAPE is null/not measurable rather than divided by zero. Historical ranges are labelled descriptive, not calibrated intervals.
- External AI, stock mutations, purchase orders, reorder-point changes and automatic replenishment remain disabled.

This baseline does not correct sales-censored demand caused by stockouts, and it is not an independently validated model. That work belongs to the next acceptance increment.

## Validation boundary

The focused local suite passed: 58 Python tests; 11 Node contract tests. Python compile, Node syntax and TypeScript/TSX syntax transpilation were also checked. The complete repository CI/build, a live database execution/RLS replay and authenticated staging were not run from this overlay-only environment. Exact CI must pass after the ZIP is extracted, and migrations 045/046 remain candidates.

## Deployment revision alignment observed before this ZIP

At inspection, Render's latest deploy and Vercel's latest READY production deployment both pointed at `2214dffa81f1d858cdfe51d695bd32758c3a56bd`. This means those two providers were aligned on that observed revision; it does not establish green deployment for the new ZIP. After upload, check both against the new extracted commit SHA.
