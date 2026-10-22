from pathlib import Path

ROOT = Path(__file__).parents[3]
SOURCE = Path(__file__).parents[1] / "app" / "routes" / "commerce.py"


def test_sales_history_supports_server_side_filters():
    source = SOURCE.read_text()
    block = source.split('@router.get("/sales")', 1)[1].split('@router.get("/sales/{sale_id}")', 1)[0]
    assert 'search: str | None = Query(default=None, max_length=100)' in block
    assert 'status: str | None = Query(default=None, max_length=20)' in block
    assert 'start_date: date | None = None' in block
    assert 'end_date: date | None = None' in block
    assert 'branch_id: UUID | None = None' in block
    assert 'LIMIT :lim OFFSET :off' in block
    assert 's.business_date >= :start_date' in block
    assert 's.business_date <= :end_date' in block


def test_sales_history_enforces_assigned_branch_scope():
    source = SOURCE.read_text()
    block = source.split('@router.get("/sales")', 1)[1].split('@router.get("/sales/{sale_id}")', 1)[0]
    assert 'membership_branch_assignments' in block
    assert "tm.status='ACTIVE'" in block
    assert "mba.status='ACTIVE'" in block
    assert 'ensure_branch_access(db, tenant_id=tenant_id, user_id=actor_id, branch_id=branch_id)' in block


def test_sale_detail_is_branch_authorized():
    source = SOURCE.read_text()
    block = source.split('@router.get("/sales/{sale_id}")', 1)[1].split('@router.post("/sales"', 1)[0]
    assert 'ensure_branch_access(db, tenant_id=tenant_id, user_id=actor_id, branch_id=sale["branch_id"])' in block
    assert 'Sale is not linked to an accessible branch' in block



def test_checkout_enforces_server_side_price_and_discount_capabilities():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales", status_code=201)', 1)[1].split('@router.get("/receivables")', 1)[0]
    assert "catalog.pricing.manage" in block
    assert "catalog.manage" in block
    assert "sales.manage" in block
    assert "Price override permission required" in block
    assert "Discount permission required" in block
    assert "No catalogue price is configured" in block


def test_cumulative_refund_balance_is_checked_inside_locked_sale_transaction():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    assert 'SELECT * FROM sales WHERE tenant_id=:t AND id=:s FOR UPDATE' in block
    assert 'JOIN sale_returns prior_return ON prior_return.id=rr.return_id AND prior_return.tenant_id=rr.tenant_id' in block
    assert "prior_return.sale_id=:s AND rr.status='RECORDED'" in block
    assert 'remaining_refund_balance(gross_collected,prior_refunds)' in block
    assert 'SUM(pa.amount)' in block
    assert 'p.status=\'RECORDED\'' in block
    assert 'AND (pa.sale_id=:s OR r.sale_id=:s)' in block
    assert 'Refund exceeds the remaining collected amount after previous refunds' in block


def test_returns_list_is_limited_to_active_assigned_branches():
    source = SOURCE.read_text()
    block = source.split('@router.get("/returns")', 1)[1].split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[0]
    assert 'JOIN sales s ON s.id=sr.sale_id AND s.tenant_id=sr.tenant_id' in block
    assert 'membership_branch_assignments' in block
    assert "tm.status='ACTIVE'" in block
    assert "mba.status='ACTIVE'" in block
    assert 'b.id=s.branch_id' in block


def test_sale_detail_includes_payment_return_and_refund_ledger_rows():
    source = SOURCE.read_text()
    block = source.split('@router.get("/sales/{sale_id}")', 1)[1].split('@router.post("/sales", status_code=201)', 1)[0]
    assert 'FROM payment_allocations pa' in block
    assert 'LEFT JOIN receivables r ON r.id=pa.receivable_id' in block
    assert 'FROM sale_returns sr WHERE sr.tenant_id=:t AND sr.sale_id=:s' in block
    assert 'FROM refund_records rr' in block
    assert 'result["payments"]' in block
    assert 'result["returns"]' in block
    assert 'result["refunds"]' in block


