-- LEXA Phase 8 finance integrity: closed daily reconciliations are historical snapshots.
-- A later payment/refund correction must not silently rewrite an already closed day.
-- Forward-only correction: never edit the applied migration 018.
BEGIN;

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
    WHERE l.tenant_id=p_tenant_id AND l.payment_channel_id=p_channel_id AND h.business_date=p_business_date AND h.status <> 'CLOSED'
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
    WHERE l.tenant_id=p_tenant_id AND l.payment_channel_id=p_channel_id AND h.business_date=p_business_date AND h.status <> 'CLOSED'
  LOOP PERFORM refresh_reconciliation_header(r.reconciliation_id); END LOOP;
END;
$fn$;


INSERT INTO public.schema_migrations(version)
VALUES ('045_phase8_reconciliation_closed_snapshot')
ON CONFLICT(version) DO NOTHING;

COMMIT;
