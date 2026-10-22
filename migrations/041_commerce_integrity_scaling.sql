-- LEXA commerce integrity and scale baseline (forward migration; do not replay on a non-disposable database).
BEGIN;

ALTER TABLE public.sales ADD COLUMN IF NOT EXISTS business_date date;
UPDATE public.sales SET business_date=COALESCE(completed_at,created_at)::date WHERE business_date IS NULL;
ALTER TABLE public.sales ALTER COLUMN business_date SET DEFAULT CURRENT_DATE;
ALTER TABLE public.sales ALTER COLUMN business_date SET NOT NULL;

ALTER TABLE public.sale_returns ADD COLUMN IF NOT EXISTS business_date date;
UPDATE public.sale_returns SET business_date=COALESCE(completed_at,created_at)::date WHERE business_date IS NULL;
ALTER TABLE public.sale_returns ALTER COLUMN business_date SET DEFAULT CURRENT_DATE;
ALTER TABLE public.sale_returns ALTER COLUMN business_date SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sales_tenant_business_date_status ON public.sales(tenant_id,business_date,status,currency_code);
CREATE INDEX IF NOT EXISTS idx_returns_tenant_business_date_status ON public.sale_returns(tenant_id,business_date,status,sale_id);
CREATE INDEX IF NOT EXISTS idx_inventory_sale_reference_cogs ON public.inventory_transactions(tenant_id,reference_id,occurred_at) WHERE lower(reference_type)='sale' AND quantity_delta<0 AND transaction_type='SALE';
CREATE INDEX IF NOT EXISTS idx_fiscal_events_pending_schedule ON public.fiscalization_events(status,next_attempt_at,created_at) WHERE status IN ('PENDING','FAILED');

CREATE OR REPLACE FUNCTION post_sale_journal(p_sale_id uuid,p_user_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_period uuid; v_currency varchar; v_date date; v_total numeric; v_tax numeric; v_net numeric; v_party uuid; v_existing uuid; v_entry uuid;
BEGIN
  SELECT tenant_id,currency_code,business_date,total,tax_total,customer_party_id INTO v_tenant,v_currency,v_date,v_total,v_tax,v_party
  FROM sales WHERE id=p_sale_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Sale not found'; END IF;
  SELECT id INTO v_existing FROM journal_entries WHERE tenant_id=v_tenant AND source_type='SALE' AND source_id=p_sale_id AND entry_role='SALE_RECOGNITION';
  IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;
  v_period:=ensure_accounting_period(v_tenant,v_date); v_net:=GREATEST(v_total-v_tax,0);
  INSERT INTO journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code)
  VALUES(v_tenant,v_period,v_date,'SALE',p_sale_id,'SALE_RECOGNITION','SALE:'||p_sale_id::text,'Sale revenue recognition',v_currency) RETURNING id INTO v_entry;
  INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
  VALUES(v_tenant,v_entry,1,accounting_mapping_account(v_tenant,'ACCOUNTS_RECEIVABLE'),'Customer receivable',v_total,0,v_currency,v_party);
  IF v_net>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
    VALUES(v_tenant,v_entry,2,accounting_mapping_account(v_tenant,'SALES_REVENUE'),'Net sales revenue',0,v_net,v_currency); END IF;
  IF v_tax>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
    VALUES(v_tenant,v_entry,3,accounting_mapping_account(v_tenant,'OUTPUT_TAX'),'Output tax',0,v_tax,v_currency); END IF;
  PERFORM post_journal_entry(v_entry,p_user_id); RETURN v_entry;
END $fn$;

