BEGIN;

-- --------------------------------------------------------------------------
-- Phase 4A application integrity: payments, allocations, receivables,
-- reconciliation lifecycle and financial-history protection.
-- --------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION refresh_receivable(p_receivable_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_tenant uuid;
  v_sale uuid;
  v_paid numeric;
BEGIN
  SELECT tenant_id, sale_id INTO v_tenant, v_sale
  FROM receivables
  WHERE id = p_receivable_id
  FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;

  SELECT COALESCE(SUM(pa.amount), 0)
    INTO v_paid
  FROM payment_allocations pa
  JOIN payments p ON p.id = pa.payment_id AND p.tenant_id = pa.tenant_id
  WHERE pa.tenant_id = v_tenant
    AND pa.receivable_id = p_receivable_id
    AND pa.status = 'RECORDED'
    AND p.status = 'RECORDED';

  UPDATE receivables r
  SET paid_amount = LEAST(r.original_amount, v_paid),
      balance = GREATEST(r.original_amount - LEAST(r.original_amount, v_paid) - r.adjustment_amount, 0),
      status = CASE
        WHEN GREATEST(r.original_amount - LEAST(r.original_amount, v_paid) - r.adjustment_amount, 0) = 0 THEN 'PAID'
        WHEN LEAST(r.original_amount, v_paid) > 0 THEN 'PARTIALLY_PAID'
        ELSE 'OPEN'
      END,
      updated_at = now()
  WHERE r.id = p_receivable_id AND r.tenant_id = v_tenant;

  IF v_sale IS NOT NULL THEN
    PERFORM refresh_sale_payment_totals(v_tenant, v_sale);
  END IF;
END;
$fn$;

CREATE OR REPLACE FUNCTION refresh_sale_payment_totals(p_tenant_id uuid, p_sale_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_paid numeric;
  v_total numeric;
  v_return_adjustment numeric;
BEGIN
  SELECT total, return_adjustment_amount
    INTO v_total, v_return_adjustment
  FROM sales
  WHERE tenant_id=p_tenant_id AND id=p_sale_id
  FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;

  SELECT COALESCE(SUM(pa.amount), 0)
    INTO v_paid
  FROM payment_allocations pa
  JOIN payments p ON p.id=pa.payment_id AND p.tenant_id=pa.tenant_id
  LEFT JOIN receivables r ON r.id=pa.receivable_id AND r.tenant_id=pa.tenant_id
  WHERE pa.tenant_id=p_tenant_id
    AND pa.status='RECORDED'
    AND p.status='RECORDED'
    AND (pa.sale_id=p_sale_id OR r.sale_id=p_sale_id);

  UPDATE sales
  SET amount_paid=LEAST(total, v_paid),
      amount_due=GREATEST(total - LEAST(total, v_paid) - return_adjustment_amount, 0),
      updated_at=now()
  WHERE tenant_id=p_tenant_id AND id=p_sale_id;
END;
$fn$;

CREATE OR REPLACE FUNCTION validate_payment_allocation()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_payment_amount numeric;
  v_payment_status text;
  v_existing numeric;
  v_sale_total numeric;
  v_sale_returned numeric;
  v_receivable_original numeric;
  v_receivable_adjustment numeric;
BEGIN
  IF NEW.status='RECORDED' THEN
    SELECT amount, status INTO v_payment_amount, v_payment_status
    FROM payments
    WHERE tenant_id=NEW.tenant_id AND id=NEW.payment_id
    FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Payment not found for allocation'; END IF;
    IF v_payment_status <> 'RECORDED' THEN
      RAISE EXCEPTION 'Only recorded payments can have recorded allocations';
    END IF;

    IF TG_OP='UPDATE' AND OLD.status='RECORDED'
       AND (OLD.payment_id <> NEW.payment_id
            OR COALESCE(OLD.sale_id,'00000000-0000-0000-0000-000000000000') <> COALESCE(NEW.sale_id,'00000000-0000-0000-0000-000000000000')
            OR COALESCE(OLD.receivable_id,'00000000-0000-0000-0000-000000000000') <> COALESCE(NEW.receivable_id,'00000000-0000-0000-0000-000000000000')
            OR OLD.amount <> NEW.amount) THEN
      RAISE EXCEPTION 'Recorded payment allocations are append-only; reverse and create a new allocation';
    END IF;

    IF TG_OP='INSERT' THEN
      v_existing := COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE tenant_id=NEW.tenant_id AND payment_id=NEW.payment_id AND status='RECORDED'),0);
    ELSE
      v_existing := COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE tenant_id=NEW.tenant_id AND payment_id=NEW.payment_id AND status='RECORDED' AND id<>NEW.id),0);
    END IF;
    IF v_existing + NEW.amount > v_payment_amount THEN
      RAISE EXCEPTION 'Payment allocations cannot exceed payment amount';
    END IF;

    IF NEW.sale_id IS NOT NULL THEN
      SELECT total, return_adjustment_amount INTO v_sale_total, v_sale_returned
      FROM sales WHERE tenant_id=NEW.tenant_id AND id=NEW.sale_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'Sale not found for allocation'; END IF;
      IF TG_OP='INSERT' THEN
        v_existing := COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE tenant_id=NEW.tenant_id AND sale_id=NEW.sale_id AND status='RECORDED'),0);
      ELSE
        v_existing := COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE tenant_id=NEW.tenant_id AND sale_id=NEW.sale_id AND status='RECORDED' AND id<>NEW.id),0);
      END IF;
      IF v_existing + NEW.amount > GREATEST(v_sale_total - v_sale_returned,0) THEN
        RAISE EXCEPTION 'Sale allocations cannot exceed the remaining sale amount';
      END IF;
    ELSE
      SELECT original_amount, adjustment_amount INTO v_receivable_original, v_receivable_adjustment
      FROM receivables WHERE tenant_id=NEW.tenant_id AND id=NEW.receivable_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'Receivable not found for allocation'; END IF;
      IF TG_OP='INSERT' THEN
        v_existing := COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE tenant_id=NEW.tenant_id AND receivable_id=NEW.receivable_id AND status='RECORDED'),0);
      ELSE
        v_existing := COALESCE((SELECT SUM(amount) FROM payment_allocations WHERE tenant_id=NEW.tenant_id AND receivable_id=NEW.receivable_id AND status='RECORDED' AND id<>NEW.id),0);
      END IF;
      IF v_existing + NEW.amount > GREATEST(v_receivable_original - v_receivable_adjustment,0) THEN
        RAISE EXCEPTION 'Receivable allocations cannot exceed receivable amount';
      END IF;
    END IF;
  ELSIF TG_OP='UPDATE' AND OLD.status='RECORDED' AND NEW.status='REVERSED' THEN
    IF NEW.payment_id <> OLD.payment_id OR NEW.sale_id IS DISTINCT FROM OLD.sale_id OR NEW.receivable_id IS DISTINCT FROM OLD.receivable_id OR NEW.amount <> OLD.amount THEN
      RAISE EXCEPTION 'A recorded allocation can only transition to REVERSED';
    END IF;
  ELSIF TG_OP='UPDATE' AND OLD.status='REVERSED' AND NEW.status <> 'REVERSED' THEN
    RAISE EXCEPTION 'A reversed payment allocation cannot be reactivated';
  END IF;
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_validate_payment_allocation ON payment_allocations;
CREATE TRIGGER trg_validate_payment_allocation
BEFORE INSERT OR UPDATE ON payment_allocations
FOR EACH ROW EXECUTE FUNCTION validate_payment_allocation();

