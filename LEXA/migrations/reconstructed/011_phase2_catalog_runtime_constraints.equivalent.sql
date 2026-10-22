-- RECONSTRUCTED EQUIVALENT — NOT THE HISTORICAL 011 SOURCE.
-- Table and trigger behavior inferred from the canonical Neon schema and app contracts.
-- Exact source recovery remains unresolved. Never copy to migrations/011_phase2_catalog_runtime_constraints.sql.
-- For non-empty production data, prepare and independently approve a context/unit backfill first.
-- This gate deliberately refuses to guess those data transformations.
BEGIN;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM product_prices WHERE price_context_id IS NULL OR unit_id IS NULL) THEN
   RAISE EXCEPTION 'Replay gate blocked: product_prices price_context_id/unit_id backfill must be evidenced before NOT NULL enforcement';
 END IF;
END $$;
ALTER TABLE product_prices ALTER COLUMN price_context_id SET NOT NULL;
ALTER TABLE product_prices ALTER COLUMN unit_id SET NOT NULL;
CREATE TABLE IF NOT EXISTS unit_conversions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 from_unit_id uuid NOT NULL,
 to_unit_id uuid NOT NULL,
 factor numeric NOT NULL,
 rounding_scale integer NOT NULL DEFAULT 6,
 status varchar NOT NULL DEFAULT 'ACTIVE',
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT unit_conversions_factor_check CHECK(factor>0),
 CONSTRAINT unit_conversions_no_self_check CHECK(from_unit_id<>to_unit_id),
 CONSTRAINT unit_conversions_rounding_check CHECK(rounding_scale BETWEEN 0 AND 8),
 CONSTRAINT unit_conversions_status_check CHECK(status IN ('ACTIVE','INACTIVE','ARCHIVED')),
 CONSTRAINT fk_unit_conversions_from FOREIGN KEY(from_unit_id) REFERENCES units(id) DEFERRABLE INITIALLY IMMEDIATE,
 CONSTRAINT fk_unit_conversions_to FOREIGN KEY(to_unit_id) REFERENCES units(id) DEFERRABLE INITIALLY IMMEDIATE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_unit_conversions_tenant_pair ON unit_conversions(tenant_id,from_unit_id,to_unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_conversions_tenant_from ON unit_conversions(tenant_id,from_unit_id,to_unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_conversions_lookup ON unit_conversions(tenant_id,from_unit_id,to_unit_id,status);

CREATE TABLE IF NOT EXISTS variant_units (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 variant_id uuid NOT NULL,
 unit_id uuid NOT NULL,
 purpose varchar NOT NULL,
 base_quantity numeric NOT NULL,
 is_default boolean NOT NULL DEFAULT false,
 status varchar NOT NULL DEFAULT 'ACTIVE',
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT variant_units_base_quantity_check CHECK(base_quantity>0),
 CONSTRAINT variant_units_purpose_check CHECK(purpose IN ('SELLING','PURCHASING','REPORTING')),
 CONSTRAINT variant_units_status_check CHECK(status IN ('ACTIVE','INACTIVE','ARCHIVED')),
 CONSTRAINT fk_variant_units_variant FOREIGN KEY(tenant_id,variant_id) REFERENCES product_variants(tenant_id,id) DEFERRABLE INITIALLY IMMEDIATE,
 CONSTRAINT fk_variant_units_unit FOREIGN KEY(unit_id) REFERENCES units(id) DEFERRABLE INITIALLY IMMEDIATE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variant_units_tenant_id ON variant_units(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variant_units_pair ON variant_units(tenant_id,variant_id,unit_id,purpose);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variant_units_default ON variant_units(tenant_id,variant_id,purpose) WHERE is_default AND status='ACTIVE';
CREATE INDEX IF NOT EXISTS idx_variant_units_variant ON variant_units(tenant_id,variant_id,purpose,status);

CREATE OR REPLACE FUNCTION lexa_validate_unit_conversion_units() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE from_ok boolean; to_ok boolean;
BEGIN
 SELECT true INTO from_ok FROM units u WHERE u.id=NEW.from_unit_id AND (u.tenant_id=NEW.tenant_id OR (u.tenant_id IS NULL AND u.is_system));
 SELECT true INTO to_ok FROM units u WHERE u.id=NEW.to_unit_id AND (u.tenant_id=NEW.tenant_id OR (u.tenant_id IS NULL AND u.is_system));
 IF from_ok IS DISTINCT FROM true OR to_ok IS DISTINCT FROM true THEN
   RAISE EXCEPTION 'Conversion units must belong to this tenant or be global system units' USING ERRCODE='23503';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_unit_conversions_validate_units ON unit_conversions;
CREATE TRIGGER trg_unit_conversions_validate_units BEFORE INSERT OR UPDATE OF from_unit_id,to_unit_id,tenant_id ON unit_conversions FOR EACH ROW EXECUTE FUNCTION lexa_validate_unit_conversion_units();

CREATE OR REPLACE FUNCTION lexa_validate_catalog_unit_tenant() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE unit_ok boolean;
BEGIN
 SELECT true INTO unit_ok FROM units u WHERE u.id=NEW.unit_id AND (u.tenant_id=NEW.tenant_id OR (u.tenant_id IS NULL AND u.is_system));
 IF unit_ok IS DISTINCT FROM true THEN
   RAISE EXCEPTION 'Unit must belong to this tenant or be a global system unit' USING ERRCODE='23503';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_variant_units_validate_unit ON variant_units;
CREATE TRIGGER trg_variant_units_validate_unit BEFORE INSERT OR UPDATE OF unit_id,tenant_id ON variant_units FOR EACH ROW EXECUTE FUNCTION lexa_validate_catalog_unit_tenant();

DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['unit_conversions','variant_units'] LOOP
   EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
   EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
   EXECUTE format('DROP POLICY IF EXISTS %I_tenant_isolation ON %I',t,t);
   EXECUTE format('CREATE POLICY %I_tenant_isolation ON %I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'',true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'',true), '''')::uuid)',t,t);
 END LOOP;
END $$;

-- Price-dimension validation recovered from current canonical Neon function definitions.
CREATE OR REPLACE FUNCTION lexa_validate_product_price_unit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
 SELECT EXISTS(SELECT 1 FROM units u WHERE u.id=NEW.unit_id AND (u.tenant_id=NEW.tenant_id OR (u.tenant_id IS NULL AND u.is_system))) INTO ok;
 IF NOT ok THEN RAISE EXCEPTION 'Product price unit does not belong to tenant or system scope' USING ERRCODE='23503'; END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION lexa_validate_product_price_dimensions() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_tenant uuid; allowed boolean; ctx_currency char(3); list_currency char(3);
BEGIN
 SELECT tenant_id INTO v_tenant FROM product_variants WHERE id=NEW.variant_id;
 IF v_tenant IS NULL OR v_tenant<>NEW.tenant_id THEN RAISE EXCEPTION 'Variant does not belong to tenant' USING ERRCODE='23503'; END IF;
 SELECT EXISTS(SELECT 1 FROM variant_units vu WHERE vu.tenant_id=NEW.tenant_id AND vu.variant_id=NEW.variant_id AND vu.unit_id=NEW.unit_id AND vu.purpose='SELLING' AND vu.status='ACTIVE') INTO allowed;
 IF NOT allowed THEN RAISE EXCEPTION 'Price unit must be an active SELLING unit for the variant' USING ERRCODE='23503'; END IF;
 SELECT currency INTO ctx_currency FROM price_contexts WHERE id=NEW.price_context_id AND tenant_id=NEW.tenant_id AND status<>'ARCHIVED';
 SELECT currency INTO list_currency FROM price_lists WHERE id=NEW.price_list_id AND tenant_id=NEW.tenant_id AND status<>'ARCHIVED';
 IF ctx_currency IS NULL OR list_currency IS NULL OR ctx_currency<>list_currency THEN RAISE EXCEPTION 'Price context and price list currencies must match' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_product_prices_validate_dimensions ON product_prices;
CREATE TRIGGER trg_product_prices_validate_dimensions BEFORE INSERT OR UPDATE OF price_context_id,price_list_id,variant_id,unit_id,tenant_id ON product_prices FOR EACH ROW EXECUTE FUNCTION lexa_validate_product_price_dimensions();
DROP TRIGGER IF EXISTS trg_product_prices_validate_unit ON product_prices;
CREATE TRIGGER trg_product_prices_validate_unit BEFORE INSERT OR UPDATE OF unit_id,tenant_id ON product_prices FOR EACH ROW EXECUTE FUNCTION lexa_validate_product_price_unit();

GRANT SELECT,INSERT,UPDATE,DELETE ON unit_conversions,variant_units TO lexa_app;
COMMIT;
