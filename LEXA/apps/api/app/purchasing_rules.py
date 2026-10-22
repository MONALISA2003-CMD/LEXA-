"""Pure rules for Phase 7 purchasing, landed-cost allocation and supplier balances."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

CENT = Decimal("0.01")
QTY_SCALE = Decimal("0.000001")
ZERO = Decimal("0")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def quantity(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(QTY_SCALE, rounding=ROUND_HALF_UP)


def line_amounts(qty: Decimal, unit_cost: Decimal, tax_rate: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    if qty <= ZERO or unit_cost <= ZERO or tax_rate < ZERO or tax_rate > Decimal("100"):
        raise ValueError("Quantity and unit cost must be positive; tax rate must be from 0 to 100")
    subtotal = money(qty * unit_cost)
    tax = money(subtotal * tax_rate / Decimal("100"))
    return subtotal, tax, money(subtotal + tax)


def allocate_landed_cost(
    total: Decimal | int | str,
    lines: Iterable[dict],
    method: str,
) -> list[dict]:
    """Allocate a positive cost exactly to receipt lines, leaving any rounding penny deterministic.

    Each line needs id, quantity and base_unit_cost. BY_VALUE weights the merchandise
    extended cost; BY_QUANTITY weights received quantities; EQUALLY gives each line
    the same share. The final line receives the rounding residual so allocation sums
    exactly to the entered landed cost.
    """
    amount = money(total)
    source = list(lines)
    if amount <= ZERO or not source:
        raise ValueError("Landed cost and receipt lines must be present and positive")
    if method not in {"BY_VALUE", "BY_QUANTITY", "EQUALLY"}:
        raise ValueError("Unsupported landed-cost allocation method")
    weights: list[Decimal] = []
    for line in source:
        qty = Decimal(str(line["quantity"]))
        cost = Decimal(str(line["base_unit_cost"]))
        if qty <= ZERO or cost <= ZERO:
            raise ValueError("Receipt line quantity and base cost must be positive")
        weights.append(cost * qty if method == "BY_VALUE" else qty if method == "BY_QUANTITY" else Decimal("1"))
    total_weight = sum(weights, ZERO)
    if total_weight <= ZERO:
        raise ValueError("Allocation basis must be positive")
    allocated: list[dict] = []
    running = ZERO
    for index, line in enumerate(source):
        share = money(amount - running) if index == len(source) - 1 else money(amount * weights[index] / total_weight)
        running += share
        qty = Decimal(str(line["quantity"]))
        allocated.append({"receipt_line_id": line["id"], "allocated_amount": share, "allocated_per_unit": quantity(share / qty)})
    if sum((x["allocated_amount"] for x in allocated), ZERO) != amount:
        raise AssertionError("Landed cost allocation lost currency precision")
    return allocated


def order_status_from_receipts(lines: Iterable[dict]) -> str:
    rows = list(lines)
    if not rows:
        raise ValueError("A purchase order must have at least one line")
    complete = all(Decimal(str(line["received_quantity"])) >= Decimal(str(line["ordered_quantity"])) for line in rows)
    any_received = any(Decimal(str(line["received_quantity"])) > ZERO for line in rows)
    return "FULLY_RECEIVED" if complete else "PARTIALLY_RECEIVED" if any_received else "OPEN"


def supplier_balance(debits: Iterable[Decimal], credits: Iterable[Decimal]) -> dict[str, Decimal]:
    payable = money(sum((Decimal(str(x)) for x in debits), ZERO) - sum((Decimal(str(x)) for x in credits), ZERO))
    return {"net_balance": payable, "payable": max(payable, ZERO), "supplier_credit": max(-payable, ZERO)}


def assert_transition(current: str, target: str, allowed: dict[str, set[str]]) -> None:
    if target not in allowed.get(current, set()):
        raise ValueError(f"Invalid purchasing transition: {current} -> {target}")


def validate_payment_allocations(amount: Decimal | int | str, allocations: Iterable[dict]) -> Decimal:
    """Validate supplier payment allocations before any database mutation.

    The same bill must not be listed twice, because the database deliberately
    enforces one allocation row per payment/bill pair. Total allocations may be
    lower than the payment (supplier advance), but never greater.
    """
    payment_amount = money(Decimal(str(amount)))
    rows = list(allocations)
    bill_ids = [str(row["bill_id"]) for row in rows]
    if len(bill_ids) != len(set(bill_ids)):
        raise ValueError("A supplier payment may allocate to each bill only once")
    total = sum((money(Decimal(str(row["amount"]))) for row in rows), ZERO)
    if total > payment_amount:
        raise ValueError("Allocated amount cannot exceed payment amount")
    return total
