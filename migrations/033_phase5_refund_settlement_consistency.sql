-- LEXA Phase 5 — refund/return settlement consistency.
-- Reconstructed from the applied function definition observed on Neon
-- branch phase3-role-admin-probe-20261021, then corrected after review.
-- This is not a byte-recovered historical source migration. It is additive and
-- idempotent. Validate on an isolated Neon branch before any production replay.

BEGIN;

DO $$
BEGIN
  IF to_regclass('public.sales') IS NULL
     OR to_regclass('public.payment_allocations') IS NULL
     OR to_regclass('public.payments') IS NULL
     OR to_regclass('public.receivables') IS NULL
     OR to_regclass('public.sale_returns') IS NULL
     OR to_regclass('public.refund_records') IS NULL
     OR to_regclass('public.customer_credits') IS NULL
     OR to_regclass('public.customer_credit_allocations') IS NULL
     OR to_regclass('public.schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'Phase 5 refund settlement prerequisites are missing';
  END IF;
END $$;

-- amount_paid is net of completed recorded refunds. Refund capacity is computed
-- by application code from gross payment allocations less all recorded refunds.
-- Unallocated store credit remains a separate liability and therefore preserves
-- the originating sale's receivable; only credit allocated to that sale reduces it.
CREATE OR REPLACE FUNCTION public.refresh_sale_payment_totals(
  p_tenant_id uuid,
  p_sale_id uuid
)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_gross_collected numeric;
  v_recorded_refunds numeric;
  v_customer_credit_issued numeric;
  v_customer_credit_applied numeric;
  v_total numeric;
  v_return_adjustment numeric;
  v_net_collected numeric;
BEGIN
  SELECT total, return_adjustment_amount
    INTO v_total, v_return_adjustment
  FROM public.sales
  WHERE tenant_id = p_tenant_id AND id = p_sale_id
  FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;

  SELECT COALESCE(SUM(pa.amount), 0)
    INTO v_gross_collected
  FROM public.payment_allocations pa
  JOIN public.payments p
    ON p.id = pa.payment_id AND p.tenant_id = pa.tenant_id
  LEFT JOIN public.receivables r
    ON r.id = pa.receivable_id AND r.tenant_id = pa.tenant_id
  WHERE pa.tenant_id = p_tenant_id
    AND pa.status = 'RECORDED'
    AND p.status = 'RECORDED'
    AND (pa.sale_id = p_sale_id OR r.sale_id = p_sale_id);

  SELECT COALESCE(SUM(rr.amount), 0)
    INTO v_recorded_refunds
  FROM public.refund_records rr
  JOIN public.sale_returns sr
    ON sr.id = rr.return_id AND sr.tenant_id = rr.tenant_id
  WHERE rr.tenant_id = p_tenant_id
    AND sr.sale_id = p_sale_id
    AND sr.status = 'COMPLETED'
    AND rr.status = 'RECORDED';

  v_net_collected := GREATEST(v_gross_collected - v_recorded_refunds, 0);

  -- Issued store credit remains a separate liability until it is allocated.
  -- Preserve the source sale's receivable while that credit is unallocated, and
  -- reduce that receivable only by credit allocations specifically posted to it.
  SELECT COALESCE(SUM(cc.original_amount), 0)
    INTO v_customer_credit_issued
  FROM public.customer_credits cc
  JOIN public.sale_returns sr
    ON sr.id = cc.source_return_id AND sr.tenant_id = cc.tenant_id
  WHERE cc.tenant_id = p_tenant_id
    AND sr.sale_id = p_sale_id
    AND sr.status = 'COMPLETED'
    AND cc.status <> 'CANCELLED';

  SELECT COALESCE(SUM(cca.amount), 0)
    INTO v_customer_credit_applied
  FROM public.customer_credit_allocations cca
  JOIN public.receivables r
    ON r.id = cca.receivable_id AND r.tenant_id = cca.tenant_id
  WHERE cca.tenant_id = p_tenant_id
    AND r.sale_id = p_sale_id
    AND cca.status = 'RECORDED';

  UPDATE public.sales
  SET amount_paid = LEAST(v_total, v_net_collected),
      amount_due = GREATEST(
        v_total
        - LEAST(v_total, v_return_adjustment)
        - LEAST(v_total, v_net_collected)
        + v_customer_credit_issued
        - v_customer_credit_applied,
        0
      ),
      updated_at = now()
  WHERE tenant_id = p_tenant_id AND id = p_sale_id;
END;
$fn$;

-- Ensure changing a refund ledger row recalculates the originating sale. The
-- existing reconciliation trigger continues to update the cash settlement view.
CREATE OR REPLACE FUNCTION public.sync_sale_payment_totals_after_refund_change()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_old_sale_id uuid;
  v_new_sale_id uuid;
BEGIN
  IF TG_OP = 'INSERT' THEN
    SELECT sr.sale_id INTO v_new_sale_id
    FROM public.sale_returns sr
    WHERE sr.tenant_id = NEW.tenant_id AND sr.id = NEW.return_id;
    IF v_new_sale_id IS NOT NULL THEN
      PERFORM public.refresh_sale_payment_totals(NEW.tenant_id, v_new_sale_id);
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    SELECT sr.sale_id INTO v_old_sale_id
    FROM public.sale_returns sr
    WHERE sr.tenant_id = OLD.tenant_id AND sr.id = OLD.return_id;
    IF v_old_sale_id IS NOT NULL THEN
      PERFORM public.refresh_sale_payment_totals(OLD.tenant_id, v_old_sale_id);
    END IF;
    RETURN OLD;
  END IF;

  -- UPDATE: recompute the old sale after the updated row has its new values;
  -- if the refund was moved to a different sale, recompute that sale as well.
  SELECT sr.sale_id INTO v_old_sale_id
  FROM public.sale_returns sr
  WHERE sr.tenant_id = OLD.tenant_id AND sr.id = OLD.return_id;
  SELECT sr.sale_id INTO v_new_sale_id
  FROM public.sale_returns sr
  WHERE sr.tenant_id = NEW.tenant_id AND sr.id = NEW.return_id;
  IF v_old_sale_id IS NOT NULL THEN
    PERFORM public.refresh_sale_payment_totals(OLD.tenant_id, v_old_sale_id);
  END IF;
  IF v_new_sale_id IS NOT NULL
     AND (OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
          OR v_old_sale_id IS DISTINCT FROM v_new_sale_id) THEN
    PERFORM public.refresh_sale_payment_totals(NEW.tenant_id, v_new_sale_id);
  END IF;
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_sync_sale_payment_totals_after_refund ON public.refund_records;
CREATE TRIGGER trg_sync_sale_payment_totals_after_refund
AFTER INSERT OR UPDATE OR DELETE ON public.refund_records
FOR EACH ROW
EXECUTE FUNCTION public.sync_sale_payment_totals_after_refund_change();



-- Refresh analytics using sales.amount_due as the authoritative receivable
-- snapshot. Recomputing due from total - amount_paid - return_adjustment
-- double-counts or loses settlement semantics after cash refunds/store credit.
DO $$
BEGIN
  IF to_regclass('public.analytics_daily_business_metrics') IS NULL
     OR to_regclass('public.analytics_branch_daily_metrics') IS NULL
     OR to_regclass('public.analytics_refresh_runs') IS NULL THEN
    RAISE EXCEPTION 'Phase 5 analytics projection prerequisites are missing';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.refresh_analytics(p_tenant_id uuid,p_from date,p_to date)
RETURNS uuid LANGUAGE plpgsql AS $fn$
DECLARE v_run uuid;
BEGIN
  IF p_from>p_to THEN RAISE EXCEPTION 'Analytics start date cannot exceed end date'; END IF;
  INSERT INTO analytics_refresh_runs(tenant_id,from_date,to_date,status) VALUES(p_tenant_id,p_from,p_to,'RUNNING') RETURNING id INTO v_run;
  DELETE FROM analytics_daily_business_metrics WHERE tenant_id=p_tenant_id AND business_date BETWEEN p_from AND p_to;
  INSERT INTO analytics_daily_business_metrics(tenant_id,business_date,currency_code,sales_total,returns_total,net_sales,payments_collected,refunds_total,credit_created,expenses_total,net_cash_movement,sale_count,return_count,payment_count,expense_count)
  SELECT p_tenant_id,c.business_date,c.currency_code,COALESCE(s.sales_total,0),COALESCE(r.returns_total,0),COALESCE(s.sales_total,0)-COALESCE(r.returns_total,0),COALESCE(pay.payments_collected,0),COALESCE(ref.refunds_total,0),COALESCE(cr.credit_created,0),COALESCE(ex.expenses_total,0),COALESCE(pay.payments_collected,0)-COALESCE(ref.refunds_total,0)-COALESCE(ex.expenses_total,0),COALESCE(s.sale_count,0),COALESCE(r.return_count,0),COALESCE(pay.payment_count,0),COALESCE(ex.expense_count,0)
  FROM (SELECT DISTINCT x.business_date,x.currency_code FROM (
    SELECT COALESCE(completed_at,created_at)::date business_date,currency_code FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND COALESCE(completed_at,created_at)::date BETWEEN p_from AND p_to
    UNION SELECT business_date,currency_code FROM payments WHERE tenant_id=p_tenant_id AND status='RECORDED' AND business_date BETWEEN p_from AND p_to
    UNION SELECT business_date,currency_code FROM refund_records WHERE tenant_id=p_tenant_id AND status='RECORDED' AND business_date BETWEEN p_from AND p_to
    UNION SELECT expense_date,currency_code FROM expense_records WHERE tenant_id=p_tenant_id AND status='POSTED' AND expense_date BETWEEN p_from AND p_to
  ) x) c
  LEFT JOIN LATERAL (SELECT SUM(total) sales_total,COUNT(*) sale_count FROM sales WHERE tenant_id=p_tenant_id AND status='COMPLETED' AND currency_code=c.currency_code AND COALESCE(completed_at,created_at)::date=c.business_date) s ON true
  LEFT JOIN LATERAL (SELECT SUM(sr.total) returns_total,COUNT(*) return_count FROM sale_returns sr JOIN sales ss ON ss.tenant_id=sr.tenant_id AND ss.id=sr.sale_id WHERE sr.tenant_id=p_tenant_id AND sr.status='COMPLETED' AND ss.currency_code=c.currency_code AND COALESCE(sr.completed_at,sr.created_at)::date=c.business_date) r ON true
  LEFT JOIN LATERAL (SELECT SUM(amount) payments_collected,COUNT(*) payment_count FROM payments WHERE tenant_id=p_tenant_id AND status='RECORDED' AND currency_code=c.currency_code AND business_date=c.business_date) pay ON true
  LEFT JOIN LATERAL (SELECT SUM(amount) refunds_total FROM refund_records WHERE tenant_id=p_tenant_id AND status='RECORDED' AND currency_code=c.currency_code AND business_date=c.business_date) ref ON true
  LEFT JOIN LATERAL (SELECT SUM(GREATEST(sx.amount_due,0)) credit_created FROM sales sx WHERE sx.tenant_id=p_tenant_id AND sx.status='COMPLETED' AND sx.currency_code=c.currency_code AND COALESCE(sx.completed_at,sx.created_at)::date=c.business_date) cr ON true
  LEFT JOIN LATERAL (SELECT SUM(total) expenses_total,COUNT(*) expense_count FROM expense_records WHERE tenant_id=p_tenant_id AND status='POSTED' AND currency_code=c.currency_code AND expense_date=c.business_date) ex ON true;

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
VALUES ('033_phase5_refund_settlement_consistency')
ON CONFLICT (version) DO NOTHING;

COMMIT;
