-- ACCEPTED REPLACEMENT — ORIGINAL HISTORICAL SOURCE LOST; NOT BYTE-IDENTICAL.
-- Accepted 2026-10-21 for reproducible clean replay after source-loss decision.
-- Do not describe this file as the exact SQL originally applied in production.
-- Full migration identity: 010_phase2_catalog_intelligence.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_categories_name_trgm_active ON categories USING gin(lower(name) gin_trgm_ops) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_brands_name_trgm_active ON brands USING gin(lower(name) gin_trgm_ops) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS product_families (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  parent_id uuid,
  name varchar NOT NULL,
  code varchar NOT NULL,
  description text,
  status varchar NOT NULL DEFAULT 'ACTIVE',
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT product_families_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT product_families_sort_order_check CHECK (sort_order >= 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_families_tenant_id ON product_families(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_families_tenant_code_active ON product_families(tenant_id,code) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_product_families_tenant_parent_active ON product_families(tenant_id,parent_id,sort_order,id) WHERE deleted_at IS NULL;
ALTER TABLE product_families DROP CONSTRAINT IF EXISTS fk_product_families_parent_tenant;
ALTER TABLE product_families ADD CONSTRAINT fk_product_families_parent_tenant FOREIGN KEY(tenant_id,parent_id) REFERENCES product_families(tenant_id,id) DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE products ADD COLUMN IF NOT EXISTS family_id uuid;
ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_family_tenant;
ALTER TABLE products ADD CONSTRAINT fk_products_family_tenant FOREIGN KEY(tenant_id,family_id) REFERENCES product_families(tenant_id,id) DEFERRABLE INITIALLY IMMEDIATE;
CREATE INDEX IF NOT EXISTS idx_products_tenant_family_active ON products(tenant_id,family_id,id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_products_name_trgm_active ON products USING gin(lower(name) gin_trgm_ops) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_variants_name_trgm_active ON product_variants USING gin(lower(name) gin_trgm_ops) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_variants_sku_trgm_active ON product_variants USING gin(lower(sku) gin_trgm_ops) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_variants_tenant_id_inventory ON product_variants(tenant_id,id);

ALTER TABLE product_attribute_definitions ADD COLUMN IF NOT EXISTS target_level varchar NOT NULL DEFAULT 'VARIANT';
ALTER TABLE product_attribute_definitions DROP CONSTRAINT IF EXISTS attribute_definitions_target_level_check;
ALTER TABLE product_attribute_definitions ADD CONSTRAINT attribute_definitions_target_level_check CHECK(target_level IN ('PRODUCT','VARIANT'));
CREATE INDEX IF NOT EXISTS idx_attribute_definitions_tenant_level ON product_attribute_definitions(tenant_id,target_level,code);

ALTER TABLE product_attribute_values ALTER COLUMN variant_id DROP NOT NULL;
ALTER TABLE product_attribute_values ADD COLUMN IF NOT EXISTS product_id uuid;
ALTER TABLE product_attribute_values DROP CONSTRAINT IF EXISTS attribute_values_one_target;
ALTER TABLE product_attribute_values ADD CONSTRAINT attribute_values_one_target CHECK (((product_id IS NOT NULL)::integer + (variant_id IS NOT NULL)::integer) = 1);
ALTER TABLE product_attribute_values DROP CONSTRAINT IF EXISTS fk_attribute_value_product_tenant;
ALTER TABLE product_attribute_values ADD CONSTRAINT fk_attribute_value_product_tenant FOREIGN KEY(tenant_id,product_id) REFERENCES products(tenant_id,id) DEFERRABLE INITIALLY IMMEDIATE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_values_product_definition ON product_attribute_values(tenant_id,product_id,attribute_definition_id) WHERE product_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_values_variant_definition_v2 ON product_attribute_values(tenant_id,variant_id,attribute_definition_id) WHERE variant_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_attribute_values_tenant_product ON product_attribute_values(tenant_id,product_id,attribute_definition_id) WHERE product_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS attribute_sets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar NOT NULL,
  code varchar NOT NULL,
  description text,
  status varchar NOT NULL DEFAULT 'ACTIVE',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT attribute_sets_status_check CHECK(status IN ('ACTIVE','INACTIVE','ARCHIVED'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_sets_tenant_id ON attribute_sets(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_sets_tenant_code ON attribute_sets(tenant_id,code) WHERE status <> 'ARCHIVED';

CREATE TABLE IF NOT EXISTS attribute_set_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  attribute_set_id uuid NOT NULL,
  attribute_definition_id uuid NOT NULL,
  sort_order integer NOT NULL DEFAULT 0,
  required_override boolean,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_attribute_set_tenant FOREIGN KEY(tenant_id,attribute_set_id) REFERENCES attribute_sets(tenant_id,id) DEFERRABLE INITIALLY IMMEDIATE,
  CONSTRAINT fk_attribute_set_definition_tenant FOREIGN KEY(tenant_id,attribute_definition_id) REFERENCES product_attribute_definitions(tenant_id,id) DEFERRABLE INITIALLY IMMEDIATE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_set_definitions_tenant_id ON attribute_set_definitions(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_set_definition_pair ON attribute_set_definitions(tenant_id,attribute_set_id,attribute_definition_id);

CREATE TABLE IF NOT EXISTS price_contexts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar NOT NULL,
  code varchar NOT NULL,
  currency char(3) NOT NULL,
  sales_channel varchar,
  customer_segment varchar,
  branch_id uuid,
  priority integer NOT NULL DEFAULT 0,
  status varchar NOT NULL DEFAULT 'ACTIVE',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT price_contexts_currency_check CHECK(currency ~ '^[A-Z]{3}$'),
  CONSTRAINT price_contexts_status_check CHECK(status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT fk_price_contexts_branch_tenant FOREIGN KEY(tenant_id,branch_id) REFERENCES branches(tenant_id,id) DEFERRABLE INITIALLY IMMEDIATE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_price_contexts_tenant_id ON price_contexts(tenant_id,id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_price_contexts_tenant_code ON price_contexts(tenant_id,code) WHERE status <> 'ARCHIVED';
CREATE INDEX IF NOT EXISTS idx_price_contexts_tenant_priority ON price_contexts(tenant_id,priority DESC,status);

ALTER TABLE product_prices ADD COLUMN IF NOT EXISTS price_context_id uuid;
ALTER TABLE product_prices ADD COLUMN IF NOT EXISTS unit_id uuid;
ALTER TABLE product_prices ADD COLUMN IF NOT EXISTS priority integer NOT NULL DEFAULT 0;
-- Existing production data may require an evidence-based backfill before enforcing NOT NULL/FKs.
-- This empty-replay equivalent applies NOT NULL after all required contexts/units can be populated by fixtures.
ALTER TABLE product_prices DROP CONSTRAINT IF EXISTS fk_product_prices_context_tenant;
ALTER TABLE product_prices ADD CONSTRAINT fk_product_prices_context_tenant FOREIGN KEY(tenant_id,price_context_id) REFERENCES price_contexts(tenant_id,id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE product_prices DROP CONSTRAINT IF EXISTS fk_product_prices_unit;
ALTER TABLE product_prices ADD CONSTRAINT fk_product_prices_unit FOREIGN KEY(unit_id) REFERENCES units(id) DEFERRABLE INITIALLY IMMEDIATE;
CREATE INDEX IF NOT EXISTS idx_product_prices_context_lookup ON product_prices(tenant_id,price_context_id,variant_id,unit_id,minimum_quantity,priority,effective_from DESC);
ALTER TABLE product_prices DROP CONSTRAINT IF EXISTS product_prices_no_overlap;
ALTER TABLE product_prices ADD CONSTRAINT product_prices_no_overlap EXCLUDE USING gist (
  tenant_id WITH =, price_context_id WITH =, price_list_id WITH =, variant_id WITH =,
  unit_id WITH =, minimum_quantity WITH =, priority WITH =,
  tstzrange(effective_from,effective_to,'[)') WITH &&
);

CREATE OR REPLACE FUNCTION lexa_validate_product_family_parent() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cursor_id uuid;
BEGIN
  IF NEW.parent_id IS NULL THEN RETURN NEW; END IF;
  IF NEW.parent_id=NEW.id THEN RAISE EXCEPTION 'Product family cannot be its own parent' USING ERRCODE='23514'; END IF;
  cursor_id:=NEW.parent_id;
  WHILE cursor_id IS NOT NULL LOOP
    IF cursor_id=NEW.id THEN RAISE EXCEPTION 'Product family hierarchy cycle detected' USING ERRCODE='23514'; END IF;
    SELECT parent_id INTO cursor_id FROM product_families WHERE tenant_id=NEW.tenant_id AND id=cursor_id AND deleted_at IS NULL;
  END LOOP;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_product_families_parent_cycle ON product_families;
CREATE TRIGGER trg_product_families_parent_cycle BEFORE INSERT OR UPDATE OF parent_id,tenant_id ON product_families FOR EACH ROW EXECUTE FUNCTION lexa_validate_product_family_parent();

DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['product_families','attribute_sets','attribute_set_definitions','price_contexts'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
    EXECUTE format('DROP POLICY IF EXISTS %I_tenant_isolation ON %I',t,t);
    EXECUTE format('CREATE POLICY %I_tenant_isolation ON %I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'',true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'',true), '''')::uuid)',t,t);
  END LOOP;
END $$;
GRANT SELECT,INSERT,UPDATE,DELETE ON product_families,attribute_sets,attribute_set_definitions,price_contexts TO lexa_app;
COMMIT;
