from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMERCE = ROOT / "app" / "routes" / "commerce.py"
FINANCE = ROOT / "app" / "routes" / "finance.py"
MIGRATION = ROOT.parent.parent / "migrations" / "040_phase8_finance_workflows.sql"


def test_payment_method_deactivation_is_tenant_scoped_and_keeps_history():
    source = COMMERCE.read_text(encoding="utf-8")
    block = source.split('@router.post("/payment-channels/{channel_id}/deactivate")', 1)[1].split('@router.get("/products")', 1)[0]
    assert 'require_permission("financial.configure")' in block
    assert "WHERE tenant_id=:t AND id=:id FOR UPDATE" in block
    assert "UPDATE payment_channels SET active=false" in block
    assert "DELETE FROM payment_channels" not in block
    assert "PAYMENT_METHOD_DEACTIVATED" in block
    assert "past" not in block.lower()  # the API changes availability only, not transaction data


def test_expense_creation_requires_a_real_payment_method_and_uses_idempotency():
    source = FINANCE.read_text(encoding="utf-8")
    block = source.split('@router.post("/expenses", status_code=201)', 1)[1].split('@router.post("/expenses/{expense_id}/post")', 1)[0]
    assert 'begin_idempotency(' in block
    assert 'finish_idempotency(' in block
    assert "WHERE tenant_id=:t AND id=:id AND account_type='EXPENSE' AND status='ACTIVE' AND allow_posting=true" in block
    assert "WHERE tenant_id=:t AND id=:id AND active=true AND currency_code=:cc" in block
    assert "expense.draft_created" in block
    assert "require_full_branch_scope" in block


def test_post_void_and_reverse_expense_actions_are_tenant_scoped_and_audited():
    source = FINANCE.read_text(encoding="utf-8")
    post = source.split('@router.post("/expenses/{expense_id}/post")', 1)[1].split('@router.post("/expenses/{expense_id}/void")', 1)[0]
    void = source.split('@router.post("/expenses/{expense_id}/void")', 1)[1].split('@router.post("/expenses/{expense_id}/reverse")', 1)[0]
    reverse = source.split('@router.post("/expenses/{expense_id}/reverse")', 1)[1].split('@compliance.get("/efris/config")', 1)[0]
    assert "WHERE tenant_id=:t AND id=:id FOR UPDATE" in post
    assert "expense.posted" in post
    assert "WHERE tenant_id=:t AND id=:id FOR UPDATE" in void
    assert "status='VOIDED'" in void and "status='DRAFT'" in void
    assert "Only a draft can be cancelled" in void
    assert "WHERE tenant_id=:t AND id=:id FOR UPDATE" in reverse
    assert "reverse_journal_entry" in reverse
    assert "reversal_journal_entry_id=:r" in reverse
    assert "status='REVERSED'" in reverse
    assert "expense.reversed" in reverse


def test_phase8_expense_migration_uses_business_date_and_traceable_reversal():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS reversal_journal_entry_id uuid" in source
    assert "('DRAFT','POSTED','VOIDED','REVERSED')" in source
    assert "ensure_accounting_period(v_tenant,v_expense_date)" in source
    assert "active=true AND currency_code=v_currency" in source
    assert "Select the payment method used for this expense" in source
    assert "040_phase8_finance_workflows" in source


def test_reconciliation_updates_and_close_are_idempotent_and_tenant_scoped():
    source = COMMERCE.read_text(encoding="utf-8")
    actual = source.split('@router.post("/reconciliation-lines/{line_id}/actual")', 1)[1].split('@router.post("/reconciliation-lines/{line_id}/resolve")', 1)[0]
    resolve = source.split('@router.post("/reconciliation-lines/{line_id}/resolve")', 1)[1].split('@router.post("/reconciliations/{reconciliation_id}/close")', 1)[0]
    close = source.split('@router.post("/reconciliations/{reconciliation_id}/close")', 1)[1].split('class ReturnLineIn', 1)[0]
    for block in (actual, resolve, close):
        assert '_idempotency(' in block
        assert '_finish(' in block
        assert 'require_full_branch_scope' in block
    assert 'SELECT id,business_date,status,closed_at FROM daily_reconciliations WHERE tenant_id=:t AND id=:id FOR UPDATE' in close
    assert 'if existing["status"] != "CLOSED"' in close