CREATE OR REPLACE FUNCTION sync_financial_totals_after_allocation()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF TG_OP='DELETE' THEN
    IF OLD.receivable_id IS NOT NULL THEN PERFORM refresh_receivable(OLD.receivable_id); END IF;
    IF OLD.sale_id IS NOT NULL THEN PERFORM refresh_sale_payment_totals(OLD.tenant_id, OLD.sale_id); END IF;
    RETURN OLD;
  END IF;
  IF NEW.receivable_id IS NOT NULL THEN PERFORM refresh_receivable(NEW.receivable_id); END IF;
  IF NEW.sale_id IS NOT NULL THEN PERFORM refresh_sale_payment_totals(NEW.tenant_id, NEW.sale_id); END IF;
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_sync_financial_totals_after_allocation ON payment_allocations;
CREATE TRIGGER trg_sync_financial_totals_after_allocation
AFTER INSERT OR UPDATE OR DELETE ON payment_allocations
FOR EACH ROW EXECUTE FUNCTION sync_financial_totals_after_allocation();

CREATE OR REPLACE FUNCTION protect_recorded_payment()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'Payments are not deleted; reverse or void the payment';
  END IF;
  IF OLD.status='RECORDED' AND (
      OLD.amount<>NEW.amount OR OLD.currency_code<>NEW.currency_code OR OLD.method<>NEW.method
      OR OLD.transaction_id IS DISTINCT FROM NEW.transaction_id
      OR OLD.party_id IS DISTINCT FROM NEW.party_id
      OR OLD.reference IS DISTINCT FROM NEW.reference
      OR OLD.payment_channel_id IS DISTINCT FROM NEW.payment_channel_id
      OR OLD.business_date<>NEW.business_date
  ) THEN
    RAISE EXCEPTION 'Recorded payment facts are immutable; use a reversal/correction event';
  END IF;
  IF OLD.status<>'RECORDED' AND NEW.status='RECORDED' THEN
    RAISE EXCEPTION 'A non-recorded payment cannot be reactivated as recorded';
  END IF;
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_protect_recorded_payment ON payments;
CREATE TRIGGER trg_protect_recorded_payment
BEFORE UPDATE OR DELETE ON payments
FOR EACH ROW EXECUTE FUNCTION protect_recorded_payment();

