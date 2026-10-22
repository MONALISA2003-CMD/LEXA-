-- Phase 7 purchasing completion: supplier identity, landed-cost allocation,
-- supplier bills/payments and a traceable supplier payable ledger.
-- Forward-only; never mutates the historical migration ledger.
BEGIN;

-- The reconstructed purchase-order base did not carry an updated_at field even
-- though the lifecycle API writes it; make the forward schema match the API contract.
ALTER TABLE public.purchase_orders ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

-- The domain uses parties/supplier_profiles for the tenant-scoped supplier identity.
-- Link the legacy suppliers catalog so supplier-specific SKU/pricing records can be used.
ALTER TABLE public.suppliers ADD COLUMN IF NOT EXISTS supplier_party_id uuid;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='suppliers_tenant_party_fk') THEN
    ALTER TABLE public.suppliers ADD CONSTRAINT suppliers_tenant_party_fk
      FOREIGN KEY (tenant_id,supplier_party_id) REFERENCES public.parties(tenant_id,id) ON DELETE RESTRICT;
  END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_suppliers_tenant_party
  ON public.suppliers(tenant_id,supplier_party_id) WHERE supplier_party_id IS NOT NULL;

ALTER TABLE public.purchase_receipts ADD COLUMN IF NOT EXISTS landed_cost_total numeric NOT NULL DEFAULT 0;
ALTER TABLE public.purchase_receipts ADD COLUMN IF NOT EXISTS landed_cost_allocation_method varchar NOT NULL DEFAULT 'BY_VALUE';
ALTER TABLE public.purchase_receipt_lines ADD COLUMN IF NOT EXISTS base_unit_cost numeric;
ALTER TABLE public.purchase_receipt_lines ADD COLUMN IF NOT EXISTS landed_cost_amount numeric NOT NULL DEFAULT 0;
ALTER TABLE public.purchase_return_lines ADD COLUMN IF NOT EXISTS supplier_credit_unit_cost numeric(20,6);
UPDATE public.purchase_receipt_lines SET base_unit_cost=unit_cost WHERE base_unit_cost IS NULL;
UPDATE public.purchase_return_lines prl SET supplier_credit_unit_cost=COALESCE((SELECT r.base_unit_cost FROM public.purchase_receipt_lines r WHERE r.tenant_id=prl.tenant_id AND r.id=prl.purchase_receipt_line_id),prl.unit_cost) WHERE supplier_credit_unit_cost IS NULL;
ALTER TABLE public.purchase_return_lines ALTER COLUMN supplier_credit_unit_cost SET NOT NULL;
ALTER TABLE public.purchase_receipt_lines ALTER COLUMN base_unit_cost SET NOT NULL;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='purchase_receipts_landed_cost_method_ck') THEN
    ALTER TABLE public.purchase_receipts ADD CONSTRAINT purchase_receipts_landed_cost_method_ck
      CHECK (landed_cost_allocation_method IN ('BY_VALUE','BY_QUANTITY','EQUALLY'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='purchase_receipts_landed_cost_total_ck') THEN
    ALTER TABLE public.purchase_receipts ADD CONSTRAINT purchase_receipts_landed_cost_total_ck CHECK(landed_cost_total>=0);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='purchase_return_lines_supplier_credit_cost_ck') THEN
    ALTER TABLE public.purchase_return_lines ADD CONSTRAINT purchase_return_lines_supplier_credit_cost_ck CHECK(supplier_credit_unit_cost>0);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='purchase_receipt_lines_base_cost_ck') THEN
    ALTER TABLE public.purchase_receipt_lines ADD CONSTRAINT purchase_receipt_lines_base_cost_ck CHECK(base_unit_cost>0 AND landed_cost_amount>=0);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.purchase_landed_costs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  receipt_id uuid NOT NULL,
  cost_code varchar(40) NOT NULL,
  description varchar(240) NOT NULL,
  amount numeric(20,2) NOT NULL CHECK(amount>0),
  currency_code varchar(3) NOT NULL CHECK(currency_code ~ '^[A-Z]{3}$'),
  allocation_method varchar(20) NOT NULL DEFAULT 'BY_VALUE' CHECK(allocation_method IN ('BY_VALUE','BY_QUANTITY','EQUALLY')),
  reference varchar(120),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT purchase_landed_cost_receipt_fk FOREIGN KEY(tenant_id,receipt_id)
    REFERENCES public.purchase_receipts(tenant_id,id) ON DELETE CASCADE,
  UNIQUE(tenant_id,id)
);
CREATE INDEX IF NOT EXISTS idx_purchase_landed_costs_receipt ON public.purchase_landed_costs(tenant_id,receipt_id,created_at);

