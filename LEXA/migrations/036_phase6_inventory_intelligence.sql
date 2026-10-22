-- LEXA Phase 6 Increment 6.1: location-specific, explainable replenishment policies.
-- Additive only. Does not create stock, purchase orders, transfers or inventory movements.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.inventory_balances') IS NULL
     OR to_regclass('public.inventory_transactions') IS NULL
     OR to_regclass('public.product_variants') IS NULL
     OR to_regclass('public.locations') IS NULL
     OR to_regclass('public.sales') IS NULL
     OR to_regclass('public.transaction_lines') IS NULL
     OR to_regclass('public.sale_returns') IS NULL
     OR to_regclass('public.sale_return_lines') IS NULL THEN
    RAISE EXCEPTION 'Phase 6 inventory-intelligence prerequisites are missing';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.inventory_replenishment_policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  location_id uuid NOT NULL REFERENCES public.locations(id) ON DELETE RESTRICT,
  variant_id uuid NOT NULL REFERENCES public.product_variants(id) ON DELETE RESTRICT,
  lead_time_days integer NOT NULL DEFAULT 7 CHECK (lead_time_days BETWEEN 0 AND 365),
  review_period_days integer NOT NULL DEFAULT 7 CHECK (review_period_days BETWEEN 1 AND 90),
  lookback_days integer NOT NULL DEFAULT 30 CHECK (lookback_days BETWEEN 7 AND 365),
  minimum_available numeric(20,6) NOT NULL DEFAULT 0 CHECK (minimum_available >= 0),
  safety_stock numeric(20,6) NOT NULL DEFAULT 0 CHECK (safety_stock >= 0),
  enabled boolean NOT NULL DEFAULT true,
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  updated_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_inventory_replenishment_policy UNIQUE (tenant_id, location_id, variant_id),
  CONSTRAINT fk_replenishment_location_tenant FOREIGN KEY (tenant_id, location_id)
    REFERENCES public.locations(tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT fk_replenishment_variant_tenant FOREIGN KEY (tenant_id, variant_id)
    REFERENCES public.product_variants(tenant_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_inventory_replenishment_policy_enabled
  ON public.inventory_replenishment_policies(tenant_id, location_id, enabled, updated_at DESC);

ALTER TABLE public.inventory_replenishment_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_replenishment_policies FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS inventory_replenishment_policies_tenant_isolation
  ON public.inventory_replenishment_policies;
CREATE POLICY inventory_replenishment_policies_tenant_isolation
  ON public.inventory_replenishment_policies
  FOR ALL TO lexa_app
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

REVOKE ALL PRIVILEGES ON TABLE public.inventory_replenishment_policies FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.inventory_replenishment_policies TO lexa_app;

INSERT INTO public.schema_migrations(version)
VALUES ('036_phase6_inventory_intelligence')
ON CONFLICT (version) DO NOTHING;
COMMIT;
