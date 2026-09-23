-- Phase 5: deterministic analytics / business intelligence foundation
CREATE TABLE IF NOT EXISTS analytics_refresh_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  from_date date NOT NULL,
  to_date date NOT NULL,
  status varchar(20) NOT NULL CHECK(status IN ('RUNNING','SUCCEEDED','FAILED')),
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz NULL,
  error_message text NULL,
  UNIQUE(tenant_id,id),
  CHECK(from_date<=to_date)
);

CREATE TABLE IF NOT EXISTS analytics_daily_business_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  business_date date NOT NULL, currency_code varchar(3) NOT NULL,
  sales_total numeric(20,4) NOT NULL DEFAULT 0, returns_total numeric(20,4) NOT NULL DEFAULT 0,
  net_sales numeric(20,4) NOT NULL DEFAULT 0, payments_collected numeric(20,4) NOT NULL DEFAULT 0,
  refunds_total numeric(20,4) NOT NULL DEFAULT 0, credit_created numeric(20,4) NOT NULL DEFAULT 0,
  expenses_total numeric(20,4) NOT NULL DEFAULT 0, net_cash_movement numeric(20,4) NOT NULL DEFAULT 0,
  sale_count integer NOT NULL DEFAULT 0, return_count integer NOT NULL DEFAULT 0,
  payment_count integer NOT NULL DEFAULT 0, expense_count integer NOT NULL DEFAULT 0,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,business_date,currency_code), UNIQUE(tenant_id,id)
);

CREATE TABLE IF NOT EXISTS analytics_branch_daily_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  branch_id uuid NOT NULL, business_date date NOT NULL, currency_code varchar(3) NOT NULL,
  sales_total numeric(20,4) NOT NULL DEFAULT 0, returns_total numeric(20,4) NOT NULL DEFAULT 0,
  net_sales numeric(20,4) NOT NULL DEFAULT 0, payments_collected numeric(20,4) NOT NULL DEFAULT 0,
  credit_created numeric(20,4) NOT NULL DEFAULT 0, sale_count integer NOT NULL DEFAULT 0,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,branch_id,business_date,currency_code), UNIQUE(tenant_id,id),
  CONSTRAINT fk_analytics_branch_tenant FOREIGN KEY (tenant_id,branch_id) REFERENCES branches(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS analytics_product_daily_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  business_date date NOT NULL, variant_id uuid NOT NULL, product_id uuid NOT NULL,
  units_sold numeric(20,4) NOT NULL DEFAULT 0, sales_amount numeric(20,4) NOT NULL DEFAULT 0,
  discount_amount numeric(20,4) NOT NULL DEFAULT 0, tax_amount numeric(20,4) NOT NULL DEFAULT 0,
  returns_units numeric(20,4) NOT NULL DEFAULT 0, returns_amount numeric(20,4) NOT NULL DEFAULT 0,
  net_sales numeric(20,4) NOT NULL DEFAULT 0, cogs numeric(20,4) NOT NULL DEFAULT 0,
  gross_margin numeric(20,4) NOT NULL DEFAULT 0, currency_code varchar(3) NOT NULL,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,business_date,variant_id,currency_code), UNIQUE(tenant_id,id),
  CONSTRAINT fk_analytics_product_variant_tenant FOREIGN KEY (tenant_id,variant_id) REFERENCES product_variants(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_analytics_product_product_tenant FOREIGN KEY (tenant_id,product_id) REFERENCES products(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS analytics_customer_purchase_patterns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  customer_party_id uuid NOT NULL, first_sale_date date NULL, last_sale_date date NULL,
  sale_count integer NOT NULL DEFAULT 0, total_sales numeric(20,4) NOT NULL DEFAULT 0,
  total_returns numeric(20,4) NOT NULL DEFAULT 0, net_sales numeric(20,4) NOT NULL DEFAULT 0,
  total_paid numeric(20,4) NOT NULL DEFAULT 0, outstanding_balance numeric(20,4) NOT NULL DEFAULT 0,
  average_sale_value numeric(20,4) NOT NULL DEFAULT 0, refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,customer_party_id), UNIQUE(tenant_id,id),
  CONSTRAINT fk_analytics_customer_tenant FOREIGN KEY (tenant_id,customer_party_id) REFERENCES parties(tenant_id,id) DEFERRABLE
);

CREATE TABLE IF NOT EXISTS analytics_inventory_health_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  snapshot_date date NOT NULL, location_id uuid NOT NULL, variant_id uuid NOT NULL,
  on_hand numeric(20,4) NOT NULL DEFAULT 0, reserved numeric(20,4) NOT NULL DEFAULT 0,
  available numeric(20,4) NOT NULL DEFAULT 0, stock_value numeric(20,4) NOT NULL DEFAULT 0,
  units_sold_30d numeric(20,4) NOT NULL DEFAULT 0, daily_velocity numeric(20,6) NOT NULL DEFAULT 0,
  days_cover numeric(20,6) NULL, refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,snapshot_date,location_id,variant_id), UNIQUE(tenant_id,id),
  CONSTRAINT fk_analytics_inventory_location_tenant FOREIGN KEY (tenant_id,location_id) REFERENCES locations(tenant_id,id) DEFERRABLE,
  CONSTRAINT fk_analytics_inventory_variant_tenant FOREIGN KEY (tenant_id,variant_id) REFERENCES product_variants(tenant_id,id) DEFERRABLE
);

