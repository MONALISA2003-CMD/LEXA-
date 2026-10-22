from decimal import Decimal
import pytest
from app.purchasing_rules import allocate_landed_cost, line_amounts, money, order_status_from_receipts, supplier_balance, validate_payment_allocations


def test_purchase_line_amounts_rounds_subtotal_and_tax_independently():
    subtotal, tax, total = line_amounts(Decimal("3"), Decimal("100.125"), Decimal("18"))
    assert subtotal == Decimal("300.38")
    assert tax == Decimal("54.07")
    assert total == Decimal("354.45")


@pytest.mark.parametrize("method", ["BY_VALUE", "BY_QUANTITY", "EQUALLY"])
def test_landed_cost_allocation_reconciles_exactly_and_is_deterministic(method):
    lines = [
        {"id": "line-a", "quantity": "3", "base_unit_cost": "100"},
        {"id": "line-b", "quantity": "7", "base_unit_cost": "25"},
        {"id": "line-c", "quantity": "1", "base_unit_cost": "18"},
    ]
    allocated = allocate_landed_cost("17.23", lines, method)
    assert sum((row["allocated_amount"] for row in allocated), Decimal("0")) == Decimal("17.23")
    assert allocated == allocate_landed_cost("17.23", lines, method)
    assert [row["receipt_line_id"] for row in allocated] == ["line-a", "line-b", "line-c"]


def test_landed_cost_rejects_empty_or_invalid_allocation_basis():
    with pytest.raises(ValueError):
        allocate_landed_cost("1.00", [], "BY_VALUE")
    with pytest.raises(ValueError):
        allocate_landed_cost("1.00", [{"id": "x", "quantity": "0", "base_unit_cost": "2"}], "BY_VALUE")
    with pytest.raises(ValueError):
        allocate_landed_cost("1.00", [{"id": "x", "quantity": "1", "base_unit_cost": "2"}], "FIFO")


def test_purchase_order_status_uses_all_lines_and_partial_receipts():
    assert order_status_from_receipts([
        {"ordered_quantity": "5", "received_quantity": "5"},
        {"ordered_quantity": "2", "received_quantity": "0"},
    ]) == "PARTIALLY_RECEIVED"
    assert order_status_from_receipts([
        {"ordered_quantity": "5", "received_quantity": "5"},
        {"ordered_quantity": "2", "received_quantity": "2"},
    ]) == "FULLY_RECEIVED"
    assert order_status_from_receipts([
        {"ordered_quantity": "5", "received_quantity": "0"},
    ]) == "OPEN"


def test_supplier_balance_exposes_payable_and_advance_separately():
    result = supplier_balance([Decimal("125"), Decimal("5")], [Decimal("80")])
    assert result == {"net_balance": Decimal("50.00"), "payable": Decimal("50.00"), "supplier_credit": Decimal("0")}
    credit = supplier_balance([Decimal("50")], [Decimal("70")])
    assert credit == {"net_balance": Decimal("-20.00"), "payable": Decimal("0"), "supplier_credit": Decimal("20.00")}


def test_money_is_cents_normalized():
    assert money("2.345") == Decimal("2.35")
    assert money("2.344") == Decimal("2.34")


def test_supplier_payment_allocations_allow_advances_but_reject_duplicate_bills_and_overallocation():
    assert validate_payment_allocations("100.00", [{"bill_id":"a","amount":"30.00"},{"bill_id":"b","amount":"20.00"}]) == Decimal("50.00")
    with pytest.raises(ValueError, match="each bill only once"):
        validate_payment_allocations("100.00", [{"bill_id":"a","amount":"30.00"},{"bill_id":"a","amount":"20.00"}])
    with pytest.raises(ValueError, match="cannot exceed payment amount"):
        validate_payment_allocations("100.00", [{"bill_id":"a","amount":"101.00"}])
