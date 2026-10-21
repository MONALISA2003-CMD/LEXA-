from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.inventory_intelligence import build_replenishment_metrics


def test_replenishment_formula_accounts_for_returns_inbound_and_reserved_stock():
    result = build_replenishment_metrics(
        on_hand="24", reserved="4", inbound="5", units_sold="60", units_returned="6",
        lookback_days=30, lead_time_days=5, review_period_days=7,
        safety_stock="3", minimum_available="8",
    )
    assert result["available"] == Decimal("20.000000")
    assert result["net_units_demand"] == Decimal("54.000000")
    assert result["average_daily_demand"] == Decimal("1.800000")
    assert result["target_stock"] == Decimal("24.600000")
    assert result["reorder_quantity"] == Decimal("0.000000")
    assert result["recommended_action"] == "STOCK_COVERED"


def test_replenishment_recommends_only_target_shortfall_after_inbound():
    result = build_replenishment_metrics(
        on_hand=5, reserved=1, inbound=2, units_sold=60, units_returned=0,
        lookback_days=30, lead_time_days=10, review_period_days=5,
        safety_stock=4, minimum_available=0,
    )
    assert result["available"] == Decimal("4.000000")
    assert result["target_stock"] == Decimal("34.000000")
    assert result["reorder_quantity"] == Decimal("28.000000")
    assert result["recommended_action"] == "REORDER"
    assert result["reason_code"] == "BELOW_TARGET_STOCK"


def test_returns_cannot_create_negative_demand_and_zero_sales_does_not_divide_by_zero():
    result = build_replenishment_metrics(
        on_hand=0, reserved=0, inbound=0, units_sold=2, units_returned=5,
        lookback_days=30, lead_time_days=7, review_period_days=7,
        safety_stock=0, minimum_available=0,
    )
    assert result["net_units_demand"] == Decimal("0.000000")
    assert result["average_daily_demand"] == Decimal("0.000000")
    assert result["days_cover"] is None
    assert result["reorder_quantity"] == Decimal("0.000000")
    assert result["reason_code"] == "NO_NET_DEMAND_IN_LOOKBACK"


def test_reserved_greater_than_on_hand_fails_closed_instead_of_hiding_data_defect():
    with pytest.raises(ValueError, match="reserved quantity cannot exceed on-hand"):
        build_replenishment_metrics(
            on_hand=1, reserved=2, inbound=0, units_sold=0, units_returned=0,
            lookback_days=30, lead_time_days=7, review_period_days=7,
            safety_stock=0, minimum_available=0,
        )


def test_invalid_policy_ranges_and_negative_inputs_are_rejected():
    with pytest.raises(ValueError, match="lookback_days"):
        build_replenishment_metrics(
            on_hand=0, reserved=0, inbound=0, units_sold=0, units_returned=0,
            lookback_days=3, lead_time_days=7, review_period_days=7,
            safety_stock=0, minimum_available=0,
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        build_replenishment_metrics(
            on_hand=-1, reserved=0, inbound=0, units_sold=0, units_returned=0,
            lookback_days=30, lead_time_days=7, review_period_days=7,
            safety_stock=0, minimum_available=0,
        )


def test_phase6_policy_api_and_database_security_contracts_are_present():
    root = Path(__file__).resolve().parents[3]
    route = (root / "apps/api/app/routes/inventory.py").read_text(encoding="utf-8")
    migration = (root / "migrations/036_phase6_inventory_intelligence.sql").read_text(encoding="utf-8")
    assert '@router.get("/replenishment/recommendations")' in route
    assert '@router.get("/replenishment/policies")' in route
    assert '@router.put("/replenishment/policies")' in route
    assert 'require_permission("inventory.manage")' in route
    assert "bt.transaction_type='SALE'" in route
    assert "sr.status='COMPLETED'" in route
    assert "COALESCE(sr.inventory_location_id, source_sale.location_id)=p.location_id" in route
    assert "inventory_replenishment_policies_tenant_isolation" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "ON CONFLICT (tenant_id, location_id, variant_id) DO UPDATE" in route
    assert "advisory_only" in route
