-- Phase 7 closeout: fail-closed purchase approval limits, supplier-return reversal,
-- and double-entry posting/reconciliation for purchasing source events.
-- Forward-only; do not run against production without the normal backup/release gate.
BEGIN;

CREATE TABLE IF NOT EXISTS public.purchase_approval_limits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  role_name varchar(100) NOT NULL CHECK(length(btrim(role_name)) >= 2),
  currency_code varchar(3) NOT NULL CHECK(currency_code ~ '^[A-Z]{3}$'),
  max_approval_amount numeric(20,2) NOT NULL CHECK(max_approval_amount >= 0),
  created_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  updated_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, role_name, currency_code),
  UNIQUE(tenant_id, id)
);
ALTER TABLE public.purchase_approval_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_approval_limits FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS purchase_approval_limits_tenant_isolation ON public.purchase_approval_limits;
CREATE POLICY purchase_approval_limits_tenant_isolation ON public.purchase_approval_limits
  FOR ALL
  USING (tenant_id = NULLIF(current_setting('app.tenant_id',true),'')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id',true),'')::uuid);
REVOKE ALL PRIVILEGES ON public.purchase_approval_limits FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.purchase_approval_limits TO lexa_app;

ALTER TABLE public.purchase_returns ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE public.purchase_returns ADD COLUMN IF NOT EXISTS reversed_by uuid REFERENCES public.users(id) ON DELETE SET NULL;
ALTER TABLE public.purchase_returns ADD COLUMN IF NOT EXISTS reversed_at timestamptz;
ALTER TABLE public.purchase_returns ADD COLUMN IF NOT EXISTS reversal_reason text;
ALTER TABLE public.purchase_returns DROP CONSTRAINT IF EXISTS pur_status_check;
ALTER TABLE public.purchase_returns ADD CONSTRAINT pur_status_check
  CHECK(status IN ('REQUESTED','APPROVED','POSTED','REVERSED','CANCELLED'));

ALTER TABLE public.supplier_ledger_entries DROP CONSTRAINT IF EXISTS supplier_ledger_entries_entry_type_check;
ALTER TABLE public.supplier_ledger_entries DROP CONSTRAINT IF EXISTS supplier_ledger_entry_type_ck;
ALTER TABLE public.supplier_ledger_entries ADD CONSTRAINT supplier_ledger_entry_type_ck
  CHECK(entry_type IN ('BILL','PAYMENT','RETURN_CREDIT','RETURN_REVERSAL','ADJUSTMENT'));

INSERT INTO public.permissions(code,description) VALUES
 ('purchasing.approval_limits.manage','Configure purchasing approval limits by role and currency'),
 ('purchasing.returns.reverse','Reverse a posted supplier return with compensating stock, supplier and accounting entries')
ON CONFLICT(code) DO NOTHING;
INSERT INTO public.role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM public.roles r JOIN public.permissions p ON p.code='purchasing.approval_limits.manage'
 WHERE r.name IN ('Owner','Administrator')
ON CONFLICT DO NOTHING;
INSERT INTO public.role_permissions(role_id,permission_id)
 SELECT r.id,p.id FROM public.roles r JOIN public.permissions p ON p.code='purchasing.returns.reverse'
 WHERE r.name IN ('Owner','Administrator')
ON CONFLICT DO NOTHING;

-- Account mappings required for receipt accruals, pre-receipt supplier invoices,
-- advances and price/cost differences. Existing mappings are preserved.
CREATE OR REPLACE FUNCTION public.seed_purchasing_accounting_accounts(p_tenant_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $seed$
DECLARE v_id uuid; v_previous_tenant text;
BEGIN
  -- The account and mapping tables use forced tenant RLS. Switch to the specific
  -- tenant only inside this definer function, then restore the request's context.
  v_previous_tenant := current_setting('app.tenant_id',true);
  PERFORM set_config('app.tenant_id',p_tenant_id::text,true);
  v_id := public.ensure_system_account(p_tenant_id,'2050','Goods Received Not Invoiced','LIABILITY','CREDIT','GOODS_RECEIVED_NOT_INVOICED');
  INSERT INTO public.accounting_mappings(tenant_id,mapping_key,account_id) VALUES(p_tenant_id,'GOODS_RECEIVED_NOT_INVOICED',v_id) ON CONFLICT(tenant_id,mapping_key) DO NOTHING;
  v_id := public.ensure_system_account(p_tenant_id,'2060','Landed Cost Clearing','LIABILITY','CREDIT','LANDED_COST_CLEARING');
  INSERT INTO public.accounting_mappings(tenant_id,mapping_key,account_id) VALUES(p_tenant_id,'LANDED_COST_CLEARING',v_id) ON CONFLICT(tenant_id,mapping_key) DO NOTHING;
  v_id := public.ensure_system_account(p_tenant_id,'1170','Purchases Clearing','ASSET','DEBIT','PURCHASES_CLEARING');
  INSERT INTO public.accounting_mappings(tenant_id,mapping_key,account_id) VALUES(p_tenant_id,'PURCHASES_CLEARING',v_id) ON CONFLICT(tenant_id,mapping_key) DO NOTHING;
  v_id := public.ensure_system_account(p_tenant_id,'1160','Supplier Advances','ASSET','DEBIT','SUPPLIER_ADVANCES');
  INSERT INTO public.accounting_mappings(tenant_id,mapping_key,account_id) VALUES(p_tenant_id,'SUPPLIER_ADVANCES',v_id) ON CONFLICT(tenant_id,mapping_key) DO NOTHING;
  v_id := public.ensure_system_account(p_tenant_id,'6200','Purchasing Cost Variance','EXPENSE','DEBIT','PURCHASE_COST_VARIANCE');
  INSERT INTO public.accounting_mappings(tenant_id,mapping_key,account_id) VALUES(p_tenant_id,'PURCHASE_COST_VARIANCE',v_id) ON CONFLICT(tenant_id,mapping_key) DO NOTHING;
  PERFORM set_config('app.tenant_id',COALESCE(v_previous_tenant,''),true);
END $seed$;

DO $backfill_accounts$
DECLARE r record;
BEGIN
  FOR r IN SELECT id FROM public.tenants LOOP
    PERFORM public.seed_purchasing_accounting_accounts(r.id);
  END LOOP;
END $backfill_accounts$;

CREATE OR REPLACE FUNCTION public.seed_purchasing_accounting_accounts_after_tenant()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $seed_tenant$
BEGIN
  PERFORM public.seed_purchasing_accounting_accounts(NEW.id);
  RETURN NEW;
END $seed_tenant$;
DROP TRIGGER IF EXISTS trg_seed_purchasing_accounting_accounts ON public.tenants;
CREATE TRIGGER trg_seed_purchasing_accounting_accounts
  AFTER INSERT ON public.tenants
  FOR EACH ROW EXECUTE FUNCTION public.seed_purchasing_accounting_accounts_after_tenant();

-- Enforce purchase approval limits in PostgreSQL too. An assigned Owner or
-- Administrator is the explicit override role; all other approver roles need a
-- currency-specific limit and must each be within that limit.
CREATE OR REPLACE FUNCTION public.enforce_purchase_order_approval_limit()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $approval$
DECLARE v_tenant uuid; v_user uuid; v_has_approver boolean; v_has_override boolean;
BEGIN
  IF NOT (OLD.status='SUBMITTED' AND NEW.status='OPEN' AND NEW.status IS DISTINCT FROM OLD.status) THEN RETURN NEW; END IF;
  v_tenant := NEW.tenant_id;
  v_user := NULLIF(current_setting('app.user_id',true),'')::uuid;
  IF v_user IS NULL THEN RAISE EXCEPTION 'PURCHASE_APPROVER_CONTEXT_REQUIRED' USING ERRCODE='23514'; END IF;
  SELECT EXISTS(
    SELECT 1 FROM public.tenant_memberships tm
    JOIN public.membership_roles mr ON mr.membership_id=tm.id
    JOIN public.roles r ON r.id=mr.role_id AND r.tenant_id=tm.tenant_id
    WHERE tm.tenant_id=v_tenant AND tm.user_id=v_user AND tm.status='ACTIVE'
      AND r.name IN ('Owner','Administrator','Admin')
  ) INTO v_has_override;
  IF v_has_override THEN RETURN NEW; END IF;
  SELECT EXISTS(
    SELECT 1 FROM public.tenant_memberships tm
    JOIN public.membership_roles mr ON mr.membership_id=tm.id
    JOIN public.roles r ON r.id=mr.role_id AND r.tenant_id=tm.tenant_id
    JOIN public.role_permissions rp ON rp.role_id=r.id
    JOIN public.permissions p ON p.id=rp.permission_id AND p.code='purchasing.approve'
    WHERE tm.tenant_id=v_tenant AND tm.user_id=v_user AND tm.status='ACTIVE'
  ) INTO v_has_approver;
  IF NOT v_has_approver THEN RAISE EXCEPTION 'PURCHASE_APPROVER_ROLE_REQUIRED' USING ERRCODE='23514'; END IF;
  IF EXISTS(
    SELECT 1 FROM public.tenant_memberships tm
    JOIN public.membership_roles mr ON mr.membership_id=tm.id
    JOIN public.roles r ON r.id=mr.role_id AND r.tenant_id=tm.tenant_id
    JOIN public.role_permissions rp ON rp.role_id=r.id
    JOIN public.permissions p ON p.id=rp.permission_id AND p.code='purchasing.approve'
    LEFT JOIN public.purchase_approval_limits lim
      ON lim.tenant_id=r.tenant_id AND lim.role_name=r.name AND lim.currency_code=upper(NEW.currency_code)
    WHERE tm.tenant_id=v_tenant AND tm.user_id=v_user AND tm.status='ACTIVE'
      AND r.name NOT IN ('Owner','Administrator','Admin')
      AND (lim.id IS NULL OR NEW.total > lim.max_approval_amount)
  ) THEN
    RAISE EXCEPTION 'PURCHASE_APPROVAL_LIMIT_EXCEEDED_OR_NOT_CONFIGURED' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $approval$;
DROP TRIGGER IF EXISTS trg_purchase_order_approval_limit ON public.purchase_orders;
CREATE TRIGGER trg_purchase_order_approval_limit
  BEFORE UPDATE OF status ON public.purchase_orders
  FOR EACH ROW EXECUTE FUNCTION public.enforce_purchase_order_approval_limit();

-- A posted goods receipt increases inventory at its effective cost (including
-- landed-cost allocations). Unbilled goods credit GRNI; pre-receipt bills offset
-- purchases clearing; landed freight remains in the separate clearing account.
CREATE OR REPLACE FUNCTION public.post_purchase_receipt_journal(p_receipt_id uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $receipt_journal$
DECLARE
  v_tenant uuid; v_po uuid; v_receipt_number text; v_entry_date date; v_user uuid; v_currency varchar(3);
  v_base numeric(20,4); v_inventory numeric(20,4); v_landed numeric(20,4); v_prebilled numeric(20,4); v_already_cleared numeric(20,4);
  v_purchase_clearing numeric(20,4); v_grni numeric(20,4); v_entry uuid; v_period uuid; v_inventory_account uuid;
  v_grni_account uuid; v_landed_account uuid; v_purchase_clearing_account uuid;
BEGIN
  SELECT r.tenant_id,r.purchase_order_id,r.receipt_number,r.received_at::date,COALESCE(r.posted_by,r.created_by),po.currency_code
    INTO v_tenant,v_po,v_receipt_number,v_entry_date,v_user,v_currency
    FROM public.purchase_receipts r JOIN public.purchase_orders po ON po.tenant_id=r.tenant_id AND po.id=r.purchase_order_id
   WHERE r.id=p_receipt_id AND r.status='POSTED' FOR UPDATE OF r;
  IF NOT FOUND THEN RAISE EXCEPTION 'Posted purchase receipt not found'; END IF;
  SELECT id INTO v_entry FROM public.journal_entries WHERE tenant_id=v_tenant AND source_type='PURCHASE_RECEIPT' AND source_id=p_receipt_id AND entry_role='RECEIPT_RECOGNITION';
  IF v_entry IS NOT NULL THEN RETURN v_entry; END IF;
  SELECT round(COALESCE(sum(rl.received_quantity*rl.base_unit_cost),0),4)
    INTO v_base FROM public.purchase_receipt_lines rl WHERE rl.tenant_id=v_tenant AND rl.receipt_id=p_receipt_id;
  SELECT round(COALESCE(sum(abs(tx.total_cost)),0),4)
    INTO v_inventory FROM public.inventory_transactions tx
   WHERE tx.tenant_id=v_tenant AND tx.transaction_type='PURCHASE_RECEIPT' AND tx.reference_type='purchase_receipt' AND tx.reference_id=p_receipt_id;
  IF v_inventory<=0 OR v_base<=0 THEN RAISE EXCEPTION 'Receipt has no positive posted stock cost'; END IF;
  v_landed := round(v_inventory-v_base,4);
  IF v_landed<0 THEN RAISE EXCEPTION 'Receipt inventory valuation is below its base goods cost'; END IF;
  SELECT round(COALESCE(sum(b.subtotal),0),4) INTO v_prebilled
    FROM public.supplier_bills b
   WHERE b.tenant_id=v_tenant AND b.purchase_order_id=v_po AND b.purchase_receipt_id IS NULL
     AND b.status='POSTED' AND b.match_status='OVERRIDDEN';
  SELECT round(COALESCE(sum(l.credit-l.debit),0),4) INTO v_already_cleared
    FROM public.purchase_receipts oldr
    JOIN public.journal_entries oldj ON oldj.tenant_id=oldr.tenant_id AND oldj.source_type='PURCHASE_RECEIPT' AND oldj.source_id=oldr.id AND oldj.entry_role='RECEIPT_RECOGNITION'
    JOIN public.journal_lines l ON l.tenant_id=oldj.tenant_id AND l.journal_entry_id=oldj.id
    JOIN public.accounting_mappings m ON m.tenant_id=l.tenant_id AND m.account_id=l.account_id AND m.mapping_key='PURCHASES_CLEARING'
   WHERE oldr.tenant_id=v_tenant AND oldr.purchase_order_id=v_po AND oldr.id<>p_receipt_id;
  v_purchase_clearing := least(v_base,greatest(v_prebilled-v_already_cleared,0));
  v_grni := round(v_base-v_purchase_clearing,4);
  v_inventory_account := public.accounting_mapping_account(v_tenant,'INVENTORY');
  v_grni_account := public.accounting_mapping_account(v_tenant,'GOODS_RECEIVED_NOT_INVOICED');
  v_landed_account := public.accounting_mapping_account(v_tenant,'LANDED_COST_CLEARING');
  v_purchase_clearing_account := public.accounting_mapping_account(v_tenant,'PURCHASES_CLEARING');
  IF v_inventory_account IS NULL OR (v_grni>0 AND v_grni_account IS NULL) OR (v_landed>0 AND v_landed_account IS NULL) OR (v_purchase_clearing>0 AND v_purchase_clearing_account IS NULL) THEN
    RAISE EXCEPTION 'Purchasing accounting mappings are not configured for tenant %',v_tenant;
  END IF;
  v_period := public.ensure_accounting_period(v_tenant,v_entry_date);
  INSERT INTO public.journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code)
  VALUES(v_tenant,v_period,v_entry_date,'PURCHASE_RECEIPT',p_receipt_id,'RECEIPT_RECOGNITION',v_receipt_number,'Inventory valuation on goods receipt',v_currency)
  RETURNING id INTO v_entry;
  INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
  VALUES(v_tenant,v_entry,1,v_inventory_account,'Inventory received at effective landed cost',v_inventory,0,v_currency);
  IF v_purchase_clearing>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
    VALUES(v_tenant,v_entry,2,v_purchase_clearing_account,'Clear approved supplier invoice posted before receipt',0,v_purchase_clearing,v_currency); END IF;
  IF v_grni>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
    VALUES(v_tenant,v_entry,3,v_grni_account,'Goods received not yet invoiced',0,v_grni,v_currency); END IF;
  IF v_landed>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
    VALUES(v_tenant,v_entry,4,v_landed_account,'Landed costs capitalised to inventory',0,v_landed,v_currency); END IF;
  PERFORM public.post_journal_entry(v_entry,v_user);
  RETURN v_entry;
END $receipt_journal$;

CREATE OR REPLACE FUNCTION public.post_supplier_ledger_journal(p_ledger_entry_id uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $supplier_journal$
DECLARE
  e public.supplier_ledger_entries%ROWTYPE; v_entry uuid; v_period uuid; v_date date; v_currency varchar(3); v_description text; v_reference text;
  v_subtotal numeric(20,4); v_tax numeric(20,4); v_other numeric(20,4); v_total numeric(20,4);
  v_allocated numeric(20,4); v_advance numeric(20,4); v_inventory_cost numeric(20,4); v_landed_cap numeric(20,4);
  v_receipt uuid; v_order uuid; v_payment uuid; v_bill uuid; v_original uuid; v_method text; v_map text; v_user uuid;
  a_ap uuid; a_grni uuid; a_landed uuid; a_purchase_clear uuid; a_input_tax uuid; a_expense uuid; a_inventory uuid; a_advance uuid; a_variance uuid; a_cash uuid;
BEGIN
  SELECT * INTO e FROM public.supplier_ledger_entries WHERE id=p_ledger_entry_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Supplier ledger entry not found'; END IF;
  SELECT id INTO v_entry FROM public.journal_entries WHERE tenant_id=e.tenant_id AND source_type='SUPPLIER_LEDGER' AND source_id=e.id AND entry_role=e.entry_type;
  IF v_entry IS NOT NULL THEN RETURN v_entry; END IF;
  v_user := COALESCE(e.actor_user_id,NULLIF(current_setting('app.user_id',true),'')::uuid);
  a_ap := public.accounting_mapping_account(e.tenant_id,'ACCOUNTS_PAYABLE');
  a_input_tax := public.accounting_mapping_account(e.tenant_id,'INPUT_TAX');
  a_expense := public.accounting_mapping_account(e.tenant_id,'OPERATING_EXPENSES');
  a_inventory := public.accounting_mapping_account(e.tenant_id,'INVENTORY');
  a_grni := public.accounting_mapping_account(e.tenant_id,'GOODS_RECEIVED_NOT_INVOICED');
  a_landed := public.accounting_mapping_account(e.tenant_id,'LANDED_COST_CLEARING');
  a_purchase_clear := public.accounting_mapping_account(e.tenant_id,'PURCHASES_CLEARING');
  a_advance := public.accounting_mapping_account(e.tenant_id,'SUPPLIER_ADVANCES');
  a_variance := public.accounting_mapping_account(e.tenant_id,'PURCHASE_COST_VARIANCE');
  IF a_ap IS NULL OR a_input_tax IS NULL OR a_expense IS NULL OR a_inventory IS NULL OR a_grni IS NULL OR a_landed IS NULL OR a_purchase_clear IS NULL OR a_advance IS NULL OR a_variance IS NULL THEN
    RAISE EXCEPTION 'Purchasing accounting mappings are not configured for tenant %',e.tenant_id;
  END IF;

  IF e.entry_type='RETURN_REVERSAL' THEN
    SELECT j.id INTO v_original
      FROM public.supplier_ledger_entries original
      JOIN public.journal_entries j ON j.tenant_id=original.tenant_id AND j.source_type='SUPPLIER_LEDGER' AND j.source_id=original.id AND j.entry_role='RETURN_CREDIT'
     WHERE original.tenant_id=e.tenant_id AND original.source_type='purchase_return' AND original.source_id=e.source_id AND original.entry_type='RETURN_CREDIT';
    IF v_original IS NULL THEN RAISE EXCEPTION 'Original supplier-return journal is missing; reversal cannot post'; END IF;
    PERFORM public.reverse_journal_entry(v_original,v_user,current_date);
    RETURN NULL;
  END IF;

  IF e.entry_type='BILL' THEN
    SELECT id, bill_date, bill_number, subtotal, tax_amount, other_charges, total, purchase_receipt_id, purchase_order_id, match_status
      INTO v_bill,v_date,v_reference,v_subtotal,v_tax,v_other,v_total,v_receipt,v_order,v_method
      FROM public.supplier_bills WHERE tenant_id=e.tenant_id AND id=e.source_id AND status='POSTED';
    IF NOT FOUND THEN RAISE EXCEPTION 'Posted supplier bill not found for supplier ledger entry %',e.id; END IF;
    v_period := public.ensure_accounting_period(e.tenant_id,v_date);
    v_entry := NULL;
    INSERT INTO public.journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code)
    VALUES(e.tenant_id,v_period,v_date,'SUPPLIER_LEDGER',e.id,'BILL',v_reference,'Supplier bill and payable recognition',e.currency_code) RETURNING id INTO v_entry;
    IF v_receipt IS NOT NULL THEN
      IF v_subtotal>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
        VALUES(e.tenant_id,v_entry,1,a_grni,'Clear goods received not invoiced',v_subtotal,0,e.currency_code); END IF;
      SELECT least(v_other,COALESCE(landed_cost_total,0)) INTO v_landed_cap FROM public.purchase_receipts WHERE tenant_id=e.tenant_id AND id=v_receipt;
      v_landed_cap := COALESCE(v_landed_cap,0);
      IF v_landed_cap>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
        VALUES(e.tenant_id,v_entry,2,a_landed,'Clear accrued landed costs',v_landed_cap,0,e.currency_code); END IF;
      IF v_other-v_landed_cap>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
        VALUES(e.tenant_id,v_entry,3,a_expense,'Supplier bill charges outside capitalised landed costs',v_other-v_landed_cap,0,e.currency_code); END IF;
    ELSIF v_order IS NOT NULL AND v_method='OVERRIDDEN' THEN
      IF v_subtotal>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
        VALUES(e.tenant_id,v_entry,1,a_purchase_clear,'Supplier invoice approved before physical receipt',v_subtotal,0,e.currency_code); END IF;
      IF v_other>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
        VALUES(e.tenant_id,v_entry,2,a_expense,'Supplier charges approved before receipt',v_other,0,e.currency_code); END IF;
    ELSE
      IF v_subtotal>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
        VALUES(e.tenant_id,v_entry,1,a_expense,'Supplier invoice not linked to a posted receipt',v_subtotal,0,e.currency_code); END IF;
      IF v_other>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
        VALUES(e.tenant_id,v_entry,2,a_expense,'Other supplier bill charges',v_other,0,e.currency_code); END IF;
    END IF;
    IF v_tax>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
      VALUES(e.tenant_id,v_entry,8,a_input_tax,'Recoverable input tax as recorded on supplier bill',v_tax,0,e.currency_code); END IF;
    INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
    VALUES(e.tenant_id,v_entry,20,a_ap,'Supplier payable',0,v_total,e.currency_code,e.supplier_party_id);
    PERFORM public.post_journal_entry(v_entry,v_user);
    RETURN v_entry;

  ELSIF e.entry_type='PAYMENT' THEN
    SELECT id,payment_date,payment_number,amount,payment_method INTO v_payment,v_date,v_reference,v_total,v_method
      FROM public.supplier_payments WHERE tenant_id=e.tenant_id AND id=e.source_id AND status='POSTED';
    IF NOT FOUND THEN RAISE EXCEPTION 'Posted supplier payment not found for supplier ledger entry %',e.id; END IF;
    SELECT round(COALESCE(sum(a.amount),0),4) INTO v_allocated
      FROM public.supplier_payment_allocations a
      JOIN public.supplier_bills b ON b.tenant_id=a.tenant_id AND b.id=a.bill_id
      WHERE a.tenant_id=e.tenant_id AND a.payment_id=v_payment AND b.status='POSTED';
    v_advance := round(v_total-v_allocated,4);
    IF v_advance<0 THEN RAISE EXCEPTION 'Posted supplier payment allocations exceed the payment total'; END IF;
    v_map := CASE v_method WHEN 'BANK_TRANSFER' THEN 'PAYMENT_CHANNEL.BANK' WHEN 'MOBILE_MONEY' THEN 'PAYMENT_CHANNEL.MOBILE_MONEY' WHEN 'CASH' THEN 'PAYMENT_CHANNEL.CASH' WHEN 'CHEQUE' THEN 'PAYMENT_CHANNEL.CHEQUE' WHEN 'CARD' THEN 'PAYMENT_CHANNEL.CARD' ELSE 'PAYMENT_CHANNEL.OTHER' END;
    v_cash := public.accounting_mapping_account(e.tenant_id,v_map);
    IF v_cash IS NULL THEN RAISE EXCEPTION 'Missing purchasing payment channel mapping %',v_map; END IF;
    v_period := public.ensure_accounting_period(e.tenant_id,v_date);
    INSERT INTO public.journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code)
    VALUES(e.tenant_id,v_period,v_date,'SUPPLIER_LEDGER',e.id,'PAYMENT',v_reference,'Supplier payment and allocation',e.currency_code) RETURNING id INTO v_entry;
    IF v_allocated>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
      VALUES(e.tenant_id,v_entry,1,a_ap,'Payment allocated to supplier bills',v_allocated,0,e.currency_code,e.supplier_party_id); END IF;
    IF v_advance>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
      VALUES(e.tenant_id,v_entry,2,a_advance,'Supplier advance not yet allocated to a bill',v_advance,0,e.currency_code,e.supplier_party_id); END IF;
    INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
    VALUES(e.tenant_id,v_entry,3,v_cash,'Payment recorded; no payment gateway is invoked',0,v_total,e.currency_code,e.supplier_party_id);
    PERFORM public.post_journal_entry(v_entry,v_user);
    RETURN v_entry;

  ELSIF e.entry_type='RETURN_CREDIT' THEN
    SELECT r.return_number, po.currency_code INTO v_reference,v_currency
      FROM public.purchase_returns r
      JOIN public.purchase_receipts rc ON rc.tenant_id=r.tenant_id AND rc.id=r.purchase_receipt_id
      JOIN public.purchase_orders po ON po.tenant_id=rc.tenant_id AND po.id=rc.purchase_order_id
     WHERE r.tenant_id=e.tenant_id AND r.id=e.source_id AND r.status IN ('POSTED','REVERSED');
    IF NOT FOUND THEN RAISE EXCEPTION 'Posted supplier return not found for supplier ledger entry %',e.id; END IF;
    SELECT round(COALESCE(sum(abs(tx.total_cost)),0),4) INTO v_inventory_cost
      FROM public.inventory_transactions tx
     WHERE tx.tenant_id=e.tenant_id AND tx.transaction_type='PURCHASE_RETURN' AND tx.reference_type='purchase_return' AND tx.reference_id=e.source_id;
    v_total := round(e.credit_amount,4);
    v_period := public.ensure_accounting_period(e.tenant_id,current_date);
    INSERT INTO public.journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code)
    VALUES(e.tenant_id,v_period,current_date,'SUPPLIER_LEDGER',e.id,'RETURN_CREDIT',v_reference,'Supplier return credit and inventory reversal',e.currency_code) RETURNING id INTO v_entry;
    IF v_total>0 THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
      VALUES(e.tenant_id,v_entry,1,a_ap,'Supplier credit reduces the payable',v_total,0,e.currency_code,e.supplier_party_id); END IF;
    IF v_inventory_cost>0 THEN
      IF v_inventory_cost>v_total THEN
        INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
        VALUES(e.tenant_id,v_entry,2,a_variance,'Cost difference: inventory removed exceeds supplier credit',v_inventory_cost-v_total,0,e.currency_code);
      END IF;
      INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
      VALUES(e.tenant_id,v_entry,3,a_inventory,'Inventory removed at moving-average cost',0,v_inventory_cost,e.currency_code);
    END IF;
    IF v_total>v_inventory_cost THEN INSERT INTO public.journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
      VALUES(e.tenant_id,v_entry,4,a_variance,'Supplier credit exceeds current inventory cost; cost recovery',0,v_total-v_inventory_cost,e.currency_code); END IF;
    PERFORM public.post_journal_entry(v_entry,v_user);
    RETURN v_entry;
  END IF;
  -- Other entry types (including a general adjustment) require their explicit
  -- business workflow and are deliberately not translated into guessed journals.
  RETURN NULL;