CREATE OR REPLACE FUNCTION post_payment_journal(p_payment_id uuid,p_user_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_currency varchar; v_date date; v_amount numeric; v_party uuid; v_account uuid; v_existing uuid; v_entry uuid; v_period uuid; v_allocated numeric;
BEGIN
  SELECT tenant_id,currency_code,business_date,amount,party_id INTO v_tenant,v_currency,v_date,v_amount,v_party
  FROM payments WHERE id=p_payment_id AND status='RECORDED' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Recorded payment not found'; END IF;
  SELECT id INTO v_existing FROM journal_entries WHERE tenant_id=v_tenant AND source_type='PAYMENT' AND source_id=p_payment_id AND entry_role='PAYMENT_RECEIPT';
  IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;
  v_account:=resolve_payment_account(p_payment_id);
  v_allocated:=COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE tenant_id=v_tenant AND payment_id=p_payment_id AND status='RECORDED'),0);
  IF v_allocated>v_amount THEN RAISE EXCEPTION 'Payment allocations exceed payment amount'; END IF;
  v_period:=ensure_accounting_period(v_tenant,v_date);
  INSERT INTO journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code)
  VALUES(v_tenant,v_period,v_date,'PAYMENT',p_payment_id,'PAYMENT_RECEIPT','PAYMENT:'||p_payment_id::text,'Payment received',v_currency) RETURNING id INTO v_entry;
  INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
  VALUES(v_tenant,v_entry,1,v_account,'Cash or settlement channel',v_amount,0,v_currency,v_party);
  IF v_allocated>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
    VALUES(v_tenant,v_entry,2,accounting_mapping_account(v_tenant,'ACCOUNTS_RECEIVABLE'),'Settlement of customer receivable',0,v_allocated,v_currency,v_party); END IF;
  IF v_amount-v_allocated>0 THEN INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code,party_id)
    VALUES(v_tenant,v_entry,3,accounting_mapping_account(v_tenant,'UNALLOCATED_RECEIPTS'),'Unallocated customer receipt',0,v_amount-v_allocated,v_currency,v_party); END IF;
  PERFORM post_journal_entry(v_entry,p_user_id); RETURN v_entry;
END $fn$;

CREATE OR REPLACE FUNCTION post_sale_cogs_journal(p_sale_id uuid,p_user_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_period uuid; v_currency varchar; v_date date; v_cogs numeric; v_existing uuid; v_entry uuid;
BEGIN
  SELECT tenant_id,currency_code,business_date INTO v_tenant,v_currency,v_date FROM sales WHERE id=p_sale_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Sale not found'; END IF;
  SELECT id INTO v_existing FROM journal_entries WHERE tenant_id=v_tenant AND source_type='SALE' AND source_id=p_sale_id AND entry_role='COGS';
  IF v_existing IS NOT NULL THEN RETURN v_existing; END IF;
  SELECT COALESCE(SUM(ABS(total_cost)),0) INTO v_cogs FROM inventory_transactions
    WHERE tenant_id=v_tenant AND lower(reference_type)='sale' AND reference_id=p_sale_id AND quantity_delta<0 AND transaction_type='SALE';
  IF v_cogs<=0 THEN RETURN NULL; END IF;
  v_period:=ensure_accounting_period(v_tenant,v_date);
  INSERT INTO journal_entries(tenant_id,period_id,entry_date,source_type,source_id,entry_role,reference,description,currency_code)
  VALUES(v_tenant,v_period,v_date,'SALE',p_sale_id,'COGS','SALE:'||p_sale_id::text,'Cost of goods sold',v_currency) RETURNING id INTO v_entry;
  INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,description,debit,credit,currency_code)
  VALUES(v_tenant,v_entry,1,accounting_mapping_account(v_tenant,'COGS'),'Cost of goods sold',v_cogs,0,v_currency),
        (v_tenant,v_entry,2,accounting_mapping_account(v_tenant,'INVENTORY'),'Inventory reduction',0,v_cogs,v_currency);
  PERFORM post_journal_entry(v_entry,p_user_id); RETURN v_entry;
END $fn$;

