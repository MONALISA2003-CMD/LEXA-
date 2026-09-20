-- LEXA Phase 2, Slice 1: Catalog + real role-permission binding.
-- Additive, non-destructive, and designed for version-controlled execution.

CREATE TABLE IF NOT EXISTS role_permissions (
  role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  parent_id uuid REFERENCES categories(id) ON DELETE RESTRICT,
  name varchar(200) NOT NULL,
  code varchar(50) NOT NULL,
  description text,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  sort_order integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  UNIQUE (tenant_id, code)
);

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
  UNIQUE (tenant_id, code)
);

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
  CHECK (precision_scale BETWEEN 0 AND 6)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_units_tenant_code ON units(COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), code);

CREATE TABLE IF NOT EXISTS products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category_id uuid NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
  brand_id uuid REFERENCES brands(id) ON DELETE RESTRICT,
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
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS product_variants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  product_id uuid NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
  name varchar(200) NOT NULL,
  sku varchar(100) NOT NULL,
  base_unit_id uuid NOT NULL REFERENCES units(id) ON DELETE RESTRICT,
  track_inventory boolean NOT NULL DEFAULT true,
  allow_fractional_quantity boolean NOT NULL DEFAULT false,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  costing_method varchar(40),
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  deleted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  UNIQUE (tenant_id, sku)
);

CREATE TABLE IF NOT EXISTS barcodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
  barcode varchar(120) NOT NULL,
  barcode_type varchar(30) NOT NULL DEFAULT 'OTHER',
  is_primary boolean NOT NULL DEFAULT false,
  status varchar(30) NOT NULL DEFAULT 'ACTIVE',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, barcode)
);

CREATE TABLE IF NOT EXISTS product_attribute_definitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category_id uuid REFERENCES categories(id) ON DELETE RESTRICT,
  name varchar(120) NOT NULL,
  code varchar(60) NOT NULL,
  data_type varchar(30) NOT NULL,
  required boolean NOT NULL DEFAULT false,
  options jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, code),
  CHECK (data_type IN ('TEXT','NUMBER','BOOLEAN','DATE','SELECT','MULTI_SELECT'))
);

CREATE TABLE IF NOT EXISTS product_attribute_values (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  attribute_definition_id uuid NOT NULL REFERENCES product_attribute_definitions(id) ON DELETE RESTRICT,
  value_text text,
  value_number numeric(20,6),
  value_boolean boolean,
  value_date timestamptz,
  value_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (variant_id, attribute_definition_id)
);

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
  CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS product_prices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  price_list_id uuid NOT NULL REFERENCES price_lists(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
  unit_price numeric(20,4) NOT NULL CHECK (unit_price >= 0),
  minimum_quantity numeric(20,6) NOT NULL DEFAULT 1 CHECK (minimum_quantity > 0),
  effective_from timestamptz NOT NULL,
  effective_to timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS outbox_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  event_type varchar(120) NOT NULL,
  event_version integer NOT NULL DEFAULT 1,
  aggregate_type varchar(80) NOT NULL,
  aggregate_id uuid NOT NULL,
  occurred_at timestamptz NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}',
  actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  correlation_id varchar(100),
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_categories_tenant_parent ON categories(tenant_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_brands_tenant_name ON brands(tenant_id, name);
CREATE INDEX IF NOT EXISTS idx_products_tenant_category ON products(tenant_id, category_id);
CREATE INDEX IF NOT EXISTS idx_products_tenant_name ON products(tenant_id, name);
CREATE INDEX IF NOT EXISTS idx_variants_tenant_product ON product_variants(tenant_id, product_id);
CREATE INDEX IF NOT EXISTS idx_barcodes_tenant_variant ON barcodes(tenant_id, variant_id);
CREATE INDEX IF NOT EXISTS idx_attrdef_tenant_category ON product_attribute_definitions(tenant_id, category_id);
CREATE INDEX IF NOT EXISTS idx_attrvalue_tenant_variant ON product_attribute_values(tenant_id, variant_id);
CREATE INDEX IF NOT EXISTS idx_prices_variant_list_effective ON product_prices(tenant_id, variant_id, price_list_id, effective_from);
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON outbox_events(tenant_id, published_at, created_at);

-- Tenant-consistency checks through composite FKs where practical.
CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_tenant_id ON categories(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_tenant_id ON products(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variants_tenant_id ON product_variants(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_units_tenant_id ON units(tenant_id, id);
ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_category_tenant;
ALTER TABLE products ADD CONSTRAINT fk_products_category_tenant FOREIGN KEY (tenant_id, category_id) REFERENCES categories(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_brand_tenant;
ALTER TABLE products ADD CONSTRAINT fk_products_brand_tenant FOREIGN KEY (tenant_id, brand_id) REFERENCES brands(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS fk_variants_product_tenant;
ALTER TABLE product_variants ADD CONSTRAINT fk_variants_product_tenant FOREIGN KEY (tenant_id, product_id) REFERENCES products(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE barcodes DROP CONSTRAINT IF EXISTS fk_barcodes_variant_tenant;
ALTER TABLE barcodes ADD CONSTRAINT fk_barcodes_variant_tenant FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE price_lists DROP CONSTRAINT IF EXISTS fk_price_lists_tenant_self;

-- RLS: tenant-owned catalog data.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['categories','brands','products','product_variants','barcodes','product_attribute_definitions','product_attribute_values','price_lists','product_prices','outbox_events'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t || '_tenant_isolation', t);
    EXECUTE format('CREATE POLICY %I ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)::uuid) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true)::uuid)', t || '_tenant_isolation', t);
  END LOOP;
END $$;

ALTER TABLE units ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS units_tenant_or_system_read ON units;
CREATE POLICY units_tenant_or_system_read ON units FOR SELECT USING (tenant_id IS NULL OR tenant_id = current_setting('app.tenant_id', true)::uuid);
DROP POLICY IF EXISTS units_tenant_write ON units;
CREATE POLICY units_tenant_write ON units FOR ALL USING (tenant_id = current_setting('app.tenant_id', true)::uuid) WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Catalog permissions.
INSERT INTO permissions (code, description) VALUES
 ('catalog.read', 'Read catalog entities'),
 ('catalog.manage', 'Create and manage catalog entities')
ON CONFLICT (code) DO NOTHING;

-- Repair the v0.3 permission model: explicitly bind Owner roles to all current permissions.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r CROSS JOIN permissions p
WHERE r.name = 'Owner'
ON CONFLICT DO NOTHING;

-- Development/system units; safe because system units are global and code is unique under the null-tenant sentinel.
INSERT INTO units (tenant_id, name, code, symbol, unit_type, allows_fraction, precision_scale, is_system)
VALUES
 (NULL, 'Piece', 'PCS', 'pc', 'COUNT', false, 0, true),
 (NULL, 'Box', 'BOX', 'box', 'COUNT', false, 0, true),
 (NULL, 'Carton', 'CTN', 'ctn', 'COUNT', false, 0, true),
 (NULL, 'Kilogram', 'KG', 'kg', 'WEIGHT', true, 3, true),
 (NULL, 'Litre', 'L', 'L', 'VOLUME', true, 3, true),
 (NULL, 'Metre', 'M', 'm', 'LENGTH', true, 3, true)
ON CONFLICT DO NOTHING;
