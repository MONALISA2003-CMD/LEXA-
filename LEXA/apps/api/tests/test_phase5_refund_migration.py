from pathlib import Path

ROOT = Path(__file__).parents[3]
MIGRATION = ROOT / "migrations" / "033_phase5_refund_settlement_consistency.sql"


def test_refund_migration_uses_gross_collections_less_recorded_refunds():
    source = MIGRATION.read_text()
    assert "SUM(pa.amount)" in source
    assert "v_gross_collected - v_recorded_refunds" in source
    assert "sr.status = 'COMPLETED'" in source
    assert "rr.status = 'RECORDED'" in source


def test_refund_migration_distinguishes_credit_issued_from_credit_applied_to_sale():
    source = MIGRATION.read_text()
    update = source.split("UPDATE public.sales", 1)[1].split("$fn$;", 1)[0]
    assert "amount_due = GREATEST(" in update
    assert "v_customer_credit_issued" in update
    assert "v_customer_credit_applied" in update
    assert "+ v_customer_credit_issued" in update
    assert "- v_customer_credit_applied" in update


def test_refund_ledger_trigger_reconciles_sale_totals_after_changes():
    source = MIGRATION.read_text()
    assert "CREATE OR REPLACE FUNCTION public.sync_sale_payment_totals_after_refund_change()" in source
    assert "AFTER INSERT OR UPDATE OR DELETE ON public.refund_records" in source
    assert "EXECUTE FUNCTION public.sync_sale_payment_totals_after_refund_change()" in source
    assert "033_phase5_refund_settlement_consistency" in source



def test_analytics_credit_metrics_use_authoritative_sale_amount_due():
    analytics_source = (ROOT / "migrations" / "021_phase5_analytics_foundation.sql").read_text()
    migration_source = MIGRATION.read_text()
    for source in (analytics_source, migration_source):
        assert "SUM(GREATEST(sx.amount_due,0)) credit_created" in source
        assert "SUM(GREATEST(amount_due,0)) credit_created" in source
        assert "SUM(GREATEST(sx.total-sx.amount_paid-sx.return_adjustment_amount,0))" not in source
        assert "SUM(GREATEST(total-amount_paid-return_adjustment_amount,0))" not in source
    assert "CREATE OR REPLACE FUNCTION public.refresh_analytics" in migration_source
    assert "sales.amount_due as the authoritative receivable" in migration_source



def test_return_accounting_migration_posts_refunds_credits_ar_and_returned_cogs():
    accounting = (ROOT / "migrations" / "034_phase5_return_accounting_journals.sql").read_text()
    for token in (
        "post_sale_return_journal", "RETURN_SETTLEMENT", "SALES_RETURNS",
        "OUTPUT_TAX", "CUSTOMER_CREDITS", "ACCOUNTS_RECEIVABLE",
        "post_sale_return_cogs_journal", "RETURN_COGS",
        "Returned inventory restored", "Reverse cost of goods sold for return",
        "034_phase5_return_accounting_journals",
        "create_fiscal_document_for_return", "document_type='CREDIT_NOTE'",
    ):
        assert token in accounting
    assert "SOURCE_RETURN" not in accounting


def test_no_refund_return_guard_migration_is_present():
    guard = (ROOT / "migrations" / "035_phase5_none_return_receivable_guard.sql").read_text()
    assert "035_phase5_none_return_receivable_guard" in guard
    assert "v_ar_reduction>v_open_receivable" in guard
    assert "status IN ('OPEN','PARTIALLY_PAID')" in guard