CREATE OR REPLACE FUNCTION create_fiscal_document_for_sale(p_sale_id uuid,p_document_type varchar DEFAULT 'INVOICE') RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_currency varchar; v_date date; v_enabled boolean; v_status text; v_mode text; v_id uuid;
BEGIN
  SELECT tenant_id,currency_code,business_date INTO v_tenant,v_currency,v_date FROM sales WHERE id=p_sale_id AND status='COMPLETED';
  IF NOT FOUND THEN RAISE EXCEPTION 'Completed sale not found'; END IF;
  SELECT enabled,registration_status,integration_mode INTO v_enabled,v_status,v_mode FROM efris_configurations WHERE tenant_id=v_tenant;
  IF NOT COALESCE(v_enabled,false) OR v_status<>'ACTIVE' OR v_mode<>'SYSTEM_TO_SYSTEM' THEN RAISE EXCEPTION 'A verified, active EFRIS system-to-system connection is required'; END IF;
  SELECT id INTO v_id FROM fiscal_documents WHERE tenant_id=v_tenant AND source_type='SALE' AND source_id=p_sale_id AND document_type=p_document_type;
  IF v_id IS NOT NULL THEN RETURN v_id; END IF;
  INSERT INTO fiscal_documents(tenant_id,source_type,source_id,document_type,currency_code,issue_date,status)
  VALUES(v_tenant,'SALE',p_sale_id,p_document_type,v_currency,v_date,'PENDING') RETURNING id INTO v_id;
  INSERT INTO fiscalization_events(tenant_id,fiscal_document_id,event_type,status) VALUES(v_tenant,v_id,'CREATE','PENDING');
  RETURN v_id;
END $fn$;

CREATE OR REPLACE FUNCTION create_fiscal_document_for_return(p_return_id uuid) RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_tenant uuid; v_sale uuid; v_currency varchar; v_date date; v_enabled boolean; v_status text; v_mode text; v_parent uuid; v_id uuid;
BEGIN
  SELECT sr.tenant_id,s.id,s.currency_code,sr.business_date
    INTO v_tenant,v_sale,v_currency,v_date
  FROM sale_returns sr JOIN sales s ON s.tenant_id=sr.tenant_id AND s.id=sr.sale_id
  WHERE sr.id=p_return_id AND sr.status='COMPLETED';
  IF NOT FOUND THEN RAISE EXCEPTION 'Completed sale return not found'; END IF;
  SELECT enabled,registration_status,integration_mode INTO v_enabled,v_status,v_mode
    FROM efris_configurations WHERE tenant_id=v_tenant;
  IF NOT COALESCE(v_enabled,false) OR COALESCE(v_status,'NOT_REGISTERED')<>'ACTIVE' OR COALESCE(v_mode,'MANUAL')<>'SYSTEM_TO_SYSTEM' THEN
    RETURN NULL;
  END IF;
  -- A credit note must reference an invoice accepted by URA; do not manufacture
  -- a standalone credit note or infer an FDN when the original invoice is missing.
  SELECT id INTO v_parent FROM fiscal_documents
    WHERE tenant_id=v_tenant AND source_type='SALE' AND source_id=v_sale
      AND document_type='INVOICE' AND status='ACCEPTED'
    ORDER BY accepted_at DESC NULLS LAST,created_at DESC LIMIT 1;
  IF v_parent IS NULL THEN RETURN NULL; END IF;
  SELECT id INTO v_id FROM fiscal_documents
    WHERE tenant_id=v_tenant AND source_type='SALE_RETURN' AND source_id=p_return_id AND document_type='CREDIT_NOTE';
  IF v_id IS NOT NULL THEN RETURN v_id; END IF;
  INSERT INTO fiscal_documents(tenant_id,source_type,source_id,document_type,currency_code,issue_date,status,metadata)
    VALUES(v_tenant,'SALE_RETURN',p_return_id,'CREDIT_NOTE',v_currency,v_date,'PENDING',jsonb_build_object('source_sale_id',v_sale,'source_fiscal_document_id',v_parent))
    RETURNING id INTO v_id;
  INSERT INTO fiscalization_events(tenant_id,fiscal_document_id,event_type,status)
    VALUES(v_tenant,v_id,'SUBMIT','PENDING');
  RETURN v_id;
