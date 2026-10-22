-- Phase 8 finance workflow completion.
-- Additive/forward-only migration. Apply only to disposable development or staging
-- until the single Phase 12 production gate is approved.
BEGIN;

ALTER TABLE public.expense_records
  ADD COLUMN IF NOT EXISTS reversal_journal_entry_id uuid;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='expense_records_reversal_journal_tenant_fk' AND conrelid='public.expense_records'::regclass
  ) THEN
    ALTER TABLE public.expense_records
      ADD CONSTRAINT expense_records_reversal_journal_tenant_fk
      FOREIGN KEY (tenant_id,reversal_journal_entry_id)
      REFERENCES public.journal_entries(tenant_id,id) ON DELETE RESTRICT;
  END IF;
END $$;

ALTER TABLE public.expense_records
  DROP CONSTRAINT IF EXISTS expense_records_status_check;
ALTER TABLE public.expense_records
  ADD CONSTRAINT expense_records_status_check
  CHECK (status IN ('DRAFT','POSTED','VOIDED','REVERSED'));

-- Use the expense's business date for its accounting period. A paid expense must
-- reference an active payment method in the same currency; unpaid supplier bills
-- belong in the supplier-bill workflow, not in this cash-expense form.
CREATE OR REPLACE FUNCTION public.post_expense_journal(p_expense_id uuid,p_user_id uuid)
RETURNS uuid
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_tenant uuid;
  v_currency varchar;
  v_subtotal numeric;
  v_tax numeric;
  v_total numeric;
  v_expense_account uuid;
  v_channel uuid;
  v_channel_type varchar;
  v_channel_account uuid;
  v_entry uuid;
  v_existing uuid;
  v_period uuid;
  v_party uuid;
  v_expense_date date;
BEGIN
  SELECT tenant_id,currency_code,subtotal,tax_amount,total,expense_account_id,
         payment_channel_id,supplier_party_id,expense_date
    INTO v_tenant,v_currency,v_subtotal,v_tax,v_total,v_expense_account,
         v_channel,v_party,v_expense_date
  FROM public.expense_records
  WHERE id=p_expense_id AND status='DRAFT'
  FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Draft expense not found'; END IF;

  IF v_channel IS NULL THEN
    RAISE EXCEPTION 'Select the payment method used for this expense';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.accounting_accounts
    WHERE tenant_id=v_tenant AND id=v_expense_account
      AND account_type='EXPENSE' AND status='ACTIVE' AND allow_posting=true
  ) THEN
    RAISE EXCEPTION 'Expense category is unavailable';
  END IF;
  SELECT channel_type,accounting_account_id
    INTO v_channel_type,v_channel_account
  FROM public.payment_channels
  WHERE tenant_id=v_tenant AND id=v_channel AND active=true AND currency_code=v_currency;
  IF NOT FOUND THEN RAISE EXCEPTION 'Payment method is inactive or uses another currency'; END IF;

  SELECT id INTO v_existing FROM public.journal_entries
  WHERE tenant_id=v_tenant AND source_type='EXPENSE'
    AND source_id=p_expense_id AND entry_role='EXPENSE';
  IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;

  v_period:=public.ensure_accounting_period(v_tenant,v_expense_date);
  INSERT INTO public.journal_entries(
    tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code
  )
  SELECT v_tenant,v_period,expense_date,'EXPENSE',p_expense_id,'EXPENSE',reference,description,v_currency
  FROM public.expense_records WHERE tenant_id=v_tenant AND id=p_expense_id
  RETURNING id INTO v_entry;

  INSERT INTO public.journal_lines(
    tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id
  ) VALUES(v_tenant,v_entry,1,v_expense_account,'Expense',v_subtotal,0,v_currency,v_party);

  IF v_tax>0 THEN
    INSERT INTO public.journal_lines(
      tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id
    ) VALUES(v_tenant,v_entry,2,public.accounting_mapping_account(v_tenant,'INPUT_TAX'),
             'Input tax',v_tax,0,v_currency,v_party);
  END IF;

  IF v_channel_account IS NULL THEN
    v_channel_account:=public.accounting_mapping_account(v_tenant,'PAYMENT_CHANNEL.'||v_channel_type);
  END IF;
  IF v_channel_account IS NULL THEN
    RAISE EXCEPTION 'Accounting setup for this payment method is incomplete';
  END IF;

  INSERT INTO public.journal_lines(
    tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id
  ) VALUES(v_tenant,v_entry,4,v_channel_account,'Expense paid',0,v_total,v_currency,v_party);

  PERFORM public.post_journal_entry(v_entry,p_user_id);
  UPDATE public.expense_records
  SET status='POSTED',journal_entry_id=v_entry,posted_by=p_user_id,updated_at=now()
  WHERE tenant_id=v_tenant AND id=p_expense_id AND status='DRAFT';
  RETURN v_entry;
