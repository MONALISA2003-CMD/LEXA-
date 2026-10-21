-- Phase 6 Increment 02: make inventory ledger age analysis efficient.
-- Additive and safe for existing ledgers; unknown provenance remains explicitly unknown.
BEGIN;

CREATE INDEX IF NOT EXISTS idx_inventory_transactions_age_analysis
  ON public.inventory_transactions (tenant_id, location_id, variant_id, occurred_at, id)
  INCLUDE (quantity_delta, transaction_type);

INSERT INTO public.schema_migrations(version)
VALUES ('037_phase6_inventory_ageing_index')
ON CONFLICT (version) DO NOTHING;

COMMIT;