def test_sale_totals_refresh_happens_after_refund_or_credit_is_recorded():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    refund_insert = block.index('INSERT INTO refund_records')
    credit_insert = block.index('INSERT INTO customer_credits')
    refresh = block.index('SELECT refresh_sale_payment_totals(:t,:s)')
    assert refresh > refund_insert
    assert refresh > credit_insert


def test_refund_cap_does_not_double_subtract_prior_refunds_from_net_paid():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    assert 'remaining_refund_balance(sale["amount_paid"],prior_refunds)' not in block
    assert 'remaining_refund_balance(gross_collected,prior_refunds)' in block




def test_cash_refund_does_not_write_return_adjustment_against_receivable():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    guard = block.index("if body.settlement_type == 'NONE':")
    receivable_update = block.index('UPDATE receivables', guard)
    receivable_adjustment = block[guard:receivable_update]
    assert guard < receivable_update
    assert "if body.settlement_type != 'REFUND':" not in block
    assert 'GREATEST(original_amount-paid_amount,0)' in block[receivable_update:]



def test_partial_return_uses_prorated_line_adjustments():
    source = SOURCE.read_text()
    assert "prorate_return_line_amounts(" in source
    block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    assert '"d":str(line_discount)' in block
    assert '"tax":str(line_tax)' in block
    assert '"d":str(line["discount_amount"])' not in block
    assert '"tax":str(line["tax_amount"])' not in block



def test_completed_return_posts_settlement_and_inventory_cogs_journals():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    settle = block.index('post_sale_return_journal(:id,:u)')
    cogs = block.index('post_sale_return_cogs_journal(:id,:u)')
    commit = block.index('db.commit()', block.index('sale.return.created'))
    assert settle < cogs < commit
    assert 'entry_role":"RETURN_SETTLEMENT"' in block
    assert 'entry_role":"RETURN_COGS"' in block



def test_return_flow_connects_fiscal_credit_note_and_accounting_ledger():
    source = SOURCE.read_text()
    return_block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    assert 'create_fiscal_document_for_return(:id)' in return_block
    assert 'post_sale_return_journal(:id,:u)' in return_block
    assert 'post_sale_return_cogs_journal(:id,:u)' in return_block
    detail_block = source.split('@router.get("/sales/{sale_id}")', 1)[1].split('@router.post("/sales", status_code=201)', 1)[0]
    assert 'result["accounting_entries"]=[out(x) for x in accounting_entries]' in detail_block
    assert "entry_role='RETURN_SETTLEMENT'" in detail_block


def test_no_refund_return_is_limited_to_open_receivable():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    assert "if body.settlement_type == 'NONE':" in block
    assert "SUM(GREATEST(balance,0))" in block
    assert "status IN ('OPEN','PARTIALLY_PAID')" in block
    assert "choose REFUND or CUSTOMER_CREDIT settlement" in block


def test_return_request_rejects_duplicate_sale_lines_before_ledger_writes():
    source = SOURCE.read_text()
    block = source.split("class ReturnCreate(Strict):", 1)[1].split('@router.get("/returns")', 1)[0]
    assert '@field_validator("lines")' in block
    assert "ensure_unique_return_line_ids(line.sale_line_id for line in lines)" in block
    rules = (ROOT / "apps/api/app/commerce_rules.py").read_text()
    assert "len(line_ids) != len(set(line_ids))" in rules
    assert "combine quantities for the same line" in rules


def test_return_stock_is_valued_from_original_sale_ledger_and_skips_nonstock_items():
    source = SOURCE.read_text()
    block = source.split('@router.post("/sales/{sale_id}/returns", status_code=201)', 1)[1]
    assert "reference_type='sale' AND reference_id=:s" in block
    assert "original_sale_inventory_unit_cost" in block
    assert "Original sale stock movement is missing" in block
    assert "if tracks_inventory:" in block
    assert '"cost_basis":"original_sale_inventory_ledger"' in block
