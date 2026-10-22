-- RECONSTRUCTED EQUIVALENT — NOT THE HISTORICAL 024 SOURCE.
-- Tenant isolation contract inferred from available 027 release-convergence SQL and canonical Neon policies.
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['suppliers','supplier_profiles','supplier_product_prices','supplier_variant_costs','purchase_orders','purchase_order_lines','purchase_order_status_history','purchase_receipts','purchase_receipt_lines','purchase_returns','purchase_return_lines'] LOOP
   EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
   EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
   EXECUTE format('DROP POLICY IF EXISTS %I_tenant_isolation ON %I',t,t);
   EXECUTE format('CREATE POLICY %I_tenant_isolation ON %I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'',true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'',true), '''')::uuid)',t,t);
 END LOOP;
END $$;
GRANT SELECT,INSERT,UPDATE,DELETE ON suppliers,supplier_profiles,supplier_product_prices,supplier_variant_costs,purchase_orders,purchase_order_lines,purchase_order_status_history,purchase_receipts,purchase_receipt_lines,purchase_returns,purchase_return_lines TO lexa_app;

CREATE OR REPLACE FUNCTION lexa_validate_supplier_price_dimensions() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE allowed boolean;
BEGIN
 SELECT EXISTS(SELECT 1 FROM variant_units vu WHERE vu.tenant_id=NEW.tenant_id AND vu.variant_id=NEW.variant_id AND vu.unit_id=NEW.unit_id AND vu.purpose IN ('PURCHASING','SELLING') AND vu.status='ACTIVE') INTO allowed;
 IF NOT allowed THEN RAISE EXCEPTION 'Supplier price unit must be an active PURCHASING or SELLING unit for the variant' USING ERRCODE='23503'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_supplier_product_prices_validate_dimensions ON supplier_product_prices;
CREATE TRIGGER trg_supplier_product_prices_validate_dimensions BEFORE INSERT OR UPDATE OF supplier_id,variant_id,unit_id,tenant_id ON supplier_product_prices FOR EACH ROW EXECUTE FUNCTION lexa_validate_supplier_price_dimensions();
DROP TRIGGER IF EXISTS trg_supplier_product_prices_validate_unit ON supplier_product_prices;
CREATE TRIGGER trg_supplier_product_prices_validate_unit BEFORE INSERT OR UPDATE OF unit_id,tenant_id ON supplier_product_prices FOR EACH ROW EXECUTE FUNCTION lexa_validate_product_price_unit();

