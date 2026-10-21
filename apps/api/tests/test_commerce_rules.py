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
