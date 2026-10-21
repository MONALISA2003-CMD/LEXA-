import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_purchasing_routes_cover_supplier_order_receipt_return_and_payables_lifecycle():
    source = (ROOT / "apps/api/app/routes/purchasing.py").read_text()
    expected = [
        'prefix="/purchasing"', '@router.post("/suppliers")', '@router.patch("/suppliers/{supplier_party_id}")',
        '@router.post("/purchase-orders")', '@router.post("/purchase-orders/{order_id}/submit")',
        '@router.post("/purchase-orders/{order_id}/approve")', '@router.post("/purchase-orders/{order_id}/receipts")',
        '@router.post("/receipts/{receipt_id}/post")', '@router.post("/returns")',
        '@router.post("/returns/{return_id}/approve")', '@router.post("/returns/{return_id}/post")',
        '@router.post("/supplier-bills")', '@router.post("/supplier-bills/{bill_id}/post")',
        '@router.post("/supplier-payments")', '@router.post("/supplier-payments/{payment_id}/post")',
        '@router.get("/supplier-balances")', '@router.get("/supplier-ledger/{supplier_party_id}")',
    ]
    for token in expected:
        assert token in source, f"Missing Phase 7 lifecycle contract: {token}"
    assert 'require_permission("purchasing.approve")' in source
    assert 'require_permission("purchasing.receive")' in source
    assert 'require_permission("purchasing.bills.manage")' in source
    assert 'require_permission("purchasing.payments.manage")' in source


def test_posted_receipts_returns_and_financial_documents_use_inventory_or_supplier_ledger():
    source = (ROOT / "apps/api/app/routes/purchasing.py").read_text()
    assert 'transaction_type="PURCHASE_RECEIPT"' in source
    assert 'transaction_type="PURCHASE_RETURN"' in source
    assert "purchase_landed_cost_allocations" in source
    assert "supplier_ledger_entries" in source
    assert "ON CONFLICT(tenant_id,source_type,source_id,entry_type) DO NOTHING" in source


def test_phase7_migration_enforces_rls_and_supplier_balance_idempotency():
    sql = (ROOT / "migrations/039_phase7_supplier_ledger_landed_costs.sql").read_text()
    for table in ["purchase_landed_costs", "purchase_landed_cost_allocations", "supplier_bills", "supplier_payments", "supplier_payment_allocations", "supplier_ledger_entries"]:
        assert f"'{table}'" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "UNIQUE(tenant_id,source_type,source_id,entry_type)" in sql
    assert "purchasing.bills.manage" in sql and "purchasing.payments.manage" in sql


def test_phase7_status_writes_are_idempotent_and_currency_balances_are_not_mixed():
    source = (ROOT / "apps/api/app/routes/purchasing.py").read_text()
    for route in ["submit_purchase_order", "approve_purchase_order", "cancel_purchase_order", "close_purchase_order"]:
        start = source.index(f"def {route}(")
        end = source.find("\n@router.", start)
        block = source[start:end if end >= 0 else len(source)]
        assert 'Header(None, alias="Idempotency-Key")' in block, f"{route} must accept an idempotency key"
        assert "_transition_idem" in block
    assert "supplier_balances_by_currency" in source
    assert "sum(e.debit_amount-e.credit_amount),0) FROM public.supplier_ledger_entries e WHERE e.tenant_id=:t) AS net_supplier_payable" not in source


def test_supplier_invoice_requires_receipt_match_or_audited_exception():
    source = (ROOT / "apps/api/app/routes/purchasing.py").read_text()
    post_start = source.index('def post_supplier_bill(')
    post_end = source.find("\n@router.", post_start)
    post_block = source[post_start:post_end]
    assert 'bill["match_status"] in {"VARIANCE", "WAITING_RECEIPT"}' in post_block
    review_start = source.index('def accept_supplier_bill_variance(')
    review_end = source.find("\n@router.", review_start)
    review_block = source[review_start:review_end]
    assert 'bill["match_status"] not in {"VARIANCE", "WAITING_RECEIPT"}' in review_block
    assert "match_exception_approved" in review_block and "prior_match_status" in review_block


def test_phase7_migration_guards_ambiguous_active_supplier_price_tiers_and_has_invoice_match_state():
    sql = (ROOT / "migrations/039_phase7_supplier_ledger_landed_costs.sql").read_text()
    assert "duplicate active supplier-cost tiers exist" in sql
    assert "uq_supplier_variant_cost_active_tier" in sql
    assert "WAITING_RECEIPT" in sql and "match_reviewed_by" in sql
    assert "supplier_credit_unit_cost" in sql and "base_unit_cost" in sql


def test_phase7_supplier_financial_ledger_and_cost_allocations_are_append_only_at_runtime_privilege_boundary():
    sql = (ROOT / "migrations/039_phase7_supplier_ledger_landed_costs.sql").read_text()
    assert "REVOKE ALL PRIVILEGES ON TABLE public.purchase_landed_costs" in sql
    assert "GRANT SELECT,INSERT ON public.purchase_landed_costs,public.purchase_landed_cost_allocations,public.supplier_payment_allocations,public.supplier_ledger_entries TO lexa_app" in sql
    assert "GRANT SELECT,INSERT,UPDATE ON public.supplier_bills,public.supplier_payments TO lexa_app" in sql
    payment_alloc = sql.split("CREATE TABLE IF NOT EXISTS public.supplier_payment_allocations", 1)[1].split("CREATE INDEX IF NOT EXISTS idx_supplier_allocations_bill", 1)[0]
    assert payment_alloc.count("bill_id uuid NOT NULL") == 1

def test_phase7_supplier_payment_model_uses_shared_allocation_rule():
    source = (ROOT / "apps/api/app/routes/purchasing.py").read_text()
    assert "validate_payment_allocations(self.amount" in source
    assert "A supplier payment may allocate to each bill only once" in (ROOT / "apps/api/app/purchasing_rules.py").read_text()


def test_phase7_append_only_allocation_grants_are_compatible_with_bounded_row_locking():
    source = (ROOT / "apps/api/app/routes/purchasing.py").read_text()
    assert "ORDER BY a.bill_id FOR UPDATE OF b" in source, "lock bill rows for payment serialization without requesting UPDATE privileges on immutable allocation rows"
    assert "FOR UPDATE OF b" in source
    migration = (ROOT / "migrations/039_phase7_supplier_ledger_landed_costs.sql").read_text()
    assert "WHERE r.name IN ('Owner','Administrator','Finance / Accounting')" in migration
    assert "WHERE r.name='Inventory'" not in migration
