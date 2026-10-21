-- LEXA Phase 5 — bound no-refund returns to the customer receivable.
-- An unpaid return may credit accounts receivable only up to its open balance.
-- This is additive and protects direct callers in addition to the API validation.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.receivables') IS NULL
     OR to_regclass('public.sale_returns') IS NULL
     OR to_regclass('public.refund_records') IS NULL
     OR to_regclass('public.customer_credits') IS NULL
     OR to_regclass('public.journal_entries') IS NULL
     OR to_regclass('public.schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'Phase 5 no-refund receivable guard prerequisites are missing';
  END IF;
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
  v_open_receivable numeric;
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

  -- A no-refund/no-credit return must not credit AR past its open balance.
  -- The API checks this before inserts too; this database guard protects other callers.
  IF v_refund_total=0 AND v_credit_total=0 AND v_ar_reduction>0 THEN
    SELECT COALESCE(SUM(GREATEST(balance,0)),0)
      INTO v_open_receivable
    FROM public.receivables
    WHERE tenant_id=v_tenant AND sale_id=v_sale_id
      AND status IN ('OPEN','PARTIALLY_PAID');
    IF v_ar_reduction>v_open_receivable THEN
      RAISE EXCEPTION 'No-refund return exceeds open receivable; choose refund or customer-credit settlement';
    END IF;
  END IF;

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

INSERT INTO public.schema_migrations(version)
VALUES ('035_phase5_none_return_receivable_guard')
ON CONFLICT (version) DO NOTHING;

COMMIT;