END $supplier_journal$;

CREATE OR REPLACE FUNCTION public.purchasing_supplier_ledger_after_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $supplier_trigger$
BEGIN
  PERFORM public.post_supplier_ledger_journal(NEW.id);
  RETURN NEW;
END $supplier_trigger$;

CREATE OR REPLACE FUNCTION public.purchasing_receipt_after_post()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $receipt_trigger$
BEGIN
  IF OLD.status IS DISTINCT FROM NEW.status AND NEW.status='POSTED' THEN
    PERFORM public.post_purchase_receipt_journal(NEW.id);
  END IF;
  RETURN NEW;
END $receipt_trigger$;

-- Backfill safely before enabling the insert/update triggers. Each function is
-- source-idempotent; reruns do not duplicate journal headers.
DO $backfill_journals$
DECLARE r record;
BEGIN
  FOR r IN SELECT id FROM public.purchase_receipts WHERE status='POSTED' ORDER BY posted_at,id LOOP
    PERFORM public.post_purchase_receipt_journal(r.id);
  END LOOP;
  FOR r IN SELECT id FROM public.supplier_ledger_entries WHERE entry_type IN ('BILL','PAYMENT','RETURN_CREDIT') ORDER BY occurred_at,id LOOP
    PERFORM public.post_supplier_ledger_journal(r.id);
  END LOOP;