END $fn$;

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
    SELECT business_date,currency_code FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND business_date BETWEEN p_from AND p_to
    UNION SELECT business_date,currency_code FROM payments WHERE tenant_id=p_tenant_id AND status='RECORDED' AND business_date BETWEEN p_from AND p_to
    UNION SELECT business_date,currency_code FROM refund_records WHERE tenant_id=p_tenant_id AND status='RECORDED' AND business_date BETWEEN p_from AND p_to
    UNION SELECT expense_date,currency_code FROM expense_records WHERE tenant_id=p_tenant_id AND status IN ('POSTED','REVERSED') AND expense_date BETWEEN p_from AND p_to
    UNION SELECT rj.entry_date,er.currency_code FROM expense_records er JOIN journal_entries rj ON rj.tenant_id=er.tenant_id AND rj.id=er.reversal_journal_entry_id WHERE er.tenant_id=p_tenant_id AND er.status='REVERSED' AND rj.status='POSTED' AND rj.entry_date BETWEEN p_from AND p_to
  ) x) c
  LEFT JOIN LATERAL (SELECT SUM(total) sales_total,COUNT(*) sale_count FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND currency_code=c.currency_code AND business_date=c.business_date) s ON true
  LEFT JOIN LATERAL (SELECT SUM(sr.total) returns_total,COUNT(*) return_count FROM sale_returns sr JOIN sales ss ON ss.tenant_id=sr.tenant_id AND ss.id=sr.sale_id WHERE sr.tenant_id=p_tenant_id AND sr.status='COMPLETED' AND ss.currency_code=c.currency_code AND sr.business_date=c.business_date) r ON true
  LEFT JOIN LATERAL (SELECT SUM(amount) payments_collected,COUNT(*) payment_count FROM payments WHERE tenant_id=p_tenant_id AND status='RECORDED' AND currency_code=c.currency_code AND business_date=c.business_date) pay ON true
  LEFT JOIN LATERAL (SELECT SUM(amount) refunds_total FROM refund_records WHERE tenant_id=p_tenant_id AND status='RECORDED' AND currency_code=c.currency_code AND business_date=c.business_date) ref ON true
  LEFT JOIN LATERAL (SELECT SUM(GREATEST(sx.amount_due,0)) credit_created FROM sales sx WHERE sx.tenant_id=p_tenant_id AND sx.status='COMPLETED' AND sx.currency_code=c.currency_code AND sx.business_date=c.business_date) cr ON true
  LEFT JOIN LATERAL (SELECT SUM(total) expenses_total,COUNT(*) expense_count FROM expense_records WHERE tenant_id=p_tenant_id AND status='POSTED' AND currency_code=c.currency_code AND expense_date=c.business_date) ex ON true
  LEFT JOIN LATERAL (SELECT SUM(total) expense_cash_outflow FROM expense_records WHERE tenant_id=p_tenant_id AND status IN ('POSTED','REVERSED') AND currency_code=c.currency_code AND expense_date=c.business_date) exout ON true
  LEFT JOIN LATERAL (SELECT SUM(er.total) expense_reversals_total FROM expense_records er JOIN journal_entries rj ON rj.tenant_id=er.tenant_id AND rj.id=er.reversal_journal_entry_id WHERE er.tenant_id=p_tenant_id AND er.status='REVERSED' AND rj.status='POSTED' AND er.currency_code=c.currency_code AND rj.entry_date=c.business_date) exrev ON true;

  DELETE FROM analytics_branch_daily_metrics WHERE tenant_id=p_tenant_id AND business_date BETWEEN p_from AND p_to;
  WITH bs AS (
    SELECT branch_id,business_date,currency_code,SUM(total) sales_total,COUNT(*) sale_count,SUM(GREATEST(amount_due,0)) credit_created
    FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND business_date BETWEEN p_from AND p_to GROUP BY branch_id,business_date,currency_code
  ), br AS (
    SELECT ss.branch_id,sr.business_date business_date,ss.currency_code,SUM(sr.total) returns_total
    FROM sale_returns sr JOIN sales ss ON ss.tenant_id=sr.tenant_id AND ss.id=sr.sale_id WHERE sr.tenant_id=p_tenant_id AND sr.status='COMPLETED' AND sr.business_date BETWEEN p_from AND p_to GROUP BY ss.branch_id,sr.business_date,ss.currency_code
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
    SELECT s.business_date business_date,tl.product_variant_id variant_id,tl.currency_code,SUM(tl.quantity) units_sold,SUM(tl.line_total) sales_amount,SUM(tl.discount_amount) discount_amount,SUM(tl.tax_amount) tax_amount
    FROM sales s JOIN business_transactions bt ON bt.tenant_id=s.tenant_id AND bt.id=s.transaction_id JOIN transaction_lines tl ON tl.tenant_id=bt.tenant_id AND tl.transaction_id=bt.id
    WHERE s.tenant_id=p_tenant_id AND s.status='COMPLETED' AND tl.product_variant_id IS NOT NULL AND s.business_date BETWEEN p_from AND p_to
    GROUP BY s.business_date,tl.product_variant_id,tl.currency_code
  ), rl AS (
    SELECT sr.business_date business_date,srl.variant_id,ss.currency_code,SUM(srl.quantity) returns_units,SUM(srl.line_total) returns_amount,SUM(srl.tax_amount) returns_tax_amount
    FROM sale_return_lines srl JOIN sale_returns sr ON sr.tenant_id=srl.tenant_id AND sr.id=srl.return_id JOIN sales ss ON ss.tenant_id=sr.tenant_id AND ss.id=sr.sale_id
    WHERE srl.tenant_id=p_tenant_id AND sr.status='COMPLETED' AND sr.business_date BETWEEN p_from AND p_to GROUP BY sr.business_date,srl.variant_id,ss.currency_code
  ), cg AS (
    SELECT s.business_date business_date,it.variant_id,s.currency_code,SUM(ABS(it.total_cost)) cogs
    FROM inventory_transactions it JOIN sales s ON s.tenant_id=it.tenant_id AND s.id=it.reference_id
    WHERE it.tenant_id=p_tenant_id AND lower(it.reference_type)='sale' AND it.quantity_delta<0 AND s.business_date BETWEEN p_from AND p_to GROUP BY s.business_date,it.variant_id,s.currency_code
  )
  INSERT INTO analytics_product_daily_metrics(tenant_id,business_date,variant_id,product_id,units_sold,sales_amount,discount_amount,tax_amount,returns_units,returns_amount,net_sales,cogs,gross_margin,currency_code)
  SELECT p_tenant_id,COALESCE(sl.business_date,rl.business_date,cg.business_date),v.id,v.product_id,COALESCE(sl.units_sold,0),COALESCE(sl.sales_amount,0),COALESCE(sl.discount_amount,0),COALESCE(sl.tax_amount,0),COALESCE(rl.returns_units,0),COALESCE(rl.returns_amount,0),(COALESCE(sl.sales_amount,0)-COALESCE(sl.tax_amount,0))-(COALESCE(rl.returns_amount,0)-COALESCE(rl.returns_tax_amount,0)),COALESCE(cg.cogs,0),(COALESCE(sl.sales_amount,0)-COALESCE(sl.tax_amount,0))-(COALESCE(rl.returns_amount,0)-COALESCE(rl.returns_tax_amount,0))-COALESCE(cg.cogs,0),COALESCE(sl.currency_code,rl.currency_code,cg.currency_code)
  FROM sl FULL OUTER JOIN rl ON rl.business_date=sl.business_date AND rl.variant_id=sl.variant_id AND rl.currency_code=sl.currency_code
  FULL OUTER JOIN cg ON cg.business_date=COALESCE(sl.business_date,rl.business_date) AND cg.variant_id=COALESCE(sl.variant_id,rl.variant_id) AND cg.currency_code=COALESCE(sl.currency_code,rl.currency_code)
  JOIN product_variants v ON v.tenant_id=p_tenant_id AND v.id=COALESCE(sl.variant_id,rl.variant_id,cg.variant_id);

  DELETE FROM analytics_customer_purchase_patterns WHERE tenant_id=p_tenant_id;
  WITH cs AS (
    SELECT customer_party_id,MIN(business_date) first_sale_date,MAX(business_date) last_sale_date,COUNT(*) sale_count,SUM(total) total_sales,SUM(amount_paid) total_paid,SUM(GREATEST(amount_due,0)) outstanding_balance,AVG(total) average_sale_value
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

-- Durable analytics refresh queue. Every relevant committed business event
-- enters this queue in the same transaction. Tenant/date rows coalesce bursts
-- of sales and are processed outside the checkout transaction.
CREATE TABLE IF NOT EXISTS public.analytics_refresh_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  business_date date NOT NULL,
  status varchar(20) NOT NULL DEFAULT 'PENDING'
    CHECK(status IN ('PENDING','PROCESSING','SUCCEEDED','FAILED','DEAD_LETTER')),
  generation bigint NOT NULL DEFAULT 1 CHECK(generation>=1),
  completed_generation bigint NOT NULL DEFAULT 0 CHECK(completed_generation>=0),
  attempt_count integer NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
  available_at timestamptz NOT NULL DEFAULT now(),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,business_date),
  CHECK(completed_generation<=generation)
);
CREATE INDEX IF NOT EXISTS idx_analytics_refresh_queue_pending
  ON public.analytics_refresh_queue(available_at,created_at)
  WHERE status IN ('PENDING','FAILED');
