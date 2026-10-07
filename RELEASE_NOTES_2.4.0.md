# LEXA v2.4.0 — Phase 5 Business Intelligence

Phase 5 adds deterministic analytics projections and the user-facing Reports & Business Intelligence workspace.

## Product cleanup

The **Business Engine** has been removed as a user-facing product module. Its underlying transaction/workflow schema remains internal technical infrastructure because commerce, inventory and accounting depend on the authoritative transaction layer. There is no Business Engine navigation item, page or public business-engine API route.

## Phase 5 analytics

- Daily business metrics: sales, returns, net sales, collections, refunds, credit created, expenses and net cash movement.
- Branch daily performance.
- Product daily performance, COGS and gross margin.
- Customer purchase patterns and outstanding exposure.
- Inventory health, rolling 30-day velocity and days of cover.
- Deterministic analytics refresh function with refresh-run status.
- Tenant-scoped forced RLS on all analytics projections.
- `analytics.read` and `analytics.refresh` permissions.
- Reports & Business Intelligence frontend workspace.
- Reports navigation replaces the technical Business Engine entry point.

## Validation

- 85 automated source/contract tests pass.
- Python backend compilation passes.
- TypeScript contract compilation passes.
- Isolated Neon validation passed for daily metrics, product sales/COGS/margin, cash movement and inventory velocity.
- Canonical Neon migration `021_phase5_analytics_foundation` is applied.
- No validation rows were left in canonical transactional tables.
