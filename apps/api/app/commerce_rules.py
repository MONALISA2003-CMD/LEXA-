"""Pure financial rules shared by commerce handlers and unit tests."""

from collections.abc import Iterable
from typing import Hashable
from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANTUM = Decimal("0.0001")
ZERO_MONEY = Decimal("0.0000")


def money(value: Decimal | int | str) -> Decimal:
    """Normalize an amount using the API's four-decimal money precision."""
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def ensure_unique_return_line_ids(sale_line_ids: Iterable[Hashable]) -> None:
    """Reject repeated source-line IDs in a single return request.

    Duplicate IDs would validate each quantity independently against the same
    available quantity and could over-return both inventory and financial value.
    """
    line_ids = list(sale_line_ids)
    if len(line_ids) != len(set(line_ids)):
        raise ValueError("Each sale line may appear only once per return; combine quantities for the same line")


def original_sale_inventory_unit_cost(total_cost: Decimal | int | str, sold_quantity: Decimal | int | str) -> Decimal:
    """Derive the original inventory cost/unit from immutable sale movements.

    Return COGS must use the sale-time cost basis, not the current inventory
    average cost, which may have changed after the sale.
    """
    cost = money(total_cost)
    quantity = Decimal(str(sold_quantity))
    if cost < ZERO_MONEY or quantity <= 0:
        raise ValueError("Original inventory cost and sold quantity must be valid")
    return money(cost / quantity)


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


def sale_settlement_totals(
    total: Decimal | int | str,
    returned_value: Decimal | int | str,
    gross_collected: Decimal | int | str,
    recorded_refunds: Decimal | int | str,
    customer_credit_issued: Decimal | int | str = 0,
    customer_credit_applied_to_sale: Decimal | int | str = 0,
) -> tuple[Decimal, Decimal]:
    """Calculate cash collections and current due from immutable ledgers.

    Customer credits are a separate liability. A source-sale credit that remains
    unallocated preserves that sale's outstanding receivable; a recorded credit
    allocation to this sale's receivable pays it down. Credits applied to another
    sale do not change the source sale's receivable.
    """
    sale_total = money(total)
    returned = money(returned_value)
    collected = money(gross_collected)
    refunded = money(recorded_refunds)
    credit_issued = money(customer_credit_issued)
    credit_applied = money(customer_credit_applied_to_sale)
    if min(sale_total, returned, collected, refunded, credit_issued, credit_applied) < ZERO_MONEY:
        raise ValueError("Sale, return, collection, refund, and credit amounts cannot be negative")
    if returned > sale_total:
        raise ValueError("Returned value cannot exceed the sale total")
    net_collected = min(sale_total, max(ZERO_MONEY, money(collected - refunded)))
    amount_due = max(
        ZERO_MONEY,
        money(sale_total - returned - net_collected + credit_issued - credit_applied),
    )
    return money(net_collected), money(amount_due)


def prorate_return_line_amounts(
    return_quantity: Decimal | int | str,
    original_quantity: Decimal | int | str,
    discount_amount: Decimal | int | str,
    tax_amount: Decimal | int | str,
    line_total: Decimal | int | str,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (line_total, discount, tax) proportionally for a partial return.

    The returned line stores its own discounted/taxed amounts. Copying the full
    source-line discount and tax to a partial return overstates both the credit
    note and the tax reversal. Four-decimal rounding matches commerce money.
    """
    qty = Decimal(str(return_quantity))
    original_qty = Decimal(str(original_quantity))
    if qty <= 0 or original_qty <= 0:
        raise ValueError("Return and original quantities must be positive")
    if qty > original_qty:
        raise ValueError("Return quantity cannot exceed the original quantity")
    discount = money(discount_amount)
    tax = money(tax_amount)
    total = money(line_total)
    if min(discount, tax, total) < ZERO_MONEY:
        raise ValueError("Line money amounts cannot be negative")
    ratio = qty / original_qty
    return money(total * ratio), money(discount * ratio), money(tax * ratio)
