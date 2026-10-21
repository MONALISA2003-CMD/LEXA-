# LEXA Phase 4 — Command Centre KPI Definitions

**Status:** Source-candidate contract, dated 21 October 2026. Definitions below describe the current implementation, not a formal accounting policy or independently reconciled financial statement.

## Scope and common rules

- **Workspace:** all requests are authenticated and tenant-scoped by the API. Inventory summary totals include only locations the logged-in member is assigned to through active branch membership.
- **Currency:** operational dashboard monetary values use `business_profiles.currency_code`; where no profile exists, the API falls back to UGX. Analytics overview and product-performance requests receive that currency explicitly. Never sum different currencies into one total.
- **Business date:** the API's `business_date` is authoritative. The browser's local date is only a first-render fallback until that value is received.
- **Unavailable is not zero:** errors, missing daily records and loading states must remain visually distinct from an actual numeric zero.
- **Period convention:** 7, 30 and 90 calendar days, inclusive of both ends, ending on the workspace business date. The selected exact date range is displayed.

## KPIs

| KPI | Definition/source | Important qualification |
|---|---|---|
| Today's sales | Sum of `sales.total` for `COMPLETED` sales whose `COALESCE(completed_at, created_at)` falls on the selected tenant business date and whose currency matches the business profile currency. | Gross completed-sale total; not net of returns. The period net-sales KPI is separate. |
| Collected today | Sum of `payments.amount` where tenant matches, `status='RECORDED'`, `business_date` is the tenant business date, and `currency_code` matches the business profile currency. | Includes separately recorded receivable payments, not just the initial payment on a sale. It is gross recorded payment inflow; refunds are shown separately in the analytics measures and are not deducted from this operational KPI. |
| Credit recorded | Sum of `sales.amount_due` on completed sales for the tenant business date and profile currency. | This is the due amount attached to today's completed sales; it is not the total aging balance. |
| Open receivables | Sum of open/partially-paid receivable balances joined to sales in the business profile currency. | Filtered by currency; excludes balances in other currencies rather than adding unlike values. |
| Net sales | Sum of `analytics_daily_business_metrics.net_sales` for the selected date range/currency. The analytics foundation computes sales less returns. | Derived from the analytics tables and therefore depends on their refresh process. It is not the same as money collected or net profit. |
| Product performance | Sums `analytics_product_daily_metrics` by product variant for the selected range and currency, then ranks by aggregate `net_sales`. | Gross margin is sales after recorded discounts/returns less recorded COGS according to the analytics model. It is not net profit because operating expenses, financing and other costs are excluded. |
| Inventory value | Server-side sum of `inventory_balances.stock_value` for all authorized locations for the current member, computed in PostgreSQL without a row cap. | Uses the persisted inventory stock valuation. Does not infer valuation from the first page of the inventory list. |
| Out of stock | Count of authorized inventory balance rows with available quantity (`on_hand - reserved`) less than or equal to zero. | Count is at balance-row / variant-location level; it is not necessarily a count of unique products. |
| Low stock | Count of authorized inventory balance rows with available quantity greater than zero and less than or equal to five units. | **Provisional generic threshold.** Phase 6 should replace it with per-variant/per-location reorder points and units-of-measure-aware thresholds. |

## Reliability and interpretation

1. A KPI card must not silently display `0` after an API error.
2. The chart keeps missing dates as gaps rather than inventing zero-valued records.
3. Dashboard analytics endpoints require `analytics.read` and full active-branch scope where the underlying metric is tenant-wide. Restricted branch users should receive a clear unavailable/permission state; the application must not bypass that authorization to draw an all-branch chart.
4. Payment-channel expected amounts are reconciliation estimates, not confirmed actual cash/bank statements.
5. Source-level tests verify query intent and authorization helpers. Only authenticated environment tests can prove actual database policy behaviour and displayed values agree against live transaction fixtures.