def test_finance_analytics_reports_recorded_expense_reversals_separately():
    source = MIGRATION.read_text(encoding="utf-8")
    api = (ROOT / "app" / "routes" / "analytics.py").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS expense_reversals_total" in source
    assert "rj.entry_date,er.currency_code" in source
    assert "COALESCE(exrev.expense_reversals_total,0)" in source
    assert "expense_reversals_total" in api


def test_reconciliation_includes_inactive_methods_that_have_historical_receipts():
    source = COMMERCE.read_text(encoding="utf-8")
    create = source.split('@router.post("/reconciliations", status_code=201)', 1)[1].split('@router.post("/reconciliation-lines/{line_id}/actual")', 1)[0]
    assert "pc.active=true" in create
    assert "FROM payments p WHERE p.tenant_id=pc.tenant_id AND p.payment_channel_id=pc.id AND p.business_date=:d" in create
    assert "FROM refund_records rr WHERE rr.tenant_id=pc.tenant_id AND rr.payment_channel_id=pc.id AND rr.business_date=:d" in create


def test_expense_correction_is_not_misreported_as_cash_received():
    source = MIGRATION.read_text(encoding="utf-8")
    # Correcting an accounting entry does not prove cash was physically returned.
    assert "COALESCE(pay.payments_collected,0)-COALESCE(ref.refunds_total,0)-COALESCE(exout.expense_cash_outflow,0)," in source
    assert "status IN ('POSTED','REVERSED') AND currency_code=c.currency_code AND expense_date=c.business_date" in source
    assert "status='POSTED' AND currency_code=c.currency_code AND expense_date=c.business_date" in source
    assert "expense_reversals_total,net_cash_movement" in source
    assert "The earlier entry is kept for history" in (ROOT.parent.parent / "apps" / "web" / "app" / "accounting" / "page.tsx").read_text(encoding="utf-8")


def test_expense_correction_uses_the_business_date_not_the_server_date():
    source = FINANCE.read_text(encoding="utf-8")
    reverse = source.split('@router.post("/expenses/{expense_id}/reverse")', 1)[1].split('@compliance.get("/efris/config")', 1)[0]
    assert "public.lexa_business_date(now(), :tenant_id)" in reverse
    assert "reverse_journal_entry(:id,:u,:d)" in reverse


def test_expense_reference_rejects_explicit_credential_terms():
    source = FINANCE.read_text(encoding="utf-8")
    model = source.split("class ExpenseCreate(Strict):", 1)[1].split("class ExpenseAction", 1)[0]
    assert "@field_validator(\"reference\")" in model
    assert "_EXPENSE_REFERENCE_SECRET.search(cleaned)" in model
    assert "Never enter a PIN, password or verification code" in model


def test_expense_history_is_tenant_scoped_and_returns_only_a_safe_timeline():
    source = FINANCE.read_text(encoding="utf-8")
    block = source.split('@router.get("/expenses/{expense_id}/history")', 1)[1].split('@router.post("/expenses", status_code=201)', 1)[0]
    assert 'require_permission("expenses.read")' in block
    assert "require_full_branch_scope" in block
    assert "WHERE tenant_id=:t AND id=:id" in block
    assert "e.actor_id" in block and "u.email AS actor_email" in block
    assert "e.payload->>'reason' AS reason" in block
    assert "return [{\"event_type\": row[\"event_type\"]" in block
    assert "e.last_error" not in block and "e.payload" in block