-- Internal cross-tenant queue is intentionally not directly accessible to the runtime role.
-- SECURITY DEFINER trigger/worker functions are the only runtime access path.
ALTER TABLE public.analytics_refresh_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analytics_refresh_queue FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS analytics_refresh_queue_worker_only ON public.analytics_refresh_queue;
CREATE POLICY analytics_refresh_queue_worker_only ON public.analytics_refresh_queue
  USING (NOT pg_has_role(current_user, 'lexa_app', 'MEMBER'))
  WITH CHECK (NOT pg_has_role(current_user, 'lexa_app', 'MEMBER'));
-- The SECURITY DEFINER trigger/worker execute as the non-runtime function owner;
-- the ordinary API role cannot read or write this cross-tenant internal queue.
REVOKE ALL ON public.analytics_refresh_queue FROM PUBLIC;
REVOKE ALL ON public.analytics_refresh_queue FROM lexa_app;

CREATE OR REPLACE FUNCTION public.enqueue_analytics_refresh_from_outbox()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp AS $fn$
DECLARE v_date date;
BEGIN
  IF NEW.event_type NOT IN ('SALE_COMPLETED','RETURN_CREATED','EXPENSE_POSTED','EXPENSE_REVERSED',
      'inventory.adjustment.posted.v1','inventory.stock_count.posted.v1',
      'inventory.transfer.completed.v1','inventory.transfer.received.v1') THEN
    RETURN NEW;
  END IF;
  IF NEW.event_type='SALE_COMPLETED' THEN
    SELECT s.business_date INTO v_date FROM public.sales s
      WHERE s.tenant_id=NEW.tenant_id AND s.id=NEW.aggregate_id AND s.status='COMPLETED';
  ELSIF NEW.event_type='RETURN_CREATED' THEN
    SELECT r.business_date INTO v_date FROM public.sale_returns r
      WHERE r.tenant_id=NEW.tenant_id AND r.id=NEW.aggregate_id AND r.status='COMPLETED';
  ELSIF NEW.event_type IN ('EXPENSE_POSTED','EXPENSE_REVERSED') THEN
    SELECT e.expense_date INTO v_date FROM public.expense_records e
      WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.aggregate_id;
  ELSE
    v_date:=public.lexa_business_date(COALESCE(NEW.occurred_at,now()),NEW.tenant_id);
  END IF;
  IF v_date IS NULL THEN
    RAISE EXCEPTION 'Cannot enqueue analytics refresh without a source business date';
  END IF;
  INSERT INTO public.analytics_refresh_queue(tenant_id,business_date,status,generation,completed_generation,attempt_count,available_at)
    VALUES(NEW.tenant_id,v_date,'PENDING',1,0,0,now()+interval '5 seconds')
    ON CONFLICT(tenant_id,business_date) DO UPDATE SET
      generation=public.analytics_refresh_queue.generation+1,
      status=CASE WHEN public.analytics_refresh_queue.status='PROCESSING' THEN 'PROCESSING' ELSE 'PENDING' END,
      attempt_count=CASE WHEN public.analytics_refresh_queue.status='PROCESSING' THEN public.analytics_refresh_queue.attempt_count ELSE 0 END,
      available_at=now()+interval '5 seconds',last_error=NULL,updated_at=now();
  RETURN NEW;
