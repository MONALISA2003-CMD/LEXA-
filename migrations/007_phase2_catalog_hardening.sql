-- LEXA Phase 2: Catalog hardening
-- Additive to Phase 1. No production data reset. Intended for LEXA development first.

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Catalog tables. Keep the deployed Phase 1 outbox contract intact.
CREATE TABLE IF NOT EXISTS categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  parent_id uuid,
  name varchar(200) NOT NULL,
  code varchar(50) NOT NULL,
  description text,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT categories_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT categories_sort_order_check CHECK (sort_order >= 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_tenant_id ON categories(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_tenant_code_active ON categories(tenant_id, code) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_categories_tenant_parent_active ON categories(tenant_id, parent_id, sort_order, id) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS brands (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar(200) NOT NULL,
  code varchar(50),
  description text,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT brands_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_brands_tenant_id ON brands(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_brands_tenant_code_active ON brands(tenant_id, code) WHERE code IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_brands_tenant_name_active ON brands(tenant_id, name, id) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar(100) NOT NULL,
  code varchar(30) NOT NULL,
  symbol varchar(20) NOT NULL,
  unit_type varchar(40) NOT NULL DEFAULT 'COUNT',
  allows_fraction boolean NOT NULL DEFAULT false,
  precision_scale integer NOT NULL DEFAULT 0,
  is_system boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT units_precision_check CHECK (precision_scale BETWEEN 0 AND 6),
  CONSTRAINT units_system_scope_check CHECK ((is_system AND tenant_id IS NULL) OR ((NOT is_system) AND tenant_id IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_units_scope_code ON units(COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), code);
CREATE INDEX IF NOT EXISTS idx_units_tenant_name ON units(tenant_id, name, id);

CREATE TABLE IF NOT EXISTS products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category_id uuid NOT NULL,
  brand_id uuid,
  name varchar(250) NOT NULL,
  description text,
  product_type varchar(30) NOT NULL DEFAULT 'STOCKED',
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  has_variants boolean NOT NULL DEFAULT true,
  tax_category_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT products_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT products_metadata_object_check CHECK (jsonb_typeof(metadata) = 'object')
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_tenant_id ON products(tenant_id, id);
CREATE INDEX IF NOT EXISTS idx_products_tenant_category_active ON products(tenant_id, category_id, id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_products_tenant_name_active ON products(tenant_id, lower(name), id) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS product_variants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  product_id uuid NOT NULL,
  name varchar(200) NOT NULL,
  sku varchar(100) NOT NULL,
  base_unit_id uuid NOT NULL,
  track_inventory boolean NOT NULL DEFAULT true,
  allow_fractional_quantity boolean NOT NULL DEFAULT false,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  costing_method varchar(40),
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT variants_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT variants_metadata_object_check CHECK (jsonb_typeof(metadata) = 'object')
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variants_tenant_id ON product_variants(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variants_tenant_sku_active ON product_variants(tenant_id, sku) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_variants_tenant_product_active ON product_variants(tenant_id, product_id, id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_variants_tenant_sku_active_lookup ON product_variants(tenant_id, sku) WHERE deleted_at IS NULL AND status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS barcodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL,
  barcode varchar(120) NOT NULL,
  barcode_type varchar(30) NOT NULL DEFAULT 'OTHER',
  is_primary boolean NOT NULL DEFAULT false,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT barcodes_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_barcodes_tenant_id ON barcodes(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_barcodes_tenant_value_active ON barcodes(tenant_id, barcode) WHERE status = 'ACTIVE';
CREATE UNIQUE INDEX IF NOT EXISTS uq_barcodes_one_primary_variant ON barcodes(tenant_id, variant_id) WHERE is_primary AND status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_barcodes_tenant_variant_active ON barcodes(tenant_id, variant_id, id) WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS product_attribute_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category_id uuid,
  name varchar(120) NOT NULL,
  code varchar(60) NOT NULL,
  data_type varchar(30) NOT NULL,
  required boolean NOT NULL DEFAULT false,
  options jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT attribute_definitions_type_check CHECK (data_type IN ('TEXT','NUMBER','BOOLEAN','DATE','SELECT','MULTI_SELECT')),
  CONSTRAINT attribute_definitions_options_check CHECK (options IS NULL OR jsonb_typeof(options) = 'object')
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_definitions_tenant_id ON product_attribute_definitions(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_definitions_tenant_code ON product_attribute_definitions(tenant_id, code);
CREATE INDEX IF NOT EXISTS idx_attribute_definitions_tenant_category ON product_attribute_definitions(tenant_id, category_id, code);

CREATE TABLE IF NOT EXISTS product_attribute_values (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL,
  attribute_definition_id uuid NOT NULL,
  value_text text,
  value_number numeric(20,6),
  value_boolean boolean,
  value_date timestamptz,
  value_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT attribute_values_one_representation CHECK (
    ((value_text IS NOT NULL)::integer + (value_number IS NOT NULL)::integer +
     (value_boolean IS NOT NULL)::integer + (value_date IS NOT NULL)::integer +
     (value_json IS NOT NULL)::integer) = 1
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_values_variant_definition ON product_attribute_values(tenant_id, variant_id, attribute_definition_id);
CREATE INDEX IF NOT EXISTS idx_attribute_values_tenant_variant ON product_attribute_values(tenant_id, variant_id, attribute_definition_id);

CREATE TABLE IF NOT EXISTS price_lists (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar(100) NOT NULL,
  currency char(3) NOT NULL DEFAULT 'UGX',
  price_type varchar(40) NOT NULL DEFAULT 'RETAIL',
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  effective_from timestamptz NOT NULL,
  effective_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT price_lists_currency_check CHECK (currency ~ '^[A-Z]{3}$'),
  CONSTRAINT price_lists_status_check CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
  CONSTRAINT price_lists_interval_check CHECK (effective_to IS NULL OR effective_to > effective_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_price_lists_tenant_id ON price_lists(tenant_id, id);
CREATE INDEX IF NOT EXISTS idx_price_lists_tenant_effective ON price_lists(tenant_id, effective_from DESC, id);

CREATE TABLE IF NOT EXISTS product_prices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  price_list_id uuid NOT NULL,
  variant_id uuid NOT NULL,
  unit_price numeric(20,4) NOT NULL,
  minimum_quantity numeric(20,6) NOT NULL DEFAULT 1,
  effective_from timestamptz NOT NULL,
  effective_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT product_prices_unit_price_check CHECK (unit_price >= 0),
  CONSTRAINT product_prices_minimum_quantity_check CHECK (minimum_quantity > 0),
  CONSTRAINT product_prices_interval_check CHECK (effective_to IS NULL OR effective_to > effective_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_prices_tenant_id ON product_prices(tenant_id, id);
CREATE INDEX IF NOT EXISTS idx_product_prices_lookup ON product_prices(tenant_id, price_list_id, variant_id, minimum_quantity, effective_from DESC);

-- Replace the original unconditional catalog uniqueness constraints with active-record uniqueness,
-- allowing a deleted identity to be re-created safely without affecting historical references.
ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_tenant_id_code_key;
ALTER TABLE brands DROP CONSTRAINT IF EXISTS brands_tenant_id_code_key;
ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS product_variants_tenant_id_sku_key;
ALTER TABLE barcodes DROP CONSTRAINT IF EXISTS barcodes_tenant_id_barcode_key;

-- Cross-tenant references are enforced by composite foreign keys, not only application checks.
ALTER TABLE categories DROP CONSTRAINT IF EXISTS fk_categories_parent_tenant;
ALTER TABLE categories ADD CONSTRAINT fk_categories_parent_tenant
  FOREIGN KEY (tenant_id, parent_id) REFERENCES categories(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_category_tenant;
ALTER TABLE products ADD CONSTRAINT fk_products_category_tenant
  FOREIGN KEY (tenant_id, category_id) REFERENCES categories(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_brand_tenant;
ALTER TABLE products ADD CONSTRAINT fk_products_brand_tenant
  FOREIGN KEY (tenant_id, brand_id) REFERENCES brands(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS fk_variants_product_tenant;
ALTER TABLE product_variants ADD CONSTRAINT fk_variants_product_tenant
  FOREIGN KEY (tenant_id, product_id) REFERENCES products(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS fk_variants_unit_tenant;
ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS product_variants_base_unit_id_fkey;
ALTER TABLE product_variants ADD CONSTRAINT product_variants_base_unit_id_fkey
  FOREIGN KEY (base_unit_id) REFERENCES units(id)
  DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE barcodes DROP CONSTRAINT IF EXISTS fk_barcodes_variant_tenant;
ALTER TABLE barcodes ADD CONSTRAINT fk_barcodes_variant_tenant
  FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE product_attribute_definitions DROP CONSTRAINT IF EXISTS fk_attribute_definition_category_tenant;
ALTER TABLE product_attribute_definitions ADD CONSTRAINT fk_attribute_definition_category_tenant
  FOREIGN KEY (tenant_id, category_id) REFERENCES categories(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE product_attribute_values DROP CONSTRAINT IF EXISTS fk_attribute_value_variant_tenant;
ALTER TABLE product_attribute_values ADD CONSTRAINT fk_attribute_value_variant_tenant
  FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE product_attribute_values DROP CONSTRAINT IF EXISTS fk_attribute_value_definition_tenant;
ALTER TABLE product_attribute_values ADD CONSTRAINT fk_attribute_value_definition_tenant
  FOREIGN KEY (tenant_id, attribute_definition_id) REFERENCES product_attribute_definitions(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE product_prices DROP CONSTRAINT IF EXISTS fk_product_price_list_tenant;
ALTER TABLE product_prices ADD CONSTRAINT fk_product_price_list_tenant
  FOREIGN KEY (tenant_id, price_list_id) REFERENCES price_lists(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE product_prices DROP CONSTRAINT IF EXISTS fk_product_price_variant_tenant;
ALTER TABLE product_prices ADD CONSTRAINT fk_product_price_variant_tenant
  FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id)
  DEFERRABLE INITIALLY IMMEDIATE;

-- Database-level temporal invariant. Different quantity tiers may overlap; the same tier may not.
ALTER TABLE product_prices DROP CONSTRAINT IF EXISTS product_prices_no_overlap;
ALTER TABLE product_prices ADD CONSTRAINT product_prices_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    price_list_id WITH =,
    variant_id WITH =,
    minimum_quantity WITH =,
    tstzrange(effective_from, effective_to, '[)') WITH &&
  );

-- Category hierarchy cycle protection.
CREATE OR REPLACE FUNCTION lexa_validate_category_parent() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  cursor_id uuid;
BEGIN
  IF NEW.parent_id IS NULL THEN RETURN NEW; END IF;
  IF NEW.parent_id = NEW.id THEN RAISE EXCEPTION 'Category cannot be its own parent' USING ERRCODE = '23514'; END IF;
  cursor_id := NEW.parent_id;
  WHILE cursor_id IS NOT NULL LOOP
    IF cursor_id = NEW.id THEN
      RAISE EXCEPTION 'Category hierarchy cycle detected' USING ERRCODE = '23514';
    END IF;
    SELECT parent_id INTO cursor_id
      FROM categories
      WHERE tenant_id = NEW.tenant_id AND id = cursor_id AND deleted_at IS NULL;
  END LOOP;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_categories_parent_cycle ON categories;
CREATE TRIGGER trg_categories_parent_cycle
BEFORE INSERT OR UPDATE OF parent_id, tenant_id ON categories
FOR EACH ROW EXECUTE FUNCTION lexa_validate_category_parent();

-- Variant fractional-quantity invariant belongs in the database because the unit is another row.
CREATE OR REPLACE FUNCTION lexa_validate_variant_unit() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  unit_allows_fraction boolean;
BEGIN
  SELECT allows_fraction INTO unit_allows_fraction
  FROM units
  WHERE (tenant_id = NEW.tenant_id OR (tenant_id IS NULL AND is_system))
    AND id = NEW.base_unit_id;
  IF unit_allows_fraction IS NULL THEN
    RAISE EXCEPTION 'Base unit does not belong to tenant or is unavailable' USING ERRCODE = '23503';
  END IF;
  IF NEW.allow_fractional_quantity AND NOT unit_allows_fraction THEN
    RAISE EXCEPTION 'Variant cannot allow fractional quantity when its base unit does not allow fractions' USING ERRCODE = '23514';
  END IF;
  IF NOT NEW.allow_fractional_quantity AND unit_allows_fraction THEN
    -- Explicit false is permitted even for a fractional-capable unit.
    NULL;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_variants_validate_unit ON product_variants;
CREATE TRIGGER trg_variants_validate_unit
BEFORE INSERT OR UPDATE OF base_unit_id, allow_fractional_quantity, tenant_id ON product_variants
FOR EACH ROW EXECUTE FUNCTION lexa_validate_variant_unit();

-- Keep updated_at deterministic for mutable catalog records.
CREATE OR REPLACE FUNCTION lexa_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$;
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'categories','brands','units','products','product_variants','barcodes',
    'product_attribute_definitions','product_attribute_values','price_lists','product_prices'
  ] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', 'trg_' || t || '_updated_at', t);
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION lexa_touch_updated_at()', 'trg_' || t || '_updated_at', t);
  END LOOP;
END $$;

-- RLS. Every tenant-owned catalog table is forced through tenant context.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'categories','brands','products','product_variants','barcodes',
    'product_attribute_definitions','product_attribute_values','price_lists','product_prices'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t || '_tenant_isolation', t);
    EXECUTE format(
      'CREATE POLICY %I ON %I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)',
      t || '_tenant_isolation', t
    );
  END LOOP;
END $$;

ALTER TABLE units ENABLE ROW LEVEL SECURITY;
ALTER TABLE units FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS units_tenant_or_system_read ON units;
CREATE POLICY units_tenant_or_system_read ON units
FOR SELECT USING (tenant_id IS NULL OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
DROP POLICY IF EXISTS units_tenant_write ON units;
CREATE POLICY units_tenant_write ON units
FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND is_system = false);

-- Permissions are data, not implicit role behavior.
INSERT INTO permissions (code, description) VALUES
  ('catalog.read', 'Read catalog entities'),
  ('catalog.manage', 'Create and manage catalog entities')
ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description;

-- Existing Owner roles retain the new catalog capabilities without changing other roles.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
WHERE r.name = 'Owner' AND p.code IN ('catalog.read','catalog.manage')
ON CONFLICT DO NOTHING;

-- Safe global units. Existing rows are preserved.
INSERT INTO units (tenant_id, name, code, symbol, unit_type, allows_fraction, precision_scale, is_system)
VALUES
  (NULL, 'Piece', 'PCS', 'pc', 'COUNT', false, 0, true),
  (NULL, 'Box', 'BOX', 'box', 'COUNT', false, 0, true),
  (NULL, 'Carton', 'CTN', 'ctn', 'COUNT', false, 0, true),
  (NULL, 'Kilogram', 'KG', 'kg', 'WEIGHT', true, 3, true),
  (NULL, 'Litre', 'L', 'L', 'VOLUME', true, 3, true),
  (NULL, 'Metre', 'M', 'm', 'LENGTH', true, 3, true)
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations (version)
VALUES ('007_phase2_catalog_hardening')
ON CONFLICT (version) DO NOTHING;
