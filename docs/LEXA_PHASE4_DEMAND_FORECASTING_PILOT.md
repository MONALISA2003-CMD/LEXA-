# LEXA Phase 4 — demand forecast baseline pilot

## Purpose

Expose an explainable first forecast for sufficiently active product variants without duplicating LEXA's sales, inventory, purchasing or accounting truth. The first increment is deliberately small: it evaluates a seasonal-naive baseline before introducing a trained model or extra Python packages.

## Data and freshness gate

Endpoint: `GET /api/v1/intelligence/demand-forecast?horizon_days=14`  
Workspace: `/demand-forecast`

It uses existing `analytics_product_daily_metrics` and `analytics_refresh_runs`. Before reading demand series, the API:

1. Requires the `analytics.read` permission.
2. Requires full branch scope, matching existing tenant-wide analytics endpoints.
3. Uses the workspace's authoritative `lexa_business_date`.
4. Requires a successful refresh with `from_date` on or before the start of the 56-day history, `to_date` on or after the business date, and completion within the previous 72 hours.
5. Returns `unavailable` when this proof is missing. Only after the successful full-window refresh gate does the code treat absent per-product/day rows as zero recorded units.

The query is capped at 30 product variants ranked by recorded units during the history window. Unit quantities are summed across transaction currencies because they describe product units, not money. It does not mix monetary values. A series needs at least six history days with recorded positive demand.

## Forecast algorithm

For each future date, estimate units as the median of recorded units for that weekday in the previous eight weeks. Historical same-weekday 10th/90th nearest-rank values are displayed as a descriptive historical range; they are not a calibrated prediction interval.

A 14-day rolling-origin holdout evaluates each test day using only observations earlier than that date. It reports:

- MAE in units;
- WAPE percentage, only if the holdout has positive total actual demand;
- a last-week-same-weekday baseline WAPE;
- whether the new baseline is better, worse, or tied on that holdout.

Forecast values are non-negative and bounded to a 7–28 day horizon. If history or the rolling test is inadequate, the service responds with explicit unavailable/partial status rather than fabricating a score.

## Safeguards

- No external AI/provider call, third-party transfer, or dependency package is added.
- The endpoint is read-only; it performs no transaction commit or business write.
- Forecasts do not post an order, adjust stock, reserve inventory, or change reorder points.
- Missing/stale 56-day history blocks output rather than pretending missing data means zero demand.
- Stockouts can suppress recorded sales, and this pilot does not reconstruct unconstrained demand; this is disclosed in API and UI.
- The method uses tenant-wide variant history, not location-level demand. Forecast-vs-stock reconciliation, stockout-censoring corrections, holidays/promotions, caching, batch refresh and representative SME backtesting remain open work.

## Acceptance still required

1. Exercise the API against synthetic fixtures with fresh complete, stale, short-range, empty and sparse histories.
2. Compare WAPE/MAE with the current reorder baseline on representative business datasets; stratify by velocity.
3. Assess stockout-censored demand using inventory availability snapshots before using forecasts for replenishment suggestions.
4. Add cached versioned results and bounded background evaluation only after measuring usage/cost.
5. Keep human review and normal purchasing workflows as the only order-creation path.