END $fn$;
DROP TRIGGER IF EXISTS trg_enqueue_analytics_refresh_from_outbox ON public.outbox_events;
CREATE TRIGGER trg_enqueue_analytics_refresh_from_outbox
  AFTER INSERT ON public.outbox_events
  FOR EACH ROW EXECUTE FUNCTION public.enqueue_analytics_refresh_from_outbox();

-- Narrow entry point for the API process' background poller. It cannot accept a
-- caller-supplied tenant ID; SECURITY DEFINER handles cross-tenant queue reads,
-- while source events and the refresh itself stay inside the same database.
CREATE OR REPLACE FUNCTION public.process_analytics_refresh_queue(p_limit integer DEFAULT 20)
RETURNS TABLE(processed_count integer,failed_count integer,dead_letter_count integer)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp AS $fn$
DECLARE q record; v_error text; v_processed integer:=0; v_failed integer:=0; v_dead integer:=0;
BEGIN
  IF p_limit<1 OR p_limit>100 THEN RAISE EXCEPTION 'Worker batch size must be between 1 and 100'; END IF;
  FOR q IN SELECT id,tenant_id,business_date,generation,attempt_count
    FROM public.analytics_refresh_queue
    WHERE status IN ('PENDING','FAILED') AND available_at<=now()
    ORDER BY available_at,created_at LIMIT p_limit FOR UPDATE SKIP LOCKED
  LOOP
    UPDATE public.analytics_refresh_queue SET status='PROCESSING',attempt_count=attempt_count+1,updated_at=now()
      WHERE id=q.id;
    BEGIN
      PERFORM public.refresh_analytics(q.tenant_id,q.business_date,q.business_date);
      UPDATE public.analytics_refresh_queue SET
        completed_generation=q.generation,
        status=CASE WHEN generation>q.generation THEN 'PENDING' ELSE 'SUCCEEDED' END,
        attempt_count=CASE WHEN generation>q.generation THEN attempt_count ELSE 0 END,
        available_at=CASE WHEN generation>q.generation THEN now() ELSE available_at END,
        last_error=NULL,updated_at=now()
        WHERE id=q.id;
      v_processed:=v_processed+1;
    EXCEPTION WHEN OTHERS THEN
      GET STACKED DIAGNOSTICS v_error=MESSAGE_TEXT;
      UPDATE public.analytics_refresh_queue SET
        status=CASE WHEN attempt_count>=8 THEN 'DEAD_LETTER' ELSE 'FAILED' END,
        available_at=CASE WHEN attempt_count>=8 THEN available_at
          ELSE now()+make_interval(secs=>LEAST(3600,5*(2^LEAST(attempt_count,9))::integer)) END,
        last_error=left(v_error,1000),updated_at=now()
        WHERE id=q.id;
      IF q.attempt_count+1>=8 THEN v_dead:=v_dead+1; ELSE v_failed:=v_failed+1; END IF;
    END;
  END LOOP;
  RETURN QUERY SELECT v_processed,v_failed,v_dead;
END $fn$;
REVOKE ALL ON FUNCTION public.process_analytics_refresh_queue(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.process_analytics_refresh_queue(integer) TO lexa_app;


INSERT INTO public.schema_migrations(version) VALUES ('041_commerce_integrity_scaling') ON CONFLICT (version) DO NOTHING;
COMMIT;
