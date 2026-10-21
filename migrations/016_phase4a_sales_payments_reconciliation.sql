BEGIN;

-- Phase 4A sales, payments, receivables and reconciliation foundation.
-- Additive and tenant-scoped. This migration is safe to replay with IF NOT EXISTS guards.

ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_channel_id uuid;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS business_date date NOT NULL DEFAULT CURRENT_DATE;

CREATE TABLE IF NOT EXISTS customer_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  party_id uuid NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
  credit_limit numeric NOT NULL DEFAULT 0 CHECK (credit_limit >= 0),
  status varchar(30) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','BLOCKED','ARCHIVED')),
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  UNIQUE (tenant_id,party_id),
  CONSTRAINT fk_customer_party_tenant FOREIGN KEY (tenant_id,party_id) REFERENCES parties(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS payment_channels (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar(160) NOT NULL,
  channel_type varchar(30) NOT NULL CHECK (channel_type IN ('CASH','MOBILE_MONEY','BANK','CARD','CHEQUE','OTHER')),
  provider varchar(100),
  currency_code varchar(3) NOT NULL,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id)
);

CREATE TABLE IF NOT EXISTS sales (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  transaction_id uuid NOT NULL REFERENCES business_transactions(id) ON DELETE RESTRICT,
  customer_party_id uuid,
  branch_id uuid,
  location_id uuid,
  currency_code varchar(3) NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','COMPLETED','VOIDED','CANCELLED')),
  subtotal numeric NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
  discount_total numeric NOT NULL DEFAULT 0 CHECK (discount_total >= 0),
  tax_total numeric NOT NULL DEFAULT 0 CHECK (tax_total >= 0),
  total numeric NOT NULL DEFAULT 0 CHECK (total >= 0),
  amount_paid numeric NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
  amount_due numeric NOT NULL DEFAULT 0 CHECK (amount_due >= 0),
  return_adjustment_amount numeric NOT NULL DEFAULT 0 CHECK (return_adjustment_amount >= 0),
  notes text,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  completed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  UNIQUE (tenant_id,transaction_id),
  CONSTRAINT fk_sales_transaction_tenant FOREIGN KEY (tenant_id,transaction_id) REFERENCES business_transactions(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_sales_customer_tenant FOREIGN KEY (tenant_id,customer_party_id) REFERENCES parties(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_sales_branch_tenant FOREIGN KEY (tenant_id,branch_id) REFERENCES branches(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_sales_location_tenant FOREIGN KEY (tenant_id,location_id) REFERENCES locations(tenant_id,id)
);

CREATE TABLE IF NOT EXISTS receivables (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  sale_id uuid NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
  customer_party_id uuid NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
  original_amount numeric NOT NULL CHECK (original_amount > 0),
  paid_amount numeric NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
  adjustment_amount numeric NOT NULL DEFAULT 0 CHECK (adjustment_amount >= 0),
  balance numeric NOT NULL DEFAULT 0 CHECK (balance >= 0),
  status varchar(30) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','PARTIALLY_PAID','PAID','WRITTEN_OFF','CANCELLED')),
  due_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  UNIQUE (tenant_id,sale_id),
  CONSTRAINT receivables_check CHECK ((paid_amount <= original_amount) OR status IN ('PAID','WRITTEN_OFF','CANCELLED')),
  CONSTRAINT receivables_check1 CHECK ((balance = GREATEST(original_amount-paid_amount-adjustment_amount,0)) OR status IN ('WRITTEN_OFF','CANCELLED')),
  CONSTRAINT fk_receivable_sale_tenant FOREIGN KEY (tenant_id,sale_id) REFERENCES sales(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_receivable_party_tenant FOREIGN KEY (tenant_id,customer_party_id) REFERENCES parties(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS payment_allocations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  payment_id uuid NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
  sale_id uuid REFERENCES sales(id) ON DELETE RESTRICT,
  receivable_id uuid REFERENCES receivables(id) ON DELETE RESTRICT,
  amount numeric NOT NULL CHECK (amount > 0),
  status varchar(30) NOT NULL DEFAULT 'RECORDED' CHECK (status IN ('RECORDED','REVERSED')),
  allocated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  UNIQUE (tenant_id,id),
  CONSTRAINT payment_alloc_target_check CHECK ((sale_id IS NOT NULL) <> (receivable_id IS NOT NULL)),
  CONSTRAINT fk_payment_alloc_payment_tenant FOREIGN KEY (tenant_id,payment_id) REFERENCES payments(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_payment_alloc_sale_tenant FOREIGN KEY (tenant_id,sale_id) REFERENCES sales(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_payment_alloc_receivable_tenant FOREIGN KEY (tenant_id,receivable_id) REFERENCES receivables(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS sale_returns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  sale_id uuid NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
  transaction_id uuid NOT NULL REFERENCES business_transactions(id) ON DELETE RESTRICT,
  inventory_location_id uuid,
  status varchar(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','COMPLETED','CANCELLED')),
  reason varchar(240) NOT NULL,
  total numeric NOT NULL DEFAULT 0 CHECK (total >= 0),
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  completed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  UNIQUE (tenant_id,transaction_id),
  CONSTRAINT fk_sale_return_sale_tenant FOREIGN KEY (tenant_id,sale_id) REFERENCES sales(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_sale_return_transaction_tenant FOREIGN KEY (tenant_id,transaction_id) REFERENCES business_transactions(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_sale_return_location_tenant FOREIGN KEY (tenant_id,inventory_location_id) REFERENCES locations(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS sale_return_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  return_id uuid NOT NULL REFERENCES sale_returns(id) ON DELETE CASCADE,
  sale_line_id uuid NOT NULL REFERENCES transaction_lines(id) ON DELETE RESTRICT,
  variant_id uuid REFERENCES product_variants(id) ON DELETE RESTRICT,
  quantity numeric NOT NULL CHECK (quantity > 0),
  unit_price numeric NOT NULL CHECK (unit_price >= 0),
  discount_amount numeric NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  tax_amount numeric NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
  line_total numeric NOT NULL CHECK (line_total >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  UNIQUE (tenant_id,return_id,sale_line_id),
  CONSTRAINT fk_sale_return_line_header_tenant FOREIGN KEY (tenant_id,return_id) REFERENCES sale_returns(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_sale_return_line_line_tenant FOREIGN KEY (tenant_id,sale_line_id) REFERENCES transaction_lines(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_sale_return_line_variant_tenant FOREIGN KEY (tenant_id,variant_id) REFERENCES product_variants(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS refund_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  return_id uuid NOT NULL REFERENCES sale_returns(id) ON DELETE RESTRICT,
  payment_channel_id uuid NOT NULL REFERENCES payment_channels(id) ON DELETE RESTRICT,
  amount numeric NOT NULL CHECK (amount > 0),
  currency_code varchar(3) NOT NULL,
  reference varchar(120),
  status varchar(30) NOT NULL DEFAULT 'RECORDED' CHECK (status IN ('RECORDED','VOIDED','REVERSED')),
  business_date date NOT NULL DEFAULT CURRENT_DATE,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  CONSTRAINT fk_refund_return_tenant FOREIGN KEY (tenant_id,return_id) REFERENCES sale_returns(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_refund_channel_tenant FOREIGN KEY (tenant_id,payment_channel_id) REFERENCES payment_channels(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS customer_credits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  customer_party_id uuid NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
  source_return_id uuid NOT NULL REFERENCES sale_returns(id) ON DELETE RESTRICT,
  original_amount numeric NOT NULL CHECK (original_amount > 0),
  allocated_amount numeric NOT NULL DEFAULT 0 CHECK (allocated_amount >= 0),
  balance numeric NOT NULL CHECK (balance >= 0),
  status varchar(30) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','PARTIALLY_USED','USED','CANCELLED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  UNIQUE (tenant_id,source_return_id),
  CONSTRAINT customer_credits_check CHECK (allocated_amount <= original_amount),
  CONSTRAINT customer_credits_check1 CHECK (balance = original_amount-allocated_amount),
  CONSTRAINT fk_customer_credit_party_tenant FOREIGN KEY (tenant_id,customer_party_id) REFERENCES parties(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS customer_credit_allocations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  customer_credit_id uuid NOT NULL REFERENCES customer_credits(id) ON DELETE RESTRICT,
  receivable_id uuid NOT NULL REFERENCES receivables(id) ON DELETE RESTRICT,
  amount numeric NOT NULL CHECK (amount > 0),
  status varchar(30) NOT NULL DEFAULT 'RECORDED' CHECK (status IN ('RECORDED','REVERSED')),
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  CONSTRAINT fk_credit_alloc_credit_tenant FOREIGN KEY (tenant_id,customer_credit_id) REFERENCES customer_credits(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_credit_alloc_receivable_tenant FOREIGN KEY (tenant_id,receivable_id) REFERENCES receivables(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS daily_reconciliations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  business_date date NOT NULL,
  status varchar(40) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RECONCILIATION_PENDING','VARIANCE_DETECTED','UNDER_REVIEW','RECONCILED','RESOLVED','ACKNOWLEDGED','CLOSED')),
  notes text,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  closed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  closed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  UNIQUE (tenant_id,business_date)
);

CREATE TABLE IF NOT EXISTS daily_reconciliation_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  reconciliation_id uuid NOT NULL REFERENCES daily_reconciliations(id) ON DELETE CASCADE,
  payment_channel_id uuid NOT NULL REFERENCES payment_channels(id) ON DELETE RESTRICT,
  expected_amount numeric NOT NULL DEFAULT 0,
  actual_amount numeric,
  variance numeric,
  status varchar(30) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','VARIANCE_DETECTED','RESOLVED','ACKNOWLEDGED','CLOSED')),
  notes text,
  reviewed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,id),
  UNIQUE (tenant_id,reconciliation_id,payment_channel_id),
  CONSTRAINT fk_recon_line_header_tenant FOREIGN KEY (tenant_id,reconciliation_id) REFERENCES daily_reconciliations(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_recon_line_channel_tenant FOREIGN KEY (tenant_id,payment_channel_id) REFERENCES payment_channels(tenant_id,id) DEFERRABLE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_channels_tenant_name ON payment_channels(tenant_id,name);
CREATE INDEX IF NOT EXISTS idx_customer_profiles_tenant ON customer_profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_payment_channels_tenant_active ON payment_channels(tenant_id,active);
CREATE INDEX IF NOT EXISTS idx_sales_tenant_created_at ON sales(tenant_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_receivables_tenant_status ON receivables(tenant_id,status);
CREATE INDEX IF NOT EXISTS idx_payment_allocations_payment ON payment_allocations(tenant_id,payment_id);
CREATE INDEX IF NOT EXISTS idx_daily_reconciliations_tenant_date ON daily_reconciliations(tenant_id,business_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_reconciliation_lines_recon ON daily_reconciliation_lines(tenant_id,reconciliation_id);

UPDATE payments SET business_date = COALESCE(business_date, paid_at::date) WHERE business_date IS NULL;

ALTER TABLE customer_profiles ENABLE ROW LEVEL SECURITY; ALTER TABLE customer_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_channels ENABLE ROW LEVEL SECURITY; ALTER TABLE payment_channels FORCE ROW LEVEL SECURITY;
ALTER TABLE sales ENABLE ROW LEVEL SECURITY; ALTER TABLE sales FORCE ROW LEVEL SECURITY;
ALTER TABLE receivables ENABLE ROW LEVEL SECURITY; ALTER TABLE receivables FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_allocations ENABLE ROW LEVEL SECURITY; ALTER TABLE payment_allocations FORCE ROW LEVEL SECURITY;
ALTER TABLE sale_returns ENABLE ROW LEVEL SECURITY; ALTER TABLE sale_returns FORCE ROW LEVEL SECURITY;
ALTER TABLE sale_return_lines ENABLE ROW LEVEL SECURITY; ALTER TABLE sale_return_lines FORCE ROW LEVEL SECURITY;
ALTER TABLE refund_records ENABLE ROW LEVEL SECURITY; ALTER TABLE refund_records FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_credits ENABLE ROW LEVEL SECURITY; ALTER TABLE customer_credits FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_credit_allocations ENABLE ROW LEVEL SECURITY; ALTER TABLE customer_credit_allocations FORCE ROW LEVEL SECURITY;
ALTER TABLE daily_reconciliations ENABLE ROW LEVEL SECURITY; ALTER TABLE daily_reconciliations FORCE ROW LEVEL SECURITY;
ALTER TABLE daily_reconciliation_lines ENABLE ROW LEVEL SECURITY; ALTER TABLE daily_reconciliation_lines FORCE ROW LEVEL SECURITY;

DO $pol$ DECLARE t text; BEGIN FOREACH t IN ARRAY ARRAY['customer_profiles','payment_channels','sales','receivables','payment_allocations','sale_returns','sale_return_lines','refund_records','customer_credits','customer_credit_allocations','daily_reconciliations','daily_reconciliation_lines'] LOOP EXECUTE format('DROP POLICY IF EXISTS %I_tenant_isolation ON %I',t,t); EXECUTE format('CREATE POLICY %I_tenant_isolation ON %I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)',t,t); END LOOP; END $pol$;

INSERT INTO permissions (code,description) VALUES
  ('customers.read','Read customers'),('customers.manage','Manage customers'),('returns.manage','Process returns'),('refunds.manage','Manage refunds'),('credits.read','Read customer credits'),('credits.manage','Manage customer credits')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions(role_id,permission_id)
SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code IN ('customers.read','customers.manage','returns.manage','refunds.manage','credits.read','credits.manage') WHERE r.name IN ('Owner','Admin') ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations(version) VALUES ('016_phase4a_sales_payments_reconciliation') ON CONFLICT (version) DO NOTHING;
COMMIT;