CREATE OR REPLACE FUNCTION sync_totals_after_payment_status()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE r record;
BEGIN
  IF OLD.status='RECORDED' AND NEW.status IN ('VOIDED','REVERSED') THEN
    UPDATE payment_allocations
    SET status='REVERSED'
    WHERE tenant_id=NEW.tenant_id AND payment_id=NEW.id AND status='RECORDED';
  END IF;
  FOR r IN SELECT DISTINCT sale_id FROM payment_allocations WHERE tenant_id=NEW.tenant_id AND payment_id=NEW.id AND sale_id IS NOT NULL
  LOOP PERFORM refresh_sale_payment_totals(NEW.tenant_id,r.sale_id); END LOOP;
  FOR r IN SELECT DISTINCT receivable_id FROM payment_allocations WHERE tenant_id=NEW.tenant_id AND payment_id=NEW.id AND receivable_id IS NOT NULL
  LOOP PERFORM refresh_receivable(r.receivable_id); END LOOP;
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_sync_totals_after_payment_status ON payments;
CREATE TRIGGER trg_sync_totals_after_payment_status
AFTER UPDATE OF status ON payments
FOR EACH ROW EXECUTE FUNCTION sync_totals_after_payment_status();

CREATE OR REPLACE FUNCTION refresh_reconciliation_header(p_reconciliation_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_missing int;
  v_unresolved int;
  v_resolved int;
  v_ack int;
BEGIN
  SELECT count(*) FILTER (WHERE actual_amount IS NULL),
         count(*) FILTER (WHERE variance IS NOT NULL AND variance<>0 AND status='VARIANCE_DETECTED'),
         count(*) FILTER (WHERE variance IS NOT NULL AND variance<>0 AND status='RESOLVED'),
         count(*) FILTER (WHERE variance IS NOT NULL AND variance<>0 AND status='ACKNOWLEDGED')
  INTO v_missing,v_unresolved,v_resolved,v_ack
  FROM daily_reconciliation_lines
  WHERE reconciliation_id=p_reconciliation_id;

  UPDATE daily_reconciliations
  SET status = CASE
      WHEN v_missing > 0 THEN 'OPEN'
      WHEN v_unresolved > 0 THEN 'VARIANCE_DETECTED'
      WHEN v_resolved > 0 THEN 'RESOLVED'
      WHEN v_ack > 0 THEN 'ACKNOWLEDGED'
      ELSE 'RECONCILED'
    END,
    updated_at=now()
  WHERE id=p_reconciliation_id AND status <> 'CLOSED';
END;
$fn$;

CREATE OR REPLACE FUNCTION refresh_reconciliation_channel_date(p_tenant_id uuid, p_channel_id uuid, p_business_date date)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT l.id
    FROM daily_reconciliation_lines l
    JOIN daily_reconciliations h ON h.id=l.reconciliation_id AND h.tenant_id=l.tenant_id
    WHERE l.tenant_id=p_tenant_id AND l.payment_channel_id=p_channel_id AND h.business_date=p_business_date
  LOOP
    UPDATE daily_reconciliation_lines
    SET expected_amount=calculate_payment_channel_expected(p_tenant_id,p_channel_id,p_business_date),
        variance=CASE WHEN actual_amount IS NULL THEN NULL ELSE actual_amount-calculate_payment_channel_expected(p_tenant_id,p_channel_id,p_business_date) END,
        status=CASE
          WHEN actual_amount IS NULL THEN 'OPEN'
          WHEN actual_amount=calculate_payment_channel_expected(p_tenant_id,p_channel_id,p_business_date) THEN 'CLOSED'
          WHEN status IN ('RESOLVED','ACKNOWLEDGED') THEN status
          ELSE 'VARIANCE_DETECTED'
        END,
        updated_at=now()
    WHERE id=r.id;
  END LOOP;

  FOR r IN
    SELECT DISTINCT reconciliation_id
    FROM daily_reconciliation_lines l
    JOIN daily_reconciliations h ON h.id=l.reconciliation_id AND h.tenant_id=l.tenant_id
    WHERE l.tenant_id=p_tenant_id AND l.payment_channel_id=p_channel_id AND h.business_date=p_business_date
  LOOP PERFORM refresh_reconciliation_header(r.reconciliation_id); END LOOP;
END;
$fn$;

CREATE OR REPLACE FUNCTION sync_reconciliation_after_money_change()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF TG_OP='DELETE' THEN
    PERFORM refresh_reconciliation_channel_date(OLD.tenant_id, OLD.payment_channel_id, OLD.business_date);
    RETURN OLD;
  END IF;
  IF TG_OP='UPDATE' AND (NEW.payment_channel_id IS DISTINCT FROM OLD.payment_channel_id OR NEW.business_date IS DISTINCT FROM OLD.business_date OR NEW.status IS DISTINCT FROM OLD.status) THEN
    PERFORM refresh_reconciliation_channel_date(OLD.tenant_id, OLD.payment_channel_id, OLD.business_date);
  END IF;
  PERFORM refresh_reconciliation_channel_date(NEW.tenant_id, NEW.payment_channel_id, NEW.business_date);
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_sync_reconciliation_after_payment ON payments;
CREATE TRIGGER trg_sync_reconciliation_after_payment
AFTER INSERT OR UPDATE OR DELETE ON payments
FOR EACH ROW EXECUTE FUNCTION sync_reconciliation_after_money_change();

CREATE OR REPLACE FUNCTION sync_reconciliation_after_refund_change()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF TG_OP='DELETE' THEN
    PERFORM refresh_reconciliation_channel_date(OLD.tenant_id, OLD.payment_channel_id, OLD.business_date);
    RETURN OLD;
  END IF;
  IF TG_OP='UPDATE' AND (NEW.payment_channel_id IS DISTINCT FROM OLD.payment_channel_id OR NEW.business_date IS DISTINCT FROM OLD.business_date OR NEW.status IS DISTINCT FROM OLD.status) THEN
    PERFORM refresh_reconciliation_channel_date(OLD.tenant_id, OLD.payment_channel_id, OLD.business_date);
  END IF;
  PERFORM refresh_reconciliation_channel_date(NEW.tenant_id, NEW.payment_channel_id, NEW.business_date);
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_sync_reconciliation_after_refund ON refund_records;
CREATE TRIGGER trg_sync_reconciliation_after_refund
AFTER INSERT OR UPDATE OR DELETE ON refund_records
FOR EACH ROW EXECUTE FUNCTION sync_reconciliation_after_refund_change();

CREATE OR REPLACE FUNCTION set_reconciliation_line_actual(p_line_id uuid, p_actual numeric, p_notes text, p_reviewer uuid)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE v_tenant uuid; v_date date; v_channel uuid; v_header_status text;
BEGIN
  IF p_actual < 0 THEN RAISE EXCEPTION 'Actual settlement cannot be negative'; END IF;
  SELECT l.tenant_id,h.business_date,l.payment_channel_id,h.status
    INTO v_tenant,v_date,v_channel,v_header_status
  FROM daily_reconciliation_lines l
  JOIN daily_reconciliations h ON h.id=l.reconciliation_id AND h.tenant_id=l.tenant_id
  WHERE l.id=p_line_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Reconciliation line not found'; END IF;
  IF v_header_status='CLOSED' THEN RAISE EXCEPTION 'Closed reconciliations cannot be edited'; END IF;
  UPDATE daily_reconciliation_lines
  SET actual_amount=p_actual, notes=p_notes, reviewed_by=p_reviewer, updated_at=now()
  WHERE id=p_line_id;
  PERFORM refresh_reconciliation_channel_date(v_tenant,v_channel,v_date);
END;
$fn$;

CREATE OR REPLACE FUNCTION resolve_reconciliation_line(p_line_id uuid, p_status text, p_reviewer uuid, p_notes text)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE v_variance numeric; v_header uuid; v_header_status text; v_line_status text;
BEGIN
  IF p_status NOT IN ('RESOLVED','ACKNOWLEDGED') THEN RAISE EXCEPTION 'Resolution status must be RESOLVED or ACKNOWLEDGED'; END IF;
  SELECT l.variance,l.reconciliation_id,h.status,l.status
    INTO v_variance,v_header,v_header_status,v_line_status
  FROM daily_reconciliation_lines l
  JOIN daily_reconciliations h ON h.id=l.reconciliation_id AND h.tenant_id=l.tenant_id
  WHERE l.id=p_line_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Reconciliation line not found'; END IF;
  IF v_header_status='CLOSED' THEN RAISE EXCEPTION 'Closed reconciliations cannot be edited'; END IF;
  IF v_variance IS NULL OR v_variance=0 THEN RAISE EXCEPTION 'A zero-variance line does not require resolution'; END IF;
  IF v_line_status NOT IN ('VARIANCE_DETECTED','RESOLVED','ACKNOWLEDGED') THEN RAISE EXCEPTION 'Only variance lines can be resolved'; END IF;
  UPDATE daily_reconciliation_lines SET status=p_status, reviewed_by=p_reviewer, notes=COALESCE(p_notes,notes), updated_at=now() WHERE id=p_line_id;
  PERFORM refresh_reconciliation_header(v_header);
END;
$fn$;

CREATE OR REPLACE FUNCTION close_daily_reconciliation(p_reconciliation_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_missing int;
  v_unresolved int;
BEGIN
  SELECT count(*) FILTER (WHERE actual_amount IS NULL),
         count(*) FILTER (WHERE variance IS NOT NULL AND variance<>0 AND status NOT IN ('RESOLVED','ACKNOWLEDGED'))
  INTO v_missing,v_unresolved
  FROM daily_reconciliation_lines
  WHERE reconciliation_id=p_reconciliation_id;
  IF v_missing > 0 THEN RAISE EXCEPTION 'All reconciliation lines require actual amounts before closing'; END IF;
  IF v_unresolved > 0 THEN RAISE EXCEPTION 'Reconciliation has unresolved variances'; END IF;
  UPDATE daily_reconciliations
  SET status='CLOSED', closed_at=now(), updated_at=now()
  WHERE id=p_reconciliation_id AND status IN ('RECONCILED','RESOLVED','ACKNOWLEDGED');
  IF NOT FOUND THEN RAISE EXCEPTION 'Reconciliation cannot be closed from its current state'; END IF;
END;
$fn$;

CREATE OR REPLACE FUNCTION refresh_reconciliation_header_after_line()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  PERFORM refresh_reconciliation_header(NEW.reconciliation_id);
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_refresh_reconciliation_header_after_line ON daily_reconciliation_lines;
CREATE TRIGGER trg_refresh_reconciliation_header_after_line
AFTER INSERT OR UPDATE ON daily_reconciliation_lines
FOR EACH ROW EXECUTE FUNCTION refresh_reconciliation_header_after_line();

CREATE INDEX IF NOT EXISTS idx_payment_allocations_payment_status ON payment_allocations(tenant_id,payment_id,status);
CREATE INDEX IF NOT EXISTS idx_payment_allocations_sale_status ON payment_allocations(tenant_id,sale_id,status);
CREATE INDEX IF NOT EXISTS idx_payment_allocations_receivable_status ON payment_allocations(tenant_id,receivable_id,status);
CREATE INDEX IF NOT EXISTS idx_reconciliation_lines_channel ON daily_reconciliation_lines(tenant_id,payment_channel_id,reconciliation_id);

INSERT INTO schema_migrations(version) VALUES ('018_phase4a_application_integrity') ON CONFLICT (version) DO NOTHING;
COMMIT;
