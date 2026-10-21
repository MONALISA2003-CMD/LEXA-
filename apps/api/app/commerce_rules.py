"""Pure financial rules shared by commerce handlers and unit tests."""

from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANTUM = Decimal("0.0001")
ZERO_MONEY = Decimal("0.0000")


def money(value: Decimal | int | str) -> Decimal:
    """Normalize an amount using the API's four-decimal money precision."""
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def remaining_refund_balance(amount_collected: Decimal | int | str, prior_refunds: Decimal | int | str) -> Decimal:
    """Return the non-negative amount still refundable from recorded collections.

    ``prior_refunds`` must include all recorded refunds on the source sale, not
    just the current return. Callers should lock the source sale row before
    calculating this value so concurrent returns serialize on the same sale.
    """
    collected = money(amount_collected)
    refunded = money(prior_refunds)
    if collected < ZERO_MONEY or refunded < ZERO_MONEY:
        raise ValueError("Collected and refunded amounts cannot be negative")
    return max(ZERO_MONEY, money(collected - refunded))
