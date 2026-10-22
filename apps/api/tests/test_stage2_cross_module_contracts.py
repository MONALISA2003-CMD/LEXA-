from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _function_block(source: str, function_name: str) -> str:
    start = source.index(f"def {function_name}(")
    end = source.find("\n@router.", start)
    return source[start : end if end >= 0 else len(source)]


def test_customer_money_views_are_branch_scoped_until_branch_rollups_are_available():
    """Tenant-wide customer balances must not leak through a branch-limited view."""
    source = _source("app/routes/commerce.py")
    block = _function_block(source, "list_receivables")
    assert "EXISTS (" in block
    assert "membership_branch_assignments" in block
    assert "tm.user_id=:u" in block
    assert "r.balance" in block


def test_supplier_financial_summaries_require_full_branch_scope_until_ledger_is_attributed():
    source = _source("app/routes/purchasing.py")
    for name in ("purchasing_summary", "supplier_balances", "supplier_ledger"):
        block = _function_block(source, name)
        assert "require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor)" in block, name
    assert "Supplier totals are tenant-wide until the ledger is branch-attributed" in _function_block(source, "purchasing_summary")


def test_sales_and_supplier_receiving_use_the_same_inventory_ledger():
    commerce = _source("app/routes/commerce.py")
    purchasing = _source("app/routes/purchasing.py")
    assert 'transaction_type="SALE"' in commerce or "SALE" in commerce and "post_ledger" in commerce
    assert 'transaction_type="PURCHASE_RECEIPT"' in purchasing
    assert 'transaction_type="PURCHASE_RETURN"' in purchasing
    assert "post_ledger(" in purchasing


def test_sales_receipts_customer_balances_supplier_ledger_and_expenses_have_a_shared_financial_trail():
    commerce = _source("app/routes/commerce.py")
    purchasing = _source("app/routes/purchasing.py")
    finance = _source("app/routes/finance.py")
    analytics = _source("app/routes/analytics.py")

    assert "post_sale_journal" in commerce
    assert "post_payment_journal" in commerce
    assert "receivable.created" in commerce
    assert "supplier_ledger_entries" in purchasing
    assert "post_expense_journal" in finance
    assert "reverse_journal_entry" in finance
    assert "expense_reversals_total" in analytics
    assert "require_full_branch_scope" in finance


def test_cash_and_mobile_money_are_recorded_methods_not_provider_integrations():
    commerce = _source("app/routes/commerce.py")
    finance = _source("app/routes/finance.py")
    assert '"MOBILE_MONEY"' in commerce
    assert "payment_channel_id" in commerce
    assert "payment pin" not in commerce.lower()
    assert "gateway" not in finance.lower()


def test_purchase_orders_receipts_and_returns_are_limited_to_assigned_branches():
    source = _source("app/routes/purchasing.py")
    for name in ("list_purchase_orders", "list_receipts", "list_returns"):
        block = _function_block(source, name)
        assert "_many_branch_scoped" in block, name
    assert "_ensure_order_access(db, tenant_id=tenant_id, user_id=actor" in _function_block(source, "get_purchase_order")
    assert "_ensure_order_access(db, tenant_id=tenant_id, user_id=actor" in _function_block(source, "_transition_order")


def test_supplier_bill_and_payment_reads_writes_fail_closed_until_ledger_is_branch_attributed():
    source = _source("app/routes/purchasing.py")
    for name in ("list_supplier_bills", "create_supplier_bill", "post_supplier_bill", "list_supplier_payments", "create_supplier_payment", "post_supplier_payment"):
        assert "_require_workspace_finance_scope" in _function_block(source, name), name
    assert "Supplier bills/payments and their ledger are workspace-wide until entries carry a branch" in source


def test_supplier_return_mutations_validate_receipt_order_and_stock_location_chain():
    source = _source("app/routes/purchasing.py")
    create_return = _function_block(source, "create_return")
    cancel_return = _function_block(source, "cancel_return")
    approve_return = _function_block(source, "approve_return")
    post_return = _function_block(source, "post_return")
    assert "_ensure_order_access" in create_return
    assert "_ensure_receipt_location_matches_order" in create_return
    assert "PURCHASE_RETURN_LOCATION_MISMATCH" in cancel_return
    assert "PURCHASE_RETURN_LOCATION_MISMATCH" in approve_return
    assert "PURCHASE_RETURN_LOCATION_MISMATCH" in post_return
    assert "_ensure_receipt_location_matches_order" in _function_block(source, "post_receipt")
    assert "_ensure_receipt_location_matches_order" in _function_block(source, "cancel_receipt")
    assert "_ensure_receipt_location_matches_order" in create_return
    assert "r.receiving_location_id=pr.receiving_location_id" in _function_block(source, "list_returns")
    assert "r.receiving_location_id=pr.receiving_location_id" in _function_block(source, "get_return")
    assert "r.receiving_location_id=po.receiving_location_id" in _function_block(source, "list_receipts")
    assert "r.receiving_location_id=po.receiving_location_id" in _function_block(source, "get_receipt")


def test_payment_method_report_uses_recorded_payments_date_currency_and_full_scope():
    source = _source("app/routes/analytics.py")
    block = _function_block(source, "payments_by_channel")
    assert "require_full_branch_scope" in block
    assert "p.status = 'RECORDED'" in block
    assert "p.business_date BETWEEN :start_date AND :end_date" in block
    assert "p.currency_code = :currency_code" in block
    assert "payment_channels" in block
    assert "SUM(p.amount) AS recorded_amount" in block