CREATE INDEX IF NOT EXISTS idx_analytics_daily_business_date ON analytics_daily_business_metrics(tenant_id,business_date);
CREATE INDEX IF NOT EXISTS idx_analytics_branch_date ON analytics_branch_daily_metrics(tenant_id,branch_id,business_date);
CREATE INDEX IF NOT EXISTS idx_analytics_product_date ON analytics_product_daily_metrics(tenant_id,variant_id,business_date);
CREATE INDEX IF NOT EXISTS idx_analytics_customer_last_sale ON analytics_customer_purchase_patterns(tenant_id,last_sale_date);
CREATE INDEX IF NOT EXISTS idx_analytics_inventory_health ON analytics_inventory_health_metrics(tenant_id,snapshot_date,location_id);

CREATE OR REPLACE FUNCTION refresh_analytics(p_tenant_id uuid,p_from date,p_to date)
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
  LEFT JOIN LATERAL (SELECT SUM(GREATEST(sx.total-sx.amount_paid-sx.return_adjustment_amount,0)) credit_created FROM sales sx WHERE sx.tenant_id=p_tenant_id AND sx.status='COMPLETED' AND sx.currency_code=c.currency_code AND COALESCE(sx.completed_at,sx.created_at)::date=c.business_date) cr ON true
  LEFT JOIN LATERAL (SELECT SUM(total) expenses_total,COUNT(*) expense_count FROM expense_records WHERE tenant_id=p_tenant_id AND status='POSTED' AND currency_code=c.currency_code AND expense_date=c.business_date) ex ON true;

  DELETE FROM analytics_branch_daily_metrics WHERE tenant_id=p_tenant_id AND business_date BETWEEN p_from AND p_to;
  WITH bs AS (
    SELECT branch_id,COALESCE(completed_at,created_at)::date business_date,currency_code,SUM(total) sales_total,COUNT(*) sale_count,SUM(GREATEST(total-amount_paid-return_adjustment_amount,0)) credit_created
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
END $fn$;\n\nALTER TABLE analytics_refresh_runs ENABLE ROW LEVEL SECURITY;\nALTER TABLE analytics_refresh_runs FORCE ROW LEVEL SECURITY;\nDROP POLICY IF EXISTS analytics_refresh_runs_tenant ON analytics_refresh_runs;\nCREATE POLICY analytics_refresh_runs_tenant ON analytics_refresh_runs USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));\nALTER TABLE analytics_daily_business_metrics ENABLE ROW LEVEL SECURITY;\nALTER TABLE analytics_daily_business_metrics FORCE ROW LEVEL SECURITY;\nDROP POLICY IF EXISTS analytics_daily_business_metrics_tenant ON analytics_daily_business_metrics;\nCREATE POLICY analytics_daily_business_metrics_tenant ON analytics_daily_business_metrics USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));\nALTER TABLE analytics_branch_daily_metrics ENABLE ROW LEVEL SECURITY;\nALTER TABLE analytics_branch_daily_metrics FORCE ROW LEVEL SECURITY;\nDROP POLICY IF EXISTS analytics_branch_daily_metrics_tenant ON analytics_branch_daily_metrics;\nCREATE POLICY analytics_branch_daily_metrics_tenant ON analytics_branch_daily_metrics USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));\nALTER TABLE analytics_product_daily_metrics ENABLE ROW LEVEL SECURITY;\nALTER TABLE analytics_product_daily_metrics FORCE ROW LEVEL SECURITY;\nDROP POLICY IF EXISTS analytics_product_daily_metrics_tenant ON analytics_product_daily_metrics;\nCREATE POLICY analytics_product_daily_metrics_tenant ON analytics_product_daily_metrics USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));\nALTER TABLE analytics_customer_purchase_patterns ENABLE ROW LEVEL SECURITY;\nALTER TABLE analytics_customer_purchase_patterns FORCE ROW LEVEL SECURITY;\nDROP POLICY IF EXISTS analytics_customer_purchase_patterns_tenant ON analytics_customer_purchase_patterns;\nCREATE POLICY analytics_customer_purchase_patterns_tenant ON analytics_customer_purchase_patterns USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));\nALTER TABLE analytics_inventory_health_metrics ENABLE ROW LEVEL SECURITY;\nALTER TABLE analytics_inventory_health_metrics FORCE ROW LEVEL SECURITY;\nDROP POLICY IF EXISTS analytics_inventory_health_metrics_tenant ON analytics_inventory_health_metrics;\nCREATE POLICY analytics_inventory_health_metrics_tenant ON analytics_inventory_health_metrics USING (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid)) WITH CHECK (tenant_id=(NULLIF(current_setting('app.tenant_id',true),'')::uuid));\nINSERT INTO permissions(code,description) VALUES ('analytics.read','View business intelligence and analytics'),('analytics.refresh','Refresh deterministic analytics projections') ON CONFLICT(code) DO NOTHING;\nINSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code='analytics.read' WHERE r.name IN ('Owner','Admin','Manager','Accountant','Auditor') ON CONFLICT DO NOTHING;\nINSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code='analytics.refresh' WHERE r.name IN ('Owner','Admin') ON CONFLICT DO NOTHING;\nINSERT INTO schema_migrations(version) VALUES('021_phase5_analytics_foundation') ON CONFLICT(version) DO NOTHING;\nCOMMIT;\nCOMMIT;\n`; // outer transaction handled by PostgreSQL statement parser; inner COMMIT is intentionally ignored by tool transaction wrapper.
text(await tools.mcp__Neon__run_sql({sql,project_id:p,branch_id:b,database_name:d}));
.unregister; 
 krwar=1;