END
$fn$;

CREATE INDEX IF NOT EXISTS idx_expense_records_reversal
  ON public.expense_records(tenant_id,reversal_journal_entry_id)
  WHERE reversal_journal_entry_id IS NOT NULL;

ALTER TABLE public.analytics_daily_business_metrics
  ADD COLUMN IF NOT EXISTS expense_reversals_total numeric(20,4) NOT NULL DEFAULT 0;

-- Report expense corrections separately from cash movement. Reversing an accounting
-- record does not prove that money was physically returned to the business. Only
-- still-posted expense records count as recorded outflows; the correction is shown
-- on its journal date as an accounting event. This is not bank/provider verification.
CREATE OR REPLACE FUNCTION refresh_analytics(p_tenant_id uuid,p_from date,p_to date)
RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_run uuid;
BEGIN
  IF p_from>p_to THEN RAISE EXCEPTION 'Analytics start date cannot exceed end date'; END IF;
  INSERT INTO analytics_refresh_runs(tenant_id,from_date,to_date,status) VALUES(p_tenant_id,p_from,p_to,'RUNNING') RETURNING id INTO v_run;
  DELETE FROM analytics_daily_business_metrics WHERE tenant_id=p_tenant_id AND business_date BETWEEN p_from AND p_to;
  INSERT INTO analytics_daily_business_metrics(tenant_id,business_date,currency_code,sales_total,returns_total,net_sales,payments_collected,refunds_total,credit_created,expenses_total,expense_reversals_total,net_cash_movement,sale_count,return_count,payment_count,expense_count)
  SELECT p_tenant_id,c.business_date,c.currency_code,COALESCE(s.sales_total,0),COALESCE(r.returns_total,0),COALESCE(s.sales_total,0)-COALESCE(r.returns_total,0),COALESCE(pay.payments_collected,0),COALESCE(ref.refunds_total,0),COALESCE(cr.credit_created,0),COALESCE(ex.expenses_total,0),COALESCE(exrev.expense_reversals_total,0),COALESCE(pay.payments_collected,0)-COALESCE(ref.refunds_total,0)-COALESCE(exout.expense_cash_outflow,0),COALESCE(s.sale_count,0),COALESCE(r.return_count,0),COALESCE(pay.payment_count,0),COALESCE(ex.expense_count,0)
  FROM (SELECT DISTINCT x.business_date,x.currency_code FROM (
    SELECT COALESCE(completed_at,created_at)::date business_date,currency_code FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND COALESCE(completed_at,created_at)::date BETWEEN p_from AND p_to
    UNION SELECT business_date,currency_code FROM payments WHERE tenant_id=p_tenant_id AND status='RECORDED' AND business_date BETWEEN p_from AND p_to
    UNION SELECT business_date,currency_code FROM refund_records WHERE tenant_id=p_tenant_id AND status='RECORDED' AND business_date BETWEEN p_from AND p_to
    UNION SELECT expense_date,currency_code FROM expense_records WHERE tenant_id=p_tenant_id AND status IN ('POSTED','REVERSED') AND expense_date BETWEEN p_from AND p_to
    UNION SELECT rj.entry_date,er.currency_code FROM expense_records er JOIN journal_entries rj ON rj.tenant_id=er.tenant_id AND rj.id=er.reversal_journal_entry_id WHERE er.tenant_id=p_tenant_id AND er.status='REVERSED' AND rj.status='POSTED' AND rj.entry_date BETWEEN p_from AND p_to
  ) x) c
  LEFT JOIN LATERAL (SELECT SUM(total) sales_total,COUNT(*) sale_count FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND currency_code=c.currency_code AND COALESCE(completed_at,created_at)::date=c.business_date) s ON true
  LEFT JOIN LATERAL (SELECT SUM(sr.total) returns_total,COUNT(*) return_count FROM sale_returns sr JOIN sales ss ON ss.tenant_id=sr.tenant_id AND ss.id=sr.sale_id WHERE sr.tenant_id=p_tenant_id AND sr.status='COMPLETED' AND ss.currency_code=c.currency_code AND COALESCE(sr.completed_at,sr.created_at)::date=c.business_date) r ON true
  LEFT JOIN LATERAL (SELECT SUM(amount) payments_collected,COUNT(*) payment_count FROM payments WHERE tenant_id=p_tenant_id AND status='RECORDED' AND currency_code=c.currency_code AND business_date=c.business_date) pay ON true
  LEFT JOIN LATERAL (SELECT SUM(amount) refunds_total FROM refund_records WHERE tenant_id=p_tenant_id AND status='RECORDED' AND currency_code=c.currency_code AND business_date=c.business_date) ref ON true
  LEFT JOIN LATERAL (SELECT SUM(GREATEST(sx.amount_due,0)) credit_created FROM sales sx WHERE sx.tenant_id=p_tenant_id AND sx.status='COMPLETED' AND sx.currency_code=c.currency_code AND COALESCE(sx.completed_at,sx.created_at)::date=c.business_date) cr ON true
  LEFT JOIN LATERAL (SELECT SUM(total) expenses_total,COUNT(*) expense_count FROM expense_records WHERE tenant_id=p_tenant_id AND status='POSTED' AND currency_code=c.currency_code AND expense_date=c.business_date) ex ON true
  LEFT JOIN LATERAL (SELECT SUM(total) expense_cash_outflow FROM expense_records WHERE tenant_id=p_tenant_id AND status IN ('POSTED','REVERSED') AND currency_code=c.currency_code AND expense_date=c.business_date) exout ON true
  LEFT JOIN LATERAL (SELECT SUM(er.total) expense_reversals_total FROM expense_records er JOIN journal_entries rj ON rj.tenant_id=er.tenant_id AND rj.id=er.reversal_journal_entry_id WHERE er.tenant_id=p_tenant_id AND er.status='REVERSED' AND rj.status='POSTED' AND er.currency_code=c.currency_code AND rj.entry_date=c.business_date) exrev ON true;

  DELETE FROM analytics_branch_daily_metrics WHERE tenant_id=p_tenant_id AND business_date BETWEEN p_from AND p_to;
  WITH bs AS (
    SELECT branch_id,COALESCE(completed_at,created_at)::date business_date,currency_code,SUM(total) sales_total,COUNT(*) sale_count,SUM(GREATEST(amount_due,0)) credit_created
    FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND COALESCE(completed_at,created_at)::date BETWEEN p_from AND p_to GROUP BY branch_id,COALESCE(completed_at,created_at)::date,currency_code
  ), br AS (
    SELECT ss.branch_id,COALESCE(sr.completed_at,sr.created_at)::date business_date,ss.currency_code,SUM(sr.total) returns_total
    FROM sale_returns sr JOIN sales ss ON ss.tenant_id=sr.tenant_id AND ss.id=sr.sale_id WHERE sr.tenant_id=p_tenant_id AND sr.status='COMPLETED' AND COALESCE(sr.completed_at,sr.created_at)::date BETWEEN p_from AND p_to GROUP BY ss.branch_id,COALESCE(sr.completed_at,sr.created_at)::date,ss.currency_code
  ), bp AS (
    SELECT bt.branch_id,p.business_date,p.currency_code,SUM(p.amount) payments_collected
    FROM payments p JOIN business_transactions bt ON bt.tenant_id=p.tenant_id AND bt.id=p.transaction_id WHERE p.tenant_id=p_tenant_id AND p.status='RECORDED' AND p.business_date BETWEEN p_from AND p_to GROUP BY bt.branch_id,p.business_date,p.currency_code
  )
  INSERT INTO analytics_branch_daily_metrics(tenant_id,branch_id,business_date,currency_code,sales_total,returns_total,net_sales,payments_collected,credit_created,sale_count)
  SELECT p_tenant_id,COALESCE(bs.branch_id,br.branch_id,bp.branch_id),COALESCE(bs.business_date,br.business_date,bp.business_date),COALESCE(bs.currency_code,br.currency_code,bp.currency_code),COALESCE(bs.sales_total,0),COALESCE(br.returns_total,0),COALESCE(bs.sales_total,0)-COALESCE(br.returns_total,0),COALESCE(bp.payments_collected,0),COALESCE(bs.credit_created,0),COALESCE(bs.sale_count,0)
  FROM bs FULL OUTER JOIN br ON br.branch_id=bs.branch_id AND br.business_date=bs.business_date AND br.currency_code=bs.currency_code
  FULL OUTER JOIN bp ON bp.branch_id=COALESCE(bs.branch_id,br.branch_id) AND bp.business_date=COALESCE(bs.business_date,br.business_date) AND bp.currency_code=COALESCE(bs.currency_code,br.currency_code);

  DELETE FROM analytics_product_daily_metrics WHERE tenant_id=p_tenant_id AND business_date BETWEEN p_from AND p_to;
  WITH sl AS (
    SELECT COALESCE(s.completed_at,s.created_at)::date business_date,tl.product_variant_id variant_id,tl.currency_code,SUM(tl.quantity) units_sold,SUM(tl.line_total) sales_amount,SUM(tl.discount_amount) discount_amount,SUM(tl.tax_amount) tax_amount
    FROM sales s JOIN business_transactions bt ON bt.tenant_id=s.tenant_id AND bt.id=s.transaction_id JOIN transaction_lines tl ON tl.tenant_id=bt.tenant_id AND tl.transaction_id=bt.id
    WHERE s.tenant_id=p_tenant_id AND s.status='COMPLETED' AND tl.product_variant_id IS NOT NULL AND COALESCE(s.completed_at,s.created_at)::date BETWEEN p_from AND p_to
    GROUP BY COALESCE(s.completed_at,s.created_at)::date,tl.product_variant_id,tl.currency_code
  ), rl AS (
    SELECT COALESCE(sr.completed_at,sr.created_at)::date business_date,srl.variant_id,ss.currency_code,SUM(srl.quantity) returns_units,SUM(srl.line_total) returns_amount
    FROM sale_return_lines srl JOIN sale_returns sr ON sr.tenant_id=srl.tenant_id AND sr.id=srl.return_id JOIN sales ss ON ss.tenant_id=sr.tenant_id AND ss.id=sr.sale_id
    WHERE srl.tenant_id=p_tenant_id AND sr.status='COMPLETED' AND COALESCE(sr.completed_at,sr.created_at)::date BETWEEN p_from AND p_to GROUP BY COALESCE(sr.completed_at,sr.created_at)::date,srl.variant_id,ss.currency_code
  ), cg AS (
    SELECT COALESCE(s.completed_at,s.created_at)::date business_date,it.variant_id,s.currency_code,SUM(ABS(it.total_cost)) cogs
    FROM inventory_transactions it JOIN sales s ON s.tenant_id=it.tenant_id AND s.id=it.reference_id
    WHERE it.tenant_id=p_tenant_id AND it.reference_type='SALE' AND it.quantity_delta<0 AND COALESCE(s.completed_at,s.created_at)::date BETWEEN p_from AND p_to GROUP BY COALESCE(s.completed_at,s.created_at)::date,it.variant_id,s.currency_code
  )
  INSERT INTO analytics_product_daily_metrics(tenant_id,business_date,variant_id,product_id,units_sold,sales_amount,discount_amount,tax_amount,returns_units,returns_amount,net_sales,cogs,gross_margin,currency_code)
  SELECT p_tenant_id,COALESCE(sl.business_date,rl.business_date,cg.business_date),v.id,v.product_id,COALESCE(sl.units_sold,0),COALESCE(sl.sales_amount,0),COALESCE(sl.discount_amount,0),COALESCE(sl.tax_amount,0),COALESCE(rl.returns_units,0),COALESCE(rl.returns_amount,0),COALESCE(sl.sales_amount,0)-COALESCE(rl.returns_amount,0),COALESCE(cg.cogs,0),COALESCE(sl.sales_amount,0)-COALESCE(rl.returns_amount,0)-COALESCE(cg.cogs,0),COALESCE(sl.currency_code,rl.currency_code,cg.currency_code)
  FROM sl FULL OUTER JOIN rl ON rl.business_date=sl.business_date AND rl.variant_id=sl.variant_id AND rl.currency_code=sl.currency_code
  FULL OUTER JOIN cg ON cg.business_date=COALESCE(sl.business_date,rl.business_date) AND cg.variant_id=COALESCE(sl.variant_id,rl.variant_id) AND cg.currency_code=COALESCE(sl.currency_code,rl.currency_code)
  JOIN product_variants v ON v.tenant_id=p_tenant_id AND v.id=COALESCE(sl.variant_id,rl.variant_id,cg.variant_id);

  DELETE FROM analytics_customer_purchase_patterns WHERE tenant_id=p_tenant_id;
  WITH cs AS (
    SELECT customer_party_id,MIN(COALESCE(completed_at,created_at)::date) first_sale_date,MAX(COALESCE(completed_at,created_at)::date) last_sale_date,COUNT(*) sale_count,SUM(total) total_sales,SUM(amount_paid) total_paid,SUM(GREATEST(amount_due,0)) outstanding_balance,AVG(total) average_sale_value
    FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND customer_party_id IS NOT NULL GROUP BY customer_party_id
  ), cr AS (
    SELECT ss.customer_party_id,SUM(sr.total) total_returns FROM sale_returns sr JOIN sales ss ON ss.tenant_id=sr.tenant_id AND ss.id=sr.sale_id WHERE sr.tenant_id=p_tenant_id AND sr.status='COMPLETED' AND ss.customer_party_id IS NOT NULL GROUP BY ss.customer_party_id
  )
  INSERT INTO analytics_customer_purchase_patterns(tenant_id,customer_party_id,first_sale_date,last_sale_date,sale_count,total_sales,total_returns,net_sales,total_paid,outstanding_balance,average_sale_value)
  SELECT p_tenant_id,cs.customer_party_id,cs.first_sale_date,cs.last_sale_date,cs.sale_count,cs.total_sales,COALESCE(cr.total_returns,0),cs.total_sales-COALESCE(cr.total_returns,0),cs.total_paid,cs.outstanding_balance,cs.average_sale_value FROM cs LEFT JOIN cr ON cr.customer_party_id=cs.customer_party_id;

  DELETE FROM analytics_inventory_health_metrics WHERE tenant_id=p_tenant_id AND snapshot_date=current_date;
  INSERT INTO analytics_inventory_health_metrics(tenant_id,snapshot_date,location_id,variant_id,on_hand,reserved,available,stock_value,units_sold_30d,daily_velocity,days_cover)
  SELECT ib.tenant_id,current_date,ib.location_id,ib.variant_id,ib.on_hand,ib.reserved,GREATEST(ib.on_hand-ib.reserved,0),ib.stock_value,
         COALESCE(-SUM(CASE WHEN it.quantity_delta<0 THEN it.quantity_delta ELSE 0 END)-SUM(CASE WHEN it.transaction_type='RETURN' AND it.quantity_delta>0 THEN it.quantity_delta ELSE 0 END),0),
         COALESCE((-SUM(CASE WHEN it.quantity_delta<0 THEN it.quantity_delta ELSE 0 END)-SUM(CASE WHEN it.transaction_type='RETURN' AND it.quantity_delta>0 THEN it.quantity_delta ELSE 0 END))/30.0,0),
         CASE WHEN COALESCE(-SUM(CASE WHEN it.quantity_delta<0 THEN it.quantity_delta ELSE 0 END)-SUM(CASE WHEN it.transaction_type='RETURN' AND it.quantity_delta>0 THEN it.quantity_delta ELSE 0 END),0)>0 THEN GREATEST(ib.on_hand-ib.reserved,0)/((-SUM(CASE WHEN it.quantity_delta<0 THEN it.quantity_delta ELSE 0 END)-SUM(CASE WHEN it.transaction_type='RETURN' AND it.quantity_delta>0 THEN it.quantity_delta ELSE 0 END))/30.0) ELSE NULL END
  FROM inventory_balances ib LEFT JOIN inventory_transactions it ON it.tenant_id=ib.tenant_id AND it.location_id=ib.location_id AND it.variant_id=ib.variant_id AND it.occurred_at>=now()-interval '30 days'
  WHERE ib.tenant_id=p_tenant_id GROUP BY ib.tenant_id,ib.location_id,ib.variant_id,ib.on_hand,ib.reserved,ib.stock_value;

  UPDATE analytics_refresh_runs SET status='SUCCEEDED',completed_at=now() WHERE id=v_run; RETURN v_run;
EXCEPTION WHEN OTHERS THEN UPDATE analytics_refresh_runs SET status='FAILED',completed_at=now(),error_message=SQLERRM WHERE id=v_run; RAISE;
END $fn$;

INSERT INTO public.schema_migrations(version)
VALUES ('040_phase8_finance_workflows')
ON CONFLICT (version) DO NOTHING;
COMMIT;