CREATE TABLE IF NOT EXISTS public.purchase_landed_cost_allocations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  landed_cost_id uuid NOT NULL,
  receipt_line_id uuid NOT NULL,
  allocated_amount numeric(20,2) NOT NULL CHECK(allocated_amount>=0),
  allocation_method varchar(20) NOT NULL CHECK(allocation_method IN ('BY_VALUE','BY_QUANTITY','EQUALLY')),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT plc_alloc_cost_fk FOREIGN KEY(tenant_id,landed_cost_id) REFERENCES public.purchase_landed_costs(tenant_id,id) ON DELETE CASCADE,
  CONSTRAINT plc_alloc_line_fk FOREIGN KEY(tenant_id,receipt_line_id) REFERENCES public.purchase_receipt_lines(tenant_id,id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,landed_cost_id,receipt_line_id)
);
CREATE INDEX IF NOT EXISTS idx_purchase_landed_alloc_line ON public.purchase_landed_cost_allocations(tenant_id,receipt_line_id);

CREATE TABLE IF NOT EXISTS public.supplier_bills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  supplier_party_id uuid NOT NULL,
  purchase_order_id uuid,
  purchase_receipt_id uuid,
  bill_number varchar(100) NOT NULL,
  bill_date date NOT NULL,
  due_date date NOT NULL,
  currency_code varchar(3) NOT NULL CHECK(currency_code ~ '^[A-Z]{3}$'),
  subtotal numeric(20,2) NOT NULL CHECK(subtotal>=0),
  tax_amount numeric(20,2) NOT NULL DEFAULT 0 CHECK(tax_amount>=0),
  other_charges numeric(20,2) NOT NULL DEFAULT 0 CHECK(other_charges>=0),
  total numeric(20,2) NOT NULL CHECK(total>0),
  status varchar(20) NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','POSTED','VOID')),
  supplier_reference varchar(120),
  match_status varchar(24) NOT NULL DEFAULT 'NOT_LINKED' CHECK(match_status IN ('NOT_LINKED','WAITING_RECEIPT','MATCHED','VARIANCE','OVERRIDDEN')),
  match_variance numeric(20,2) NOT NULL DEFAULT 0,
  match_reason text,
  match_checked_at timestamptz,
  match_reviewed_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  notes text,
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  posted_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  posted_at timestamptz,
  CONSTRAINT supplier_bills_total_ck CHECK(total=subtotal+tax_amount+other_charges),
  CONSTRAINT supplier_bills_party_fk FOREIGN KEY(tenant_id,supplier_party_id) REFERENCES public.parties(tenant_id,id) ON DELETE RESTRICT,
  CONSTRAINT supplier_bills_po_fk FOREIGN KEY(tenant_id,purchase_order_id) REFERENCES public.purchase_orders(tenant_id,id) ON DELETE RESTRICT,
  CONSTRAINT supplier_bills_receipt_fk FOREIGN KEY(tenant_id,purchase_receipt_id) REFERENCES public.purchase_receipts(tenant_id,id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,id), UNIQUE(tenant_id,supplier_party_id,bill_number)
);
CREATE INDEX IF NOT EXISTS idx_supplier_bills_open_due ON public.supplier_bills(tenant_id,supplier_party_id,currency_code,due_date) WHERE status='POSTED';
CREATE INDEX IF NOT EXISTS idx_supplier_bills_receipt ON public.supplier_bills(tenant_id,purchase_receipt_id);

CREATE TABLE IF NOT EXISTS public.supplier_payments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  supplier_party_id uuid NOT NULL,
  payment_number varchar(100) NOT NULL,
  payment_date date NOT NULL,
  currency_code varchar(3) NOT NULL CHECK(currency_code ~ '^[A-Z]{3}$'),
  amount numeric(20,2) NOT NULL CHECK(amount>0),
  payment_method varchar(30) NOT NULL CHECK(payment_method IN ('CASH','BANK_TRANSFER','MOBILE_MONEY','CHEQUE','CARD','OTHER')),
  reference varchar(120),
  notes text,
  status varchar(20) NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','POSTED','VOID')),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  posted_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  posted_at timestamptz,
  CONSTRAINT supplier_payments_party_fk FOREIGN KEY(tenant_id,supplier_party_id) REFERENCES public.parties(tenant_id,id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,id), UNIQUE(tenant_id,payment_number)
);
CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier_date ON public.supplier_payments(tenant_id,supplier_party_id,currency_code,payment_date DESC);

CREATE TABLE IF NOT EXISTS public.supplier_payment_allocations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  payment_id uuid NOT NULL,
  bill_id uuid NOT NULL,
  amount numeric(20,2) NOT NULL CHECK(amount>0),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT spa_payment_fk FOREIGN KEY(tenant_id,payment_id) REFERENCES public.supplier_payments(tenant_id,id) ON DELETE CASCADE,
  CONSTRAINT spa_bill_fk FOREIGN KEY(tenant_id,bill_id) REFERENCES public.supplier_bills(tenant_id,id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,payment_id,bill_id)
);
CREATE INDEX IF NOT EXISTS idx_supplier_allocations_bill ON public.supplier_payment_allocations(tenant_id,bill_id);

