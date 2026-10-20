-- RECONSTRUCTED OBSERVED-SCHEMA COMPATIBILITY DELTA — NOT A HISTORICAL MIGRATION.
-- Derived from schema inspection of the LEXA canonical clone, not from historical SQL bytes.
-- Apply only on a disposable/isolated replay database. This is not approved for production.
BEGIN;

-- Audit metadata present in the observed schema but absent from the available 001 source.
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS actor_type varchar;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_type varchar;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_id uuid;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS result varchar;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_id uuid;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip_hash varchar;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_agent text;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS before_data jsonb;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS after_data jsonb;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS metadata jsonb;

-- Tax/discount fields were observed as NOT NULL DEFAULT 0 in the canonical contract.
ALTER TABLE transaction_lines ADD COLUMN IF NOT EXISTS discount_amount numeric NOT NULL DEFAULT 0;
ALTER TABLE transaction_lines ADD COLUMN IF NOT EXISTS tax_rate numeric NOT NULL DEFAULT 0;
ALTER TABLE transaction_lines ADD COLUMN IF NOT EXISTS tax_amount numeric NOT NULL DEFAULT 0;
ALTER TABLE idempotency_keys ALTER COLUMN response_json SET DEFAULT '{}'::jsonb;

DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.transaction_lines'::regclass AND conname='transaction_lines_tenant_id_id_key') THEN
   ALTER TABLE transaction_lines ADD CONSTRAINT transaction_lines_tenant_id_id_key UNIQUE(tenant_id,id);
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.transaction_lines'::regclass AND conname='transaction_lines_discount_check') THEN
   ALTER TABLE transaction_lines ADD CONSTRAINT transaction_lines_discount_check CHECK(discount_amount>=0 AND discount_amount<=quantity*unit_price);
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.transaction_lines'::regclass AND conname='transaction_lines_tax_rate_check') THEN
   ALTER TABLE transaction_lines ADD CONSTRAINT transaction_lines_tax_rate_check CHECK(tax_rate>=0 AND tax_rate<=100);
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.transaction_lines'::regclass AND conname='transaction_lines_tax_amount_check') THEN
   ALTER TABLE transaction_lines ADD CONSTRAINT transaction_lines_tax_amount_check CHECK(tax_amount>=0);
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.payment_channels'::regclass AND conname='payment_channels_tenant_id_name_key') THEN
   ALTER TABLE payment_channels ADD CONSTRAINT payment_channels_tenant_id_name_key UNIQUE(tenant_id,name);
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.payments'::regclass AND conname='fk_payments_channel_tenant') THEN
   ALTER TABLE payments ADD CONSTRAINT fk_payments_channel_tenant FOREIGN KEY(tenant_id,payment_channel_id) REFERENCES payment_channels(tenant_id,id) DEFERRABLE;
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.payments'::regclass AND conname='payments_amount_check') THEN
   ALTER TABLE payments ADD CONSTRAINT payments_amount_check CHECK(amount>0);
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.sales'::regclass AND conname='sales_branch_id_fkey') THEN
   ALTER TABLE sales ADD CONSTRAINT sales_branch_id_fkey FOREIGN KEY(branch_id) REFERENCES branches(id) ON DELETE SET NULL;
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.sales'::regclass AND conname='sales_customer_party_id_fkey') THEN
   ALTER TABLE sales ADD CONSTRAINT sales_customer_party_id_fkey FOREIGN KEY(customer_party_id) REFERENCES parties(id) ON DELETE SET NULL;
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.sales'::regclass AND conname='sales_location_id_fkey') THEN
   ALTER TABLE sales ADD CONSTRAINT sales_location_id_fkey FOREIGN KEY(location_id) REFERENCES locations(id) ON DELETE RESTRICT;
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.sales'::regclass AND conname='sales_check') THEN
   ALTER TABLE sales ADD CONSTRAINT sales_check CHECK(amount_paid<=total OR status='VOIDED');
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.sale_returns'::regclass AND conname='sale_returns_inventory_location_id_fkey') THEN
   ALTER TABLE sale_returns ADD CONSTRAINT sale_returns_inventory_location_id_fkey FOREIGN KEY(inventory_location_id) REFERENCES locations(id) ON DELETE RESTRICT;
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.brain_runs'::regclass AND conname='fk_brain_run_actor') THEN
   ALTER TABLE brain_runs ADD CONSTRAINT fk_brain_run_actor FOREIGN KEY(actor_user_id) REFERENCES users(id) DEFERRABLE;
 END IF;
END $$;

-- Restore query-serving indexes recorded in the canonical schema. Existing equivalent indexes are not dropped.
CREATE INDEX IF NOT EXISTS idx_categories_name_trgm_active ON categories USING gin(lower(name) gin_trgm_ops) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_brands_name_trgm_active ON brands USING gin(lower(name) gin_trgm_ops) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_customer_credit_allocations_tenant_credit ON customer_credit_allocations(tenant_id,customer_credit_id);
CREATE INDEX IF NOT EXISTS idx_customer_credit_allocations_tenant_receivable ON customer_credit_allocations(tenant_id,receivable_id);
CREATE INDEX IF NOT EXISTS idx_customer_credits_tenant_customer ON customer_credits(tenant_id,customer_party_id,status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_customer_profiles_tenant_status ON customer_profiles(tenant_id,status);
CREATE INDEX IF NOT EXISTS idx_recon_lines_tenant_header ON daily_reconciliation_lines(tenant_id,reconciliation_id);
CREATE INDEX IF NOT EXISTS idx_recon_tenant_date ON daily_reconciliations(tenant_id,business_date DESC);
CREATE INDEX IF NOT EXISTS idx_mba_tenant_branch ON membership_branch_assignments(tenant_id,branch_id,status);
CREATE INDEX IF NOT EXISTS idx_payment_allocations_tenant_payment ON payment_allocations(tenant_id,payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_allocations_tenant_receivable ON payment_allocations(tenant_id,receivable_id);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_channel_date ON payments(tenant_id,payment_channel_id,business_date,paid_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_channel_date_status ON payments(tenant_id,payment_channel_id,business_date,status);
CREATE INDEX IF NOT EXISTS idx_purchase_history_po ON purchase_order_status_history(tenant_id,purchase_order_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_receivables_tenant_customer_status ON receivables(tenant_id,customer_party_id,status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_refunds_tenant_channel_date ON refund_records(tenant_id,payment_channel_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_refunds_tenant_channel_date_status ON refund_records(tenant_id,payment_channel_id,business_date,status);
CREATE INDEX IF NOT EXISTS idx_returns_tenant_sale ON sale_returns(tenant_id,sale_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sales_tenant_customer ON sales(tenant_id,customer_party_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sales_tenant_status_date ON sales(tenant_id,status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sales_tenant_transaction ON sales(tenant_id,transaction_id);
CREATE INDEX IF NOT EXISTS idx_supplier_profiles_tenant_status ON supplier_profiles(tenant_id,status);
COMMIT;
