from decimal import Decimal

import pytest

from app.commerce_rules import remaining_refund_balance


@pytest.mark.parametrize(
    ("collected", "prior_refunds", "expected"),
    [
        ("1000", "0", "1000.0000"),
        ("1000", "250.5", "749.5000"),
        ("1000", "1000", "0.0000"),
        ("1000", "1200", "0.0000"),
        ("10.12345", "1.00004", "9.1235"),
    ],
)
def test_remaining_refund_balance_is_cumulative_and_nonnegative(collected, prior_refunds, expected):
    assert remaining_refund_balance(collected, prior_refunds) == Decimal(expected)


@pytest.mark.parametrize(("collected", "prior_refunds"), [("-1", "0"), ("10", "-0.01")])
def test_remaining_refund_balance_rejects_negative_ledger_totals(collected, prior_refunds):
    with pytest.raises(ValueError, match="cannot be negative"):
        remaining_refund_balance(collected, prior_refunds)



def test_sale_settlement_totals_preserves_receivable_after_cash_refund():
    from decimal import Decimal
    from app.commerce_rules import sale_settlement_totals

    # $15,000 sale: $10,000 collected, $5,000 due. Refund an $8,000 returned
    # line in cash. Net collections become $2,000 and the remaining due stays $5,000.
    assert sale_settlement_totals("15000", "8000", "10000", "8000") == (Decimal("2000.0000"), Decimal("5000.0000"))


def test_sale_settlement_totals_keeps_unallocated_customer_credit_separate_from_due():
    from decimal import Decimal
    from app.commerce_rules import sale_settlement_totals

    # A $20 credit on a partially paid $100 sale remains a liability until allocated;
    # the source-sale receivable stays $50 rather than being written off by the return.
    assert sale_settlement_totals("100", "20", "50", "0", "20", "0") == (Decimal("50.0000"), Decimal("50.0000"))


def test_sale_settlement_totals_reduces_due_only_when_credit_is_applied_to_this_sale():
    from decimal import Decimal
    from app.commerce_rules import sale_settlement_totals

    assert sale_settlement_totals("100", "20", "50", "0", "20", "20") == (Decimal("50.0000"), Decimal("30.0000"))


def test_sale_settlement_totals_reduces_due_for_unsettled_no_cash_return():
    from decimal import Decimal
    from app.commerce_rules import sale_settlement_totals

    assert sale_settlement_totals("100", "20", "50", "0") == (Decimal("50.0000"), Decimal("30.0000"))


@pytest.mark.parametrize(
    ("return_qty", "orig_qty", "discount", "tax", "total", "expected"),
    [
        ("1", "2", "10", "18", "108", ("54.0000", "5.0000", "9.0000")),
        ("2", "2", "10", "18", "108", ("108.0000", "10.0000", "18.0000")),
        ("0.5", "2", "2", "3", "23", ("5.7500", "0.5000", "0.7500")),
    ],
)
def test_partial_return_prorates_discount_tax_and_total(
    return_qty, orig_qty, discount, tax, total, expected
):
    from app.commerce_rules import prorate_return_line_amounts

    result = prorate_return_line_amounts(return_qty, orig_qty, discount, tax, total)
    assert tuple(map(str, result)) == expected


@pytest.mark.parametrize(("return_qty", "orig_qty"), [("0", "2"), ("1", "0"), ("3", "2")])
def test_partial_return_proration_rejects_invalid_quantities(return_qty, orig_qty):
    from app.commerce_rules import prorate_return_line_amounts

    with pytest.raises(ValueError):
        prorate_return_line_amounts(return_qty, orig_qty, "0", "0", "10")


def test_return_inventory_cost_uses_original_sale_cost_basis():
    from app.commerce_rules import original_sale_inventory_unit_cost

    # Original sale cost is 12 per unit; current stock average could be 15.
    # The return must reverse COGS at the original 12, not current average 15.
    assert original_sale_inventory_unit_cost("60", "5") == Decimal("12.0000")


@pytest.mark.parametrize(("total_cost", "sold_quantity"), [("-1", "2"), ("10", "0"), ("10", "-2")])
def test_return_inventory_cost_rejects_invalid_source_ledger(total_cost, sold_quantity):
    from app.commerce_rules import original_sale_inventory_unit_cost

    with pytest.raises(ValueError, match="valid"):
        original_sale_inventory_unit_cost(total_cost, sold_quantity)


def test_return_line_ids_must_be_unique_within_one_return():
    from uuid import uuid4
    from app.commerce_rules import ensure_unique_return_line_ids

    first, second = uuid4(), uuid4()
    ensure_unique_return_line_ids([first, second])
    with pytest.raises(ValueError, match="combine quantities"):
        ensure_unique_return_line_ids([first, second, first])


@pytest.mark.parametrize(
    ("gross", "discount", "rate", "inclusive", "expected_tax", "expected_total"),
    [
        ("118", "0", "18", True, "18.0000", "118.0000"),
        ("100", "0", "18", False, "18.0000", "118.0000"),
        ("100", "10", "18", False, "16.2000", "106.2000"),
        ("100", "10", "18", True, "13.7288", "90.0000"),
        ("100", "0", "0", False, "0.0000", "100.0000"),
    ],
)
def test_effective_tax_math_handles_inclusive_exclusive_discount_and_zero(
    gross, discount, rate, inclusive, expected_tax, expected_total
):
    from app.commerce_rules import calculate_line_tax

    tax, total = calculate_line_tax(gross, discount, rate, inclusive=inclusive)
    assert str(tax) == expected_tax
    assert str(total) == expected_total


def test_effective_tax_math_rejects_bad_discount_and_tax_rate():
    from app.commerce_rules import calculate_line_tax

    with pytest.raises(ValueError, match="discount"):
        calculate_line_tax("10", "11", "18")
    with pytest.raises(ValueError, match="Tax rate"):
        calculate_line_tax("10", "0", "101")
