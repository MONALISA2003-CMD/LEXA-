BEGIN;

CREATE OR REPLACE FUNCTION refresh_customer_credit(p_credit_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_tenant uuid;
  v_allocated numeric;
BEGIN
  SELECT tenant_id INTO v_tenant
  FROM customer_credits
  WHERE id=p_credit_id
  FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;

  SELECT COALESCE(SUM(amount),0)
    INTO v_allocated
  FROM customer_credit_allocations
  WHERE tenant_id=v_tenant
    AND customer_credit_id=p_credit_id
    AND status='RECORDED';

  UPDATE customer_credits
  SET allocated_amount=LEAST(original_amount,v_allocated),
      balance=GREATEST(original_amount-LEAST(original_amount,v_allocated),0),
      status=CASE
        WHEN GREATEST(original_amount-LEAST(original_amount,v_allocated),0)=0 THEN 'USED'
        WHEN LEAST(original_amount,v_allocated)>0 THEN 'PARTIALLY_USED'
        ELSE 'OPEN'
      END,
      updated_at=now()
  WHERE tenant_id=v_tenant AND id=p_credit_id;
END
$fn$;

CREATE OR REPLACE FUNCTION refresh_receivable(p_receivable_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_paid numeric;
  v_tenant uuid;
  v_sale uuid;
BEGIN
  SELECT tenant_id,sale_id INTO v_tenant,v_sale
  FROM receivables
  WHERE id=p_receivable_id
  FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;

  SELECT COALESCE((SELECT SUM(pa.amount)
      FROM payment_allocations pa
      JOIN payments p ON p.id=pa.payment_id AND p.tenant_id=pa.tenant_id
      WHERE pa.tenant_id=v_tenant
        AND pa.receivable_id=p_receivable_id
        AND pa.status='RECORDED'
        AND p.status='RECORDED'),0)
    + COALESCE((SELECT SUM(cca.amount)
      FROM customer_credit_allocations cca
      WHERE cca.tenant_id=v_tenant
        AND cca.receivable_id=p_receivable_id
        AND cca.status='RECORDED'),0)
    INTO v_paid;

  UPDATE receivables
  SET paid_amount=LEAST(original_amount,v_paid),
      balance=GREATEST(original_amount-LEAST(original_amount,v_paid)-adjustment_amount,0),
      status=CASE
        WHEN GREATEST(original_amount-LEAST(original_amount,v_paid)-adjustment_amount,0)=0 THEN 'PAID'
        WHEN LEAST(original_amount,v_paid)>0 THEN 'PARTIALLY_PAID'
        ELSE 'OPEN'
      END,
      updated_at=now()
  WHERE tenant_id=v_tenant AND id=p_receivable_id;

  IF v_sale IS NOT NULL THEN
    PERFORM refresh_sale_payment_totals(v_tenant,v_sale);
  END IF;
END
$fn$;

CREATE OR REPLACE FUNCTION validate_customer_credit_allocation()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_credit_balance numeric;
  v_credit_customer uuid;
  v_receivable_balance numeric;
  v_receivable_customer uuid;
  v_existing numeric;
BEGIN
  IF NEW.status='RECORDED' THEN
    SELECT balance,customer_party_id
      INTO v_credit_balance,v_credit_customer
    FROM customer_credits
    WHERE tenant_id=NEW.tenant_id AND id=NEW.customer_credit_id
    FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Customer credit not found'; END IF;
    IF v_credit_balance<=0 THEN RAISE EXCEPTION 'Customer credit has no available balance'; END IF;

    SELECT balance,customer_party_id
      INTO v_receivable_balance,v_receivable_customer
    FROM receivables
    WHERE tenant_id=NEW.tenant_id AND id=NEW.receivable_id
    FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Receivable not found'; END IF;
    IF v_credit_customer<>v_receivable_customer THEN
      RAISE EXCEPTION 'Customer credit and receivable belong to different customers';
    END IF;

    SELECT COALESCE(SUM(amount),0)
      INTO v_existing
    FROM customer_credit_allocations
    WHERE tenant_id=NEW.tenant_id
      AND customer_credit_id=NEW.customer_credit_id
      AND status='RECORDED'
      AND (TG_OP='INSERT' OR id<>NEW.id);
    IF v_existing+NEW.amount>v_credit_balance THEN
      RAISE EXCEPTION 'Customer credit allocations cannot exceed available credit balance';
    END IF;

    SELECT COALESCE(SUM(amount),0)
      INTO v_existing
    FROM customer_credit_allocations
    WHERE tenant_id=NEW.tenant_id
      AND receivable_id=NEW.receivable_id
      AND status='RECORDED'
      AND (TG_OP='INSERT' OR id<>NEW.id);
    IF v_existing+NEW.amount>v_receivable_balance THEN
      RAISE EXCEPTION 'Customer credit allocation cannot exceed receivable balance';
    END IF;

  ELSIF TG_OP='UPDATE' AND OLD.status='RECORDED' AND NEW.status='REVERSED' THEN
    IF NEW.customer_credit_id<>OLD.customer_credit_id
       OR NEW.receivable_id<>OLD.receivable_id
       OR NEW.amount<>OLD.amount THEN
      RAISE EXCEPTION 'A recorded customer credit allocation can only transition to REVERSED';
    END IF;
  ELSIF TG_OP='UPDATE' AND OLD.status='REVERSED' AND NEW.status<>'REVERSED' THEN
    RAISE EXCEPTION 'A reversed customer credit allocation cannot be reactivated';
  END IF;

  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_validate_customer_credit_allocation ON customer_credit_allocations;
CREATE TRIGGER trg_validate_customer_credit_allocation
BEFORE INSERT OR UPDATE ON customer_credit_allocations
FOR EACH ROW EXECUTE FUNCTION validate_customer_credit_allocation();

CREATE OR REPLACE FUNCTION sync_customer_credit_allocation_totals()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF TG_OP='DELETE' THEN
    PERFORM refresh_customer_credit(OLD.customer_credit_id);
    PERFORM refresh_receivable(OLD.receivable_id);
    RETURN OLD;
  END IF;
  PERFORM refresh_customer_credit(NEW.customer_credit_id);
  PERFORM refresh_receivable(NEW.receivable_id);
  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_sync_customer_credit_allocation_totals ON customer_credit_allocations;
CREATE TRIGGER trg_sync_customer_credit_allocation_totals
AFTER INSERT OR UPDATE OR DELETE ON customer_credit_allocations
FOR EACH ROW EXECUTE FUNCTION sync_customer_credit_allocation_totals();

CREATE INDEX IF NOT EXISTS idx_customer_credit_allocations_credit_status
  ON customer_credit_allocations(tenant_id,customer_credit_id,status);
CREATE INDEX IF NOT EXISTS idx_customer_credit_allocations_receivable_status
  ON customer_credit_allocations(tenant_id,receivable_id,status);

INSERT INTO schema_migrations(version)
VALUES ('019_phase4a_customer_credit_allocation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
