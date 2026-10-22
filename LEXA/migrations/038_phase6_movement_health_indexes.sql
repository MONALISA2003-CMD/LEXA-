-- Phase 6 Increment 03: indexes for location-scoped completed sales/returns movement health.
-- Intentionally non-transactional: CREATE INDEX CONCURRENTLY cannot run inside BEGIN/COMMIT.
-- IF NOT EXISTS protects already-completed index builds. If a concurrent build is interrupted, inspect pg_index and drop any invalid index with DROP INDEX CONCURRENTLY before retrying this file. Do not rerun the full migration sequence against a partially populated database; clean replay always uses a fresh disposable database. The migration ledger row is written only after all index builds complete.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_inventory_movement_history
  ON public.sales (tenant_id, location_id, status, (COALESCE(completed_at, created_at)) DESC)
  INCLUDE (transaction_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transaction_lines_variant_demand
  ON public.transaction_lines (tenant_id, product_variant_id, transaction_id)
  INCLUDE (quantity)
  WHERE line_type = 'PRODUCT' AND product_variant_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sale_returns_movement_history
  ON public.sale_returns (tenant_id, status, (COALESCE(completed_at, created_at)) DESC)
  INCLUDE (sale_id, inventory_location_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sale_return_lines_variant_movement
  ON public.sale_return_lines (tenant_id, variant_id, return_id)
  INCLUDE (quantity);

INSERT INTO public.schema_migrations(version)
VALUES ('038_phase6_movement_health_indexes')
ON CONFLICT (version) DO NOTHING;
