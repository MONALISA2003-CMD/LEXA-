-- LEXA Phase 3: inventory foundation
-- Safe additive migration. No existing business data is deleted or reseeded.

CREATE TABLE IF NOT EXISTS idempotency_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  operation varchar(160) NOT NULL,
  key varchar(200) NOT NULL,
  request_hash varchar(64) NOT NULL,
  response_status integer NOT NULL DEFAULT 200,
  response_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  UNIQUE (tenant_id, operation, key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expiry ON idempotency_keys(expires_at);

CREATE TABLE IF NOT EXISTS inventory_balances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  location_id uuid NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
  on_hand numeric(20,6) NOT NULL DEFAULT 0,
  reserved numeric(20,6) NOT NULL DEFAULT 0,
  inbound numeric(20,6) NOT NULL DEFAULT 0,
  average_cost numeric(20,6) NOT NULL DEFAULT 0,
  stock_value numeric(24,6) NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, location_id, variant_id),
  CHECK (on_hand >= 0),
  CHECK (reserved >= 0),
  CHECK (inbound >= 0),
  CHECK (average_cost >= 0),
  CHECK (stock_value >= 0)
);
CREATE INDEX IF NOT EXISTS idx_inventory_balances_tenant_location ON inventory_balances(tenant_id, location_id);
CREATE INDEX IF NOT EXISTS idx_inventory_balances_tenant_variant ON inventory_balances(tenant_id, variant_id);