CREATE TABLE IF NOT EXISTS public.supplier_ledger_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  supplier_party_id uuid NOT NULL,
  currency_code varchar(3) NOT NULL CHECK(currency_code ~ '^[A-Z]{3}$'),
  entry_type varchar(30) NOT NULL CHECK(entry_type IN ('BILL','PAYMENT','RETURN_CREDIT','ADJUSTMENT')),
  source_type varchar(40) NOT NULL,
  source_id uuid NOT NULL,
  reference varchar(120),
  debit_amount numeric(20,2) NOT NULL DEFAULT 0 CHECK(debit_amount>=0),
  credit_amount numeric(20,2) NOT NULL DEFAULT 0 CHECK(credit_amount>=0),
  occurred_at timestamptz NOT NULL DEFAULT now(),
  actor_user_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT supplier_ledger_party_fk FOREIGN KEY(tenant_id,supplier_party_id) REFERENCES public.parties(tenant_id,id) ON DELETE RESTRICT,
  CONSTRAINT supplier_ledger_one_side_ck CHECK ((debit_amount>0 AND credit_amount=0) OR (credit_amount>0 AND debit_amount=0)),
  UNIQUE(tenant_id,id), UNIQUE(tenant_id,source_type,source_id,entry_type)
);
CREATE INDEX IF NOT EXISTS idx_supplier_ledger_balance ON public.supplier_ledger_entries(tenant_id,supplier_party_id,currency_code,occurred_at,id);
CREATE INDEX IF NOT EXISTS idx_supplier_bills_tenant_status_due ON public.supplier_bills(tenant_id,status,due_date);
DO $$ DECLARE duplicate_tiers integer; BEGIN
  SELECT count(*) INTO duplicate_tiers FROM (
    SELECT tenant_id,supplier_party_id,variant_id,currency_code,minimum_quantity
    FROM public.supplier_variant_costs WHERE effective_to IS NULL
    GROUP BY tenant_id,supplier_party_id,variant_id,currency_code,minimum_quantity HAVING count(*)>1
  ) d;
  IF duplicate_tiers > 0 THEN
    RAISE EXCEPTION 'Phase 7 migration blocked: % duplicate active supplier-cost tiers exist. Resolve the duplicates with an audited supersession before replay/deploy.',duplicate_tiers;
  END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_variant_cost_active_tier ON public.supplier_variant_costs(tenant_id,supplier_party_id,variant_id,currency_code,minimum_quantity) WHERE effective_to IS NULL;
CREATE INDEX IF NOT EXISTS idx_supplier_payment_allocations_bill ON public.supplier_payment_allocations(tenant_id,bill_id,payment_id);

-- Every new purchasing finance/inventory table uses forced tenant RLS.
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['purchase_landed_costs','purchase_landed_cost_allocations','supplier_bills','supplier_payments','supplier_payment_allocations','supplier_ledger_entries'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',t);
    EXECUTE format('DROP POLICY IF EXISTS %I_tenant_isolation ON public.%I',t,t);
    EXECUTE format('CREATE POLICY %I_tenant_isolation ON public.%I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'',true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'',true), '''')::uuid)',t,t);
  END LOOP;
END $$;
-- Keep ledger/allocation rows append-only at the runtime privilege boundary.
-- Business corrections must go through explicit return/adjustment/reversal workflows.
REVOKE ALL PRIVILEGES ON TABLE public.purchase_landed_costs,public.purchase_landed_cost_allocations,public.supplier_bills,public.supplier_payments,public.supplier_payment_allocations,public.supplier_ledger_entries FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TABLE public.purchase_landed_costs,public.purchase_landed_cost_allocations,public.supplier_bills,public.supplier_payments,public.supplier_payment_allocations,public.supplier_ledger_entries FROM lexa_app;
GRANT SELECT,INSERT ON public.purchase_landed_costs,public.purchase_landed_cost_allocations,public.supplier_payment_allocations,public.supplier_ledger_entries TO lexa_app;
GRANT SELECT,INSERT,UPDATE ON public.supplier_bills,public.supplier_payments TO lexa_app;

INSERT INTO public.permissions(code,description) VALUES
 ('purchasing.bills.manage','Record, review and post supplier invoices'),
 ('purchasing.payments.manage','Record and post supplier payments')
ON CONFLICT(code) DO NOTHING;
INSERT INTO public.role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM public.roles r JOIN public.permissions p ON p.code='purchasing.bills.manage'
 WHERE r.name IN ('Owner','Administrator','Manager','Finance / Accounting')
ON CONFLICT DO NOTHING;
INSERT INTO public.role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM public.roles r JOIN public.permissions p ON p.code='purchasing.payments.manage'
 WHERE r.name IN ('Owner','Administrator','Finance / Accounting')
ON CONFLICT DO NOTHING;

INSERT INTO public.schema_migrations(version) VALUES ('039_phase7_supplier_ledger_landed_costs') ON CONFLICT(version) DO NOTHING;
COMMIT;
