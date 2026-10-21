-- LEXA Phase 5 — return/refund/store-credit accounting integration.
-- Additive release migration. Historical source SQL gaps remain documented in the manifest.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.sales') IS NULL
     OR to_regclass('public.sale_returns') IS NULL
     OR to_regclass('public.sale_return_lines') IS NULL
     OR to_regclass('public.refund_records') IS NULL
     OR to_regclass('public.customer_credits') IS NULL
     OR to_regclass('public.inventory_transactions') IS NULL
     OR to_regclass('public.journal_entries') IS NULL
     OR to_regclass('public.journal_lines') IS NULL
     OR to_regclass('public.accounting_mappings') IS NULL
     OR to_regclass('public.accounting_accounts') IS NULL
     OR to_regclass('public.efris_configurations') IS NULL
     OR to_regclass('public.fiscal_documents') IS NULL
     OR to_regclass('public.fiscalization_events') IS NULL
     OR to_regclass('public.schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'Phase 5 return-accounting prerequisites are missing';
  END IF;
END $$;

-- Use a dedicated liability account for store credit rather than conflating it
-- with unallocated incoming cash/receipts. Do not silently repurpose an existing
-- code 2210 if it has a different accounting classification.
DO $$
DECLARE v_tenant uuid; v_account uuid;
BEGIN
  IF EXISTS (
    SELECT 1 FROM public.accounting_accounts
    WHERE code='2210' AND (account_type<>'LIABILITY' OR normal_balance<>'CREDIT')
  ) THEN
    RAISE EXCEPTION 'Accounting account 2210 exists with an incompatible classification; reconcile the chart of accounts before applying Phase 5 migration 034';
  END IF;

  FOR v_tenant IN SELECT id FROM public.tenants LOOP
    v_account := public.ensure_system_account(
      v_tenant, '2210', 'Customer Store Credit Liability', 'LIABILITY', 'CREDIT', 'CUSTOMER_CREDITS'
    );
    INSERT INTO public.accounting_mappings(tenant_id,mapping_key,account_id)
    VALUES(v_tenant,'CUSTOMER_CREDITS',v_account)
    ON CONFLICT (tenant_id,mapping_key) DO UPDATE
      SET account_id=EXCLUDED.account_id, updated_at=now();
  END LOOP;
END $$;

CREATE OR REPLACE FUNCTION public.post_sale_return_journal(p_return_id uuid,p_user_id uuid)
RETURNS uuid
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_tenant uuid;
  v_sale_id uuid;
  v_currency varchar;
  v_party uuid;
  v_return_total numeric;
  v_return_tax numeric;
  v_net_return numeric;
  v_refund_total numeric;
  v_credit_total numeric;
  v_ar_reduction numeric;
  v_channel record;
  v_period uuid;
  v_entry uuid;
  v_existing uuid;
  v_line integer := 1;
  v_entry_date date;
BEGIN
  SELECT sr.tenant_id,sr.sale_id,s.currency_code,s.customer_party_id,sr.total,
         COALESCE(sr.completed_at::date,current_date)
    INTO v_tenant,v_sale_id,v_currency,v_party,v_return_total,v_entry_date
  FROM public.sale_returns sr
  JOIN public.sales s ON s.tenant_id=sr.tenant_id AND s.id=sr.sale_id
  WHERE sr.id=p_return_id AND sr.status='COMPLETED'
  FOR UPDATE OF sr;
  IF NOT FOUND THEN RAISE EXCEPTION 'Completed sale return not found'; END IF;

  SELECT id INTO v_existing
  FROM public.journal_entries
  WHERE tenant_id=v_tenant AND source_type='SALE_RETURN'
    AND source_id=p_return_id AND entry_role='RETURN_SETTLEMENT';
  IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;

  SELECT COALESCE(SUM(tax_amount),0)
    INTO v_return_tax
  FROM public.sale_return_lines
  WHERE tenant_id=v_tenant AND return_id=p_return_id;
  IF v_return_tax > v_return_total THEN
    RAISE EXCEPTION 'Return tax exceeds the return total; review the source sale-line calculations';
  END IF;
  v_net_return := GREATEST(v_return_total-v_return_tax,0);

  SELECT COALESCE(SUM(amount),0)
    INTO v_refund_total
  FROM public.refund_records
  WHERE tenant_id=v_tenant AND return_id=p_return_id AND status='RECORDED';

  SELECT COALESCE(SUM(original_amount),0)
    INTO v_credit_total
  FROM public.customer_credits
  WHERE tenant_id=v_tenant AND source_return_id=p_return_id AND status<>'CANCELLED';

  IF v_refund_total+v_credit_total > v_return_total THEN
    RAISE EXCEPTION 'Cash refund and customer credit exceed the return value';
  END IF;
  v_ar_reduction := GREATEST(v_return_total-v_refund_total-v_credit_total,0);

  v_period := public.ensure_accounting_period(v_tenant,v_entry_date);
  INSERT INTO public.journal_entries(
    tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,
    description,currency_code
  ) VALUES (
    v_tenant,v_period,v_entry_date,'SALE_RETURN',p_return_id,'RETURN_SETTLEMENT',
    'RETURN:'||p_return_id::text,'Sales return settlement',v_currency
  ) RETURNING id INTO v_entry;

  IF v_net_return > 0 THEN
    INSERT INTO public.journal_lines(
      tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id
    ) VALUES (
      v_tenant,v_entry,v_line,public.accounting_mapping_account(v_tenant,'SALES_RETURNS'),
      'Sales return net of tax',v_net_return,0,v_currency,v_party
    );
    v_line := v_line+1;
  END IF;

  IF v_return_tax > 0 THEN
    INSERT INTO public.journal_lines(
      tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id
    ) VALUES (
      v_tenant,v_entry,v_line,public.accounting_mapping_account(v_tenant,'OUTPUT_TAX'),
      'Reverse output tax on returned goods',v_return_tax,0,v_currency,v_party
    );
    v_line := v_line+1;
  END IF;

  -- Refunds credit the same cash/settlement channel used to send the money back.
  FOR v_channel IN
    SELECT rr.payment_channel_id,SUM(rr.amount) amount,
           pc.accounting_account_id,pc.channel_type
    FROM public.refund_records rr
    JOIN public.payment_channels pc
      ON pc.tenant_id=rr.tenant_id AND pc.id=rr.payment_channel_id
    WHERE rr.tenant_id=v_tenant AND rr.return_id=p_return_id AND rr.status='RECORDED'
    GROUP BY rr.payment_channel_id,pc.accounting_account_id,pc.channel_type
    ORDER BY rr.payment_channel_id
  LOOP
    INSERT INTO public.journal_lines(
      tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id
    ) VALUES (
      v_tenant,v_entry,v_line,
      COALESCE(v_channel.accounting_account_id,
               public.accounting_mapping_account(v_tenant,'PAYMENT_CHANNEL.'||v_channel.channel_type)),
      'Cash refund paid to customer',0,v_channel.amount,v_currency,v_party
    );
    v_line := v_line+1;
  END LOOP;

  IF v_credit_total > 0 THEN
    INSERT INTO public.journal_lines(
      tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id
    ) VALUES (
      v_tenant,v_entry,v_line,public.accounting_mapping_account(v_tenant,'CUSTOMER_CREDITS'),
      'Customer store credit liability issued',0,v_credit_total,v_currency,v_party
    );
    v_line := v_line+1;
  END IF;

  IF v_ar_reduction > 0 THEN
    INSERT INTO public.journal_lines(
      tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id
    ) VALUES (
      v_tenant,v_entry,v_line,public.accounting_mapping_account(v_tenant,'ACCOUNTS_RECEIVABLE'),
      'Reduce customer receivable for unsettled return value',0,v_ar_reduction,v_currency,v_party
    );
  END IF;

  PERFORM public.post_journal_entry(v_entry,p_user_id);
  RETURN v_entry;
END;
$fn$;

CREATE OR REPLACE FUNCTION public.post_sale_return_cogs_journal(p_return_id uuid,p_user_id uuid)
RETURNS uuid
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_tenant uuid;
  v_sale_id uuid;
  v_currency varchar;
  v_entry_date date;
  v_cogs numeric;
  v_period uuid;
  v_entry uuid;
  v_existing uuid;
BEGIN
  SELECT sr.tenant_id,sr.sale_id,s.currency_code,COALESCE(sr.completed_at::date,current_date)
    INTO v_tenant,v_sale_id,v_currency,v_entry_date
  FROM public.sale_returns sr
  JOIN public.sales s ON s.tenant_id=sr.tenant_id AND s.id=sr.sale_id
  WHERE sr.id=p_return_id AND sr.status='COMPLETED'
  FOR UPDATE OF sr;
  IF NOT FOUND THEN RAISE EXCEPTION 'Completed sale return not found'; END IF;

  SELECT id INTO v_existing
  FROM public.journal_entries
  WHERE tenant_id=v_tenant AND source_type='SALE_RETURN'
    AND source_id=p_return_id AND entry_role='RETURN_COGS';
  IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;

  SELECT COALESCE(SUM(total_cost),0)
    INTO v_cogs
  FROM public.inventory_transactions
  WHERE tenant_id=v_tenant AND reference_type='sale_return'
    AND reference_id=p_return_id AND transaction_type='RETURN' AND quantity_delta>0;
  IF v_cogs<=0 THEN RETURN NULL; END IF;

  v_period := public.ensure_accounting_period(v_tenant,v_entry_date);
  INSERT INTO public.journal_entries(
    tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,
    description,currency_code
  ) VALUES (
    v_tenant,v_period,v_entry_date,'SALE_RETURN',p_return_id,'RETURN_COGS',
    'RETURN:'||p_return_id::text,'Reverse cost of returned inventory',v_currency
  ) RETURNING id INTO v_entry;

  INSERT INTO public.journal_lines(
    tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code
  ) VALUES
    (v_tenant,v_entry,1,public.accounting_mapping_account(v_tenant,'INVENTORY'),'Returned inventory restored',v_cogs,0,v_currency),
    (v_tenant,v_entry,2,public.accounting_mapping_account(v_tenant,'COGS'),'Reverse cost of goods sold for return',0,v_cogs,v_currency);

  PERFORM public.post_journal_entry(v_entry,p_user_id);
  RETURN v_entry;
END;
$fn$;

CREATE OR REPLACE FUNCTION public.create_fiscal_document_for_return(p_return_id uuid)
RETURNS uuid
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_tenant uuid;
  v_currency varchar;
  v_issue_date date;
  v_enabled boolean;
  v_registration_status text;
  v_document uuid;
BEGIN
  SELECT sr.tenant_id,s.currency_code,COALESCE(sr.completed_at::date,current_date)
    INTO v_tenant,v_currency,v_issue_date
  FROM public.sale_returns sr
  JOIN public.sales s ON s.tenant_id=sr.tenant_id AND s.id=sr.sale_id
  WHERE sr.id=p_return_id AND sr.status='COMPLETED';
  IF NOT FOUND THEN RAISE EXCEPTION 'Completed sale return not found'; END IF;

  SELECT enabled,registration_status
    INTO v_enabled,v_registration_status
  FROM public.efris_configurations
  WHERE tenant_id=v_tenant;
  IF NOT COALESCE(v_enabled,false) OR COALESCE(v_registration_status,'NOT_REGISTERED')<>'ACTIVE' THEN
    RETURN NULL;
  END IF;

  SELECT id INTO v_document
  FROM public.fiscal_documents
  WHERE tenant_id=v_tenant AND source_type='SALE_RETURN'
    AND source_id=p_return_id AND document_type='CREDIT_NOTE';
  IF v_document IS NOT NULL THEN RETURN v_document; END IF;

  INSERT INTO public.fiscal_documents(tenant_id,source_type,source_id,document_type,currency_code,issue_date,status)
  VALUES(v_tenant,'SALE_RETURN',p_return_id,'CREDIT_NOTE',v_currency,v_issue_date,'PENDING')
  RETURNING id INTO v_document;
  INSERT INTO public.fiscalization_events(tenant_id,fiscal_document_id,event_type,status)
  VALUES(v_tenant,v_document,'SUBMIT','PENDING');
  RETURN v_document;
END;
$fn$;

INSERT INTO public.schema_migrations(version)
VALUES ('034_phase5_return_accounting_journals')
ON CONFLICT (version) DO NOTHING;
COMMIT;