CREATE TABLE IF NOT EXISTS inventory_transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  location_id uuid NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
  transaction_type varchar(40) NOT NULL,
  quantity_delta numeric(20,6) NOT NULL CHECK (quantity_delta <> 0),
  unit_cost numeric(20,6) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
  total_cost numeric(24,6) NOT NULL DEFAULT 0 CHECK (total_cost >= 0),
  balance_after numeric(20,6) NOT NULL,
  reference_type varchar(80),
  reference_id uuid,
  source_transaction_id uuid REFERENCES inventory_transactions(id) ON DELETE RESTRICT,
  idempotency_key varchar(200),
  actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_inventory_ledger_tenant_location_time ON inventory_transactions(tenant_id, location_id, occurred_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_ledger_tenant_variant_time ON inventory_transactions(tenant_id, variant_id, occurred_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_ledger_reference ON inventory_transactions(tenant_id, reference_type, reference_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_transaction_idempotency ON inventory_transactions(tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS inventory_adjustments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  location_id uuid NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
  reason_code varchar(60) NOT NULL,
  notes text,
  status varchar(30) NOT NULL DEFAULT 'DRAFT',
  idempotency_key varchar(200),
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  approved_by uuid REFERENCES users(id) ON DELETE SET NULL,
  posted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  posted_at timestamptz,
  UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_inventory_adjustments_tenant_status ON inventory_adjustments(tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS inventory_adjustment_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  adjustment_id uuid NOT NULL REFERENCES inventory_adjustments(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
  quantity_delta numeric(20,6) NOT NULL CHECK (quantity_delta <> 0),
  unit_cost numeric(20,6) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
  notes text,
  UNIQUE (tenant_id, adjustment_id, variant_id)
);
CREATE INDEX IF NOT EXISTS idx_inventory_adjustment_lines_header ON inventory_adjustment_lines(tenant_id, adjustment_id);

CREATE TABLE IF NOT EXISTS stock_counts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  location_id uuid NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
  status varchar(30) NOT NULL DEFAULT 'DRAFT',
  scope_description text,
  started_at timestamptz,
  submitted_at timestamptz,
  approved_at timestamptz,
  posted_at timestamptz,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  submitted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  approved_by uuid REFERENCES users(id) ON DELETE SET NULL,
  posted_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_stock_counts_tenant_status ON stock_counts(tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS stock_count_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  stock_count_id uuid NOT NULL REFERENCES stock_counts(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
  expected_quantity numeric(20,6) NOT NULL DEFAULT 0,
  counted_quantity numeric(20,6),
  variance_quantity numeric(20,6),
  unit_cost numeric(20,6) NOT NULL DEFAULT 0,
  UNIQUE (tenant_id, stock_count_id, variant_id)
);
CREATE INDEX IF NOT EXISTS idx_stock_count_lines_header ON stock_count_lines(tenant_id, stock_count_id);

CREATE TABLE IF NOT EXISTS inventory_transfers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  source_location_id uuid NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
  destination_location_id uuid NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
  status varchar(30) NOT NULL DEFAULT 'DRAFT',
  notes text,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  approved_by uuid REFERENCES users(id) ON DELETE SET NULL,
  dispatched_by uuid REFERENCES users(id) ON DELETE SET NULL,
  received_by uuid REFERENCES users(id) ON DELETE SET NULL,
  completed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  dispatched_at timestamptz,
  received_at timestamptz,
  completed_at timestamptz,
  CHECK (source_location_id <> destination_location_id)
);
CREATE INDEX IF NOT EXISTS idx_inventory_transfers_tenant_status ON inventory_transfers(tenant_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS inventory_transfer_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  transfer_id uuid NOT NULL REFERENCES inventory_transfers(id) ON DELETE CASCADE,
  variant_id uuid NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
  requested_quantity numeric(20,6) NOT NULL CHECK (requested_quantity > 0),
  dispatched_quantity numeric(20,6) NOT NULL DEFAULT 0 CHECK (dispatched_quantity >= 0),
  received_quantity numeric(20,6) NOT NULL DEFAULT 0 CHECK (received_quantity >= 0),
  unit_cost numeric(20,6) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
  UNIQUE (tenant_id, transfer_id, variant_id),
  CHECK (dispatched_quantity <= requested_quantity),
  CHECK (received_quantity <= dispatched_quantity)
);
CREATE INDEX IF NOT EXISTS idx_inventory_transfer_lines_header ON inventory_transfer_lines(tenant_id, transfer_id);

-- Tenant-consistency composite references.
CREATE UNIQUE INDEX IF NOT EXISTS uq_locations_tenant_id ON locations(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variants_tenant_id_inventory ON product_variants(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_transfers_tenant_id ON inventory_transfers(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_adjustments_tenant_id ON inventory_adjustments(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_counts_tenant_id ON stock_counts(tenant_id, id);

ALTER TABLE inventory_balances DROP CONSTRAINT IF EXISTS fk_inventory_balance_location_tenant;
ALTER TABLE inventory_balances ADD CONSTRAINT fk_inventory_balance_location_tenant FOREIGN KEY (tenant_id, location_id) REFERENCES locations(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_balances DROP CONSTRAINT IF EXISTS fk_inventory_balance_variant_tenant;
ALTER TABLE inventory_balances ADD CONSTRAINT fk_inventory_balance_variant_tenant FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_transactions DROP CONSTRAINT IF EXISTS fk_inventory_tx_location_tenant;
ALTER TABLE inventory_transactions ADD CONSTRAINT fk_inventory_tx_location_tenant FOREIGN KEY (tenant_id, location_id) REFERENCES locations(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_transactions DROP CONSTRAINT IF EXISTS fk_inventory_tx_variant_tenant;
ALTER TABLE inventory_transactions ADD CONSTRAINT fk_inventory_tx_variant_tenant FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_adjustments DROP CONSTRAINT IF EXISTS fk_inventory_adj_location_tenant;
ALTER TABLE inventory_adjustments ADD CONSTRAINT fk_inventory_adj_location_tenant FOREIGN KEY (tenant_id, location_id) REFERENCES locations(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_adjustment_lines DROP CONSTRAINT IF EXISTS fk_inventory_adj_line_header_tenant;
ALTER TABLE inventory_adjustment_lines ADD CONSTRAINT fk_inventory_adj_line_header_tenant FOREIGN KEY (tenant_id, adjustment_id) REFERENCES inventory_adjustments(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_adjustment_lines DROP CONSTRAINT IF EXISTS fk_inventory_adj_line_variant_tenant;
ALTER TABLE inventory_adjustment_lines ADD CONSTRAINT fk_inventory_adj_line_variant_tenant FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE stock_counts DROP CONSTRAINT IF EXISTS fk_stock_count_location_tenant;
ALTER TABLE stock_counts ADD CONSTRAINT fk_stock_count_location_tenant FOREIGN KEY (tenant_id, location_id) REFERENCES locations(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE stock_count_lines DROP CONSTRAINT IF EXISTS fk_stock_count_line_header_tenant;
ALTER TABLE stock_count_lines ADD CONSTRAINT fk_stock_count_line_header_tenant FOREIGN KEY (tenant_id, stock_count_id) REFERENCES stock_counts(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE stock_count_lines DROP CONSTRAINT IF EXISTS fk_stock_count_line_variant_tenant;
ALTER TABLE stock_count_lines ADD CONSTRAINT fk_stock_count_line_variant_tenant FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_transfers DROP CONSTRAINT IF EXISTS fk_transfer_source_location_tenant;
ALTER TABLE inventory_transfers ADD CONSTRAINT fk_transfer_source_location_tenant FOREIGN KEY (tenant_id, source_location_id) REFERENCES locations(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_transfers DROP CONSTRAINT IF EXISTS fk_transfer_destination_location_tenant;
ALTER TABLE inventory_transfers ADD CONSTRAINT fk_transfer_destination_location_tenant FOREIGN KEY (tenant_id, destination_location_id) REFERENCES locations(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_transfer_lines DROP CONSTRAINT IF EXISTS fk_transfer_line_header_tenant;
ALTER TABLE inventory_transfer_lines ADD CONSTRAINT fk_transfer_line_header_tenant FOREIGN KEY (tenant_id, transfer_id) REFERENCES inventory_transfers(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE inventory_transfer_lines DROP CONSTRAINT IF EXISTS fk_transfer_line_variant_tenant;
ALTER TABLE inventory_transfer_lines ADD CONSTRAINT fk_transfer_line_variant_tenant FOREIGN KEY (tenant_id, variant_id) REFERENCES product_variants(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;

-- Inventory and command permissions.
INSERT INTO permissions (code, description) VALUES
 ('inventory.read', 'Read inventory balances and ledger'),
 ('inventory.manage', 'Create and manage inventory adjustments'),
 ('inventory.adjust.approve', 'Approve inventory adjustments'),
 ('inventory.adjust.post', 'Post inventory adjustments'),
 ('inventory.count.manage', 'Create and manage stock counts'),
 ('inventory.count.approve', 'Approve stock counts'),
 ('inventory.count.post', 'Post stock count reconciliations'),
 ('inventory.transfer.create', 'Create inventory transfers'),
 ('inventory.transfer.approve', 'Approve inventory transfers'),
 ('inventory.transfer.dispatch', 'Dispatch inventory transfers'),
 ('inventory.transfer.receive', 'Receive inventory transfers'),
 ('inventory.transfer.complete', 'Complete inventory transfers')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE r.name = 'Owner' ON CONFLICT DO NOTHING;

-- Tenant isolation. Idempotency records are tenant-owned. Inventory ledger/balances are tenant-owned.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['idempotency_keys','inventory_balances','inventory_transactions','inventory_adjustments','inventory_adjustment_lines','stock_counts','stock_count_lines','inventory_transfers','inventory_transfer_lines'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t || '_tenant_isolation', t);
    EXECUTE format('CREATE POLICY %I ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)::uuid) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true)::uuid)', t || '_tenant_isolation', t);
  END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_transactions_tenant_id ON inventory_transactions(tenant_id, id);
ALTER TABLE inventory_transactions DROP CONSTRAINT IF EXISTS fk_inventory_tx_source_tenant;
ALTER TABLE inventory_transactions ADD CONSTRAINT fk_inventory_tx_source_tenant FOREIGN KEY (tenant_id, source_transaction_id) REFERENCES inventory_transactions(tenant_id, id) DEFERRABLE INITIALLY IMMEDIATE;
