BEGIN;

CREATE OR REPLACE FUNCTION calculate_payment_channel_expected(p_tenant_id uuid,p_channel_id uuid,p_business_date date)
RETURNS numeric LANGUAGE sql STABLE AS $fn$
  SELECT COALESCE((SELECT SUM(amount) FROM payments WHERE tenant_id=p_tenant_id AND payment_channel_id=p_channel_id AND business_date=p_business_date AND status='RECORDED'),0)
       - COALESCE((SELECT SUM(amount) FROM refund_records WHERE tenant_id=p_tenant_id AND payment_channel_id=p_channel_id AND business_date=p_business_date AND status='RECORDED'),0)
$fn$;

CREATE OR REPLACE FUNCTION refresh_reconciliation_line()
RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE d date;
BEGIN
  SELECT business_date INTO d FROM daily_reconciliations WHERE id=NEW.reconciliation_id AND tenant_id=NEW.tenant_id;
  IF d IS NULL THEN RAISE EXCEPTION 'Reconciliation header not found'; END IF;
  NEW.expected_amount := calculate_payment_channel_expected(NEW.tenant_id,NEW.payment_channel_id,d);
  IF NEW.actual_amount IS NULL THEN NEW.variance := NULL; NEW.status := 'OPEN';
  ELSIF NEW.actual_amount = NEW.expected_amount THEN NEW.variance := 0; NEW.status := 'CLOSED';
  ELSIF NEW.status IN ('RESOLVED','ACKNOWLEDGED') THEN NEW.variance := NEW.actual_amount-NEW.expected_amount;
  ELSE NEW.variance := NEW.actual_amount-NEW.expected_amount; NEW.status := 'VARIANCE_DETECTED'; END IF;
  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_refresh_reconciliation_line ON daily_reconciliation_lines;
CREATE TRIGGER trg_refresh_reconciliation_line BEFORE INSERT OR UPDATE OF payment_channel_id,actual_amount,reconciliation_id ON daily_reconciliation_lines FOR EACH ROW EXECUTE FUNCTION refresh_reconciliation_line();

CREATE OR REPLACE FUNCTION refresh_reconciliation_lines(p_reconciliation_id uuid)
RETURNS void LANGUAGE plpgsql AS $fn$
DECLARE r record;
BEGIN
  FOR r IN SELECT id FROM daily_reconciliation_lines WHERE reconciliation_id=p_reconciliation_id LOOP UPDATE daily_reconciliation_lines SET actual_amount=actual_amount WHERE id=r.id; END LOOP;
END
$fn$;

CREATE OR REPLACE FUNCTION close_daily_reconciliation(p_reconciliation_id uuid)
RETURNS void LANGUAGE plpgsql AS $fn$
DECLARE missing_count int; unresolved_count int;
BEGIN
  SELECT count(*) FILTER (WHERE actual_amount IS NULL), count(*) FILTER (WHERE variance IS NOT NULL AND variance<>0 AND status NOT IN ('RESOLVED','ACKNOWLEDGED')) INTO missing_count,unresolved_count FROM daily_reconciliation_lines WHERE reconciliation_id=p_reconciliation_id;
  IF missing_count>0 THEN RAISE EXCEPTION 'All reconciliation lines require actual amounts before closing'; END IF;
  IF unresolved_count>0 THEN RAISE EXCEPTION 'Reconciliation has unresolved variances'; END IF;
  UPDATE daily_reconciliations SET status='CLOSED',closed_at=now(),updated_at=now() WHERE id=p_reconciliation_id AND status IN ('RECONCILED','RESOLVED','ACKNOWLEDGED');
  IF NOT FOUND THEN RAISE EXCEPTION 'Reconciliation cannot be closed from its current state'; END IF;
END
$fn$;

CREATE INDEX IF NOT EXISTS idx_payments_channel_date_status ON payments(tenant_id,payment_channel_id,business_date,status);
CREATE INDEX IF NOT EXISTS idx_refunds_channel_date_status ON refund_records(tenant_id,payment_channel_id,business_date,status);
CREATE INDEX IF NOT EXISTS idx_reconciliation_lines_channel_date ON daily_reconciliation_lines(tenant_id,payment_channel_id,reconciliation_id);

INSERT INTO schema_migrations(version) VALUES ('017_phase4a_reconciliation_engine') ON CONFLICT (version) DO NOTHING;
COMMIT;