END $backfill_journals$;

DROP TRIGGER IF EXISTS trg_purchasing_supplier_ledger_after_insert ON public.supplier_ledger_entries;
CREATE TRIGGER trg_purchasing_supplier_ledger_after_insert
  AFTER INSERT ON public.supplier_ledger_entries
  FOR EACH ROW EXECUTE FUNCTION public.purchasing_supplier_ledger_after_insert();
DROP TRIGGER IF EXISTS trg_purchasing_receipt_after_post ON public.purchase_receipts;
CREATE TRIGGER trg_purchasing_receipt_after_post
  AFTER UPDATE OF status ON public.purchase_receipts
  FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status AND NEW.status='POSTED')
  EXECUTE FUNCTION public.purchasing_receipt_after_post();

-- SECURITY DEFINER helpers are trigger-only internals. Revoke the default PUBLIC
-- EXECUTE grant so a runtime tenant cannot call the tenant-seeding helper with an
-- arbitrary tenant id or invoke purchasing journal functions out of workflow.
REVOKE ALL PRIVILEGES ON FUNCTION
  public.seed_purchasing_accounting_accounts(uuid),
  public.seed_purchasing_accounting_accounts_after_tenant(),
  public.enforce_purchase_order_approval_limit(),
  public.post_purchase_receipt_journal(uuid),
  public.post_supplier_ledger_journal(uuid),
  public.purchasing_supplier_ledger_after_insert(),
  public.purchasing_receipt_after_post()
FROM PUBLIC, lexa_app;

INSERT INTO public.schema_migrations(version) VALUES ('048_phase7_approval_limits_reversals_accounting') ON CONFLICT(version) DO NOTHING;
COMMIT;
