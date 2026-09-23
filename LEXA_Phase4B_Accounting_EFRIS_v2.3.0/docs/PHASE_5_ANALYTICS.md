# Phase 5 — Business Intelligence Foundation

LEXA now derives deterministic analytical projections from authoritative transactional data. The projections are a reporting layer; they never replace the transaction ledger, accounting journal or inventory ledger.

## Product surface

`Reports & Business Intelligence` is a user-facing module. The former `Business Engine` page is removed from the product surface because it exposed implementation concepts rather than business outcomes.

## Projections

- `analytics_daily_business_metrics`
- `analytics_branch_daily_metrics`
- `analytics_product_daily_metrics`
- `analytics_customer_purchase_patterns`
- `analytics_inventory_health_metrics`
- `analytics_refresh_runs`

## Refresh model

`Transactional Core → deterministic refresh_analytics() → analytics projections → Reports UI`

The refresh is repeatable for a tenant/date range. Projection rebuilds are allowed because the authoritative truth remains in the transactional database.

## Intelligence boundary

Phase 5 is descriptive BI. Forecasting, anomaly detection, recommendations and LEXA Brain behavior remain later intelligence phases.
