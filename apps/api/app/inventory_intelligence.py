"""Pure, deterministic Phase 6 inventory recommendation calculations.

This module deliberately recommends only; it never creates inventory, purchase orders,
transfers, or financial entries.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

ZERO = Decimal("0")
SIX = Decimal("0.000001")


def _decimal(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def build_replenishment_metrics(
    *,
    on_hand: Any,
    reserved: Any,
    inbound: Any,
    units_sold: Any,
    units_returned: Any,
    lookback_days: int,
    lead_time_days: int,
    review_period_days: int,
    safety_stock: Any,
    minimum_available: Any,
) -> dict[str, Any]:
    """Calculate an explainable replenishment target with explicit non-negative quantities."""
    if lookback_days < 7 or lookback_days > 365:
        raise ValueError("lookback_days must be between 7 and 365")
    if lead_time_days < 0 or lead_time_days > 365:
        raise ValueError("lead_time_days must be between 0 and 365")
    if review_period_days < 1 or review_period_days > 90:
        raise ValueError("review_period_days must be between 1 and 90")

    on_hand_d = _decimal(on_hand)
    reserved_d = _decimal(reserved)
    inbound_d = _decimal(inbound)
    sold_d = _decimal(units_sold)
    returned_d = _decimal(units_returned)
    safety_d = _decimal(safety_stock)
    minimum_d = _decimal(minimum_available)

    if min(on_hand_d, reserved_d, inbound_d, sold_d, returned_d, safety_d, minimum_d) < ZERO:
        raise ValueError("inventory, demand and policy quantities cannot be negative")
    if reserved_d > on_hand_d:
        # Reservations over physical stock are a consistency defect, not a valid reorder input.
        raise ValueError("reserved quantity cannot exceed on-hand quantity")

    net_demand = max(sold_d - returned_d, ZERO)
    daily_demand = (net_demand / Decimal(lookback_days)).quantize(SIX, rounding=ROUND_HALF_UP)
    available = on_hand_d - reserved_d
    target = max(minimum_d, safety_d + daily_demand * Decimal(lead_time_days + review_period_days))
    reorder = max(target - available - inbound_d, ZERO).quantize(SIX, rounding=ROUND_HALF_UP)
    days_cover = None if daily_demand <= ZERO else (available / daily_demand).quantize(SIX, rounding=ROUND_HALF_UP)

    if available <= minimum_d and reorder > ZERO:
        reason = "AT_OR_BELOW_MINIMUM_AVAILABLE"
    elif reorder > ZERO:
        reason = "BELOW_TARGET_STOCK"
    elif daily_demand == ZERO:
        reason = "NO_NET_DEMAND_IN_LOOKBACK"
    else:
        reason = "TARGET_STOCK_COVERED"

    return {
        "on_hand": on_hand_d.quantize(SIX),
        "reserved": reserved_d.quantize(SIX),
        "available": available.quantize(SIX),
        "inbound": inbound_d.quantize(SIX),
        "units_sold": sold_d.quantize(SIX),
        "units_returned": returned_d.quantize(SIX),
        "net_units_demand": net_demand.quantize(SIX),
        "lookback_days": lookback_days,
        "average_daily_demand": daily_demand,
        "days_cover": days_cover,
        "target_stock": target.quantize(SIX),
        "reorder_quantity": reorder,
        "recommended_action": "REORDER" if reorder > ZERO else "MONITOR" if daily_demand == ZERO else "STOCK_COVERED",
        "reason_code": reason,
    }
