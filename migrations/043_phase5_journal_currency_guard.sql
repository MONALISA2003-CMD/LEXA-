-- Phase 5 ledger safety: posted entries must be balanced in one explicit currency.
-- This is a forward-only guard for future posting; it does not rewrite historical journals.
BEGIN;

CREATE OR REPLACE FUNCTION public.post_journal_entry(p_entry_id uuid, p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_tenant uuid;
  v_status text;
  v_period uuid;
  v_currency varchar(3);
  v_debit numeric;
  v_credit numeric;
  v_lines integer;
BEGIN
  SELECT tenant_id, status, period_id, currency_code
    INTO v_tenant, v_status, v_period, v_currency
    FROM public.journal_entries
   WHERE id = p_entry_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Journal entry not found'; END IF;
  IF v_status <> 'DRAFT' THEN RAISE EXCEPTION 'Only draft journal entries can be posted'; END IF;
  IF EXISTS (SELECT 1 FROM public.accounting_periods WHERE id = v_period AND status <> 'OPEN') THEN
    RAISE EXCEPTION 'Accounting period is not open';
  END IF;
  IF v_currency IS NULL OR v_currency !~ '^[A-Z]{3}$' THEN
    RAISE EXCEPTION 'Journal entry must declare a valid three-letter currency';
  END IF;
  IF EXISTS (
    SELECT 1
      FROM public.journal_lines jl
      LEFT JOIN public.accounting_accounts a
        ON a.tenant_id = jl.tenant_id AND a.id = jl.account_id
     WHERE jl.tenant_id = v_tenant
       AND jl.journal_entry_id = p_entry_id
       AND (
         upper(jl.currency_code) <> v_currency
         OR (a.currency_code IS NOT NULL AND upper(a.currency_code) <> v_currency)
       )
  ) THEN
    RAISE EXCEPTION 'Journal lines and any account denomination must use the journal entry currency';
  END IF;
  SELECT count(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
    INTO v_lines, v_debit, v_credit
    FROM public.journal_lines
   WHERE tenant_id = v_tenant AND journal_entry_id = p_entry_id;
  IF v_lines < 2 THEN RAISE EXCEPTION 'A journal entry requires at least two lines'; END IF;
  IF round(v_debit, 4) <> round(v_credit, 4) THEN
    RAISE EXCEPTION 'Journal entry is not balanced: debit %, credit %', v_debit, v_credit;
  END IF;
  IF EXISTS (
    SELECT 1
      FROM public.journal_lines jl
      JOIN public.accounting_accounts a
        ON a.id = jl.account_id AND a.tenant_id = jl.tenant_id
     WHERE jl.tenant_id = v_tenant
       AND jl.journal_entry_id = p_entry_id
       AND (a.status <> 'ACTIVE' OR NOT a.allow_posting)
  ) THEN
    RAISE EXCEPTION 'Journal contains an inactive or non-posting account';
  END IF;
  UPDATE public.journal_entries
     SET status = 'POSTED', posted_at = now(), posted_by = p_user_id, updated_at = now()
   WHERE tenant_id = v_tenant AND id = p_entry_id;
END
$fn$;

REVOKE ALL ON FUNCTION public.post_journal_entry(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.post_journal_entry(uuid, uuid) TO lexa_app;

INSERT INTO public.schema_migrations(version)
VALUES ('043_phase5_journal_currency_guard')
ON CONFLICT (version) DO NOTHING;
COMMIT;
