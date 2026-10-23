from datetime import date, timedelta
from decimal import Decimal

from app.business_insights import (
    build_margin_insight,
    build_sales_movement_insight,
    build_stock_risk_insight,
)

START = date(2026, 10, 1)
END = date(2026, 10, 23)
PREVIOUS_END = START - timedelta(days=1)
PREVIOUS_START = PREVIOUS_END - timedelta(days=(END - START).days)


def daily(*, rows: int, net_sales: str, refreshed_at="2026-10-23T08:00:00+00:00"):
    return {
        "record_count": rows,
        "latest_business_date": END,
        "refreshed_at": refreshed_at,
        "net_sales": Decimal(net_sales),
    }


def products(*, rows: int, net_sales: str, cogs: str, gross_margin: str, refreshed_at="2026-10-23T08:00:00+00:00"):
    return {
        "record_count": rows,
        "latest_business_date": END,
        "refreshed_at": refreshed_at,
        "net_sales": Decimal(net_sales),
        "cogs": Decimal(cogs),
        "gross_margin": Decimal(gross_margin),
    }


def sales(**kwargs):
    return build_sales_movement_insight(
        current=kwargs.pop("current", daily(rows=1, net_sales="900")),
        previous=kwargs.pop("previous", daily(rows=1, net_sales="1000")),
        start_date=START,
        end_date=END,
        previous_start_date=PREVIOUS_START,
        previous_end_date=PREVIOUS_END,
        currency_code="UGX",
        fresh=kwargs.pop("fresh", True),
    )


def margin(**kwargs):
    return build_margin_insight(
        current=kwargs.pop("current", products(rows=2, net_sales="1000", cogs="600", gross_margin="400")),
        previous=kwargs.pop("previous", products(rows=2, net_sales="1000", cogs="550", gross_margin="450")),
        start_date=START,
        end_date=END,
        previous_start_date=PREVIOUS_START,
        previous_end_date=PREVIOUS_END,
        currency_code="UGX",
        fresh=kwargs.pop("fresh", True),
    )


def test_sales_insight_does_not_infer_zero_when_no_saved_rows_exist():
    result = sales(current=daily(rows=0, net_sales="0"))
    assert result["status"] == "unavailable"
    assert result["metric"] is None
    assert "has not assumed that sales were zero" in result["summary"]
    assert result["source"]["record_count"] == 0


def test_sales_drop_is_compared_with_equal_length_previous_period():
    result = sales(current=daily(rows=1, net_sales="850"), previous=daily(rows=1, net_sales="1000"))
    assert result["status"] == "available"
    assert result["severity"] == "attention"
    assert result["comparison"]["change_percent"] == "-15.00"
    assert result["comparison"]["from_date"] == PREVIOUS_START.isoformat()


def test_sales_does_not_publish_percentage_change_for_zero_previous_baseline():
    result = sales(current=daily(rows=1, net_sales="400"), previous=daily(rows=1, net_sales="0"))
    assert result["status"] == "partial"
    assert result["comparison"]["change_percent"] is None
    assert "percentage change is not meaningful" in result["summary"]


def test_sales_projection_stale_state_suppresses_untrustworthy_metric():
    result = sales(fresh=False)
    assert result["status"] == "stale"
    assert result["metric"] is None
    assert "Refresh the reports" in result["summary"]


def test_margin_rate_uses_percentage_points_not_relative_percent_change():
    result = margin(
        current=products(rows=3, net_sales="1000", cogs="650", gross_margin="350"),
        previous=products(rows=3, net_sales="1000", cogs="550", gross_margin="450"),
    )
    assert result["status"] == "available"
    assert result["severity"] == "attention"
    assert result["metric"]["value"] == "35.00"
    assert result["comparison"]["change_value"] == "-10.00"
    assert result["comparison"]["unit"] == "percentage_points"
    assert "not net profit" in result["methodology"]


def test_margin_is_unavailable_without_positive_net_sales_rows():
    result = margin(current=products(rows=0, net_sales="0", cogs="0", gross_margin="0"))
    assert result["status"] == "unavailable"
    assert result["metric"] is None
    assert "not substituted zero" in result["summary"]


def test_stock_insight_marks_missing_snapshot_unavailable_not_zero():
    result = build_stock_risk_insight(snapshot_date=None, as_of_date=END, stock_summary=None)
    assert result["status"] == "unavailable"
    assert result["metric"] is None
    assert "no saved inventory-health snapshot" in result["summary"]


def test_stock_insight_suppresses_old_snapshot_metrics():
    snapshot = date(2026, 10, 18)
    result = build_stock_risk_insight(
        snapshot_date=snapshot,
        as_of_date=END,
        stock_summary={"record_count": 10, "out_of_stock_count": 2, "low_cover_count": 3, "slow_moving_count": 4, "items_needing_review": 6},
        examples=[{"product_name": "Example"}],
    )
    assert result["status"] == "stale"
    assert result["metric"] is None
    assert result.get("examples") is None
    assert "will not present those counts as current stock advice" in result["summary"]


def test_stock_insight_explains_review_counts_and_keeps_examples_bounded():
    result = build_stock_risk_insight(
        snapshot_date=END,
        as_of_date=END,
        stock_summary={"record_count": 20, "out_of_stock_count": 2, "low_cover_count": 3, "slow_moving_count": 4, "items_needing_review": 6},
        examples=[{"product_name": f"Item {i}"} for i in range(8)],
    )
    assert result["status"] == "available"
    assert result["severity"] == "critical"
    assert result["metric"]["value"] == "6"
    assert len(result["examples"]) == 5
    assert "Counts can overlap" in result["summary"]


def test_stock_snapshot_with_no_flags_is_a_no_finding_not_missing_data():
    result = build_stock_risk_insight(
        snapshot_date=END,
        as_of_date=END,
        stock_summary={"record_count": 20, "out_of_stock_count": 0, "low_cover_count": 0, "slow_moving_count": 0, "items_needing_review": 0},
    )
    assert result["status"] == "no_finding"
    assert result["metric"]["value"] == "0"
    assert "No stockout" in result["summary"]


def balance_insight(*, receivables=None, supplier_ledger=None):
    from app.business_insights import build_balance_insight

    return build_balance_insight(
        receivables=receivables or {
            "record_count": 4,
            "open_count": 2,
            "open_customer_count": 2,
            "open_balance": Decimal("1200"),
            "overdue_count": 1,
            "overdue_balance": Decimal("300"),
        },
        supplier_ledger=supplier_ledger or {
            "record_count": 6,
            "supplier_count": 3,
            "net_balance": Decimal("500"),
        },
        as_of_date=END,
        currency_code="UGX",
    )


def test_balance_insight_keeps_customer_receivables_and_supplier_payables_separate():
    result = balance_insight()
    assert result["status"] == "available"
    assert result["severity"] == "attention"
    assert result["metric"]["value"] == "1200.0000"
    assert result["metric"]["currency_code"] == "UGX"
    assert result["details"]["overdue_receivables"] == "300.0000"
    assert result["details"]["supplier_payables"] == "500.0000"
    assert result["details"]["supplier_credit"] == "0.0000"
    assert result["source"]["record_count"] == 10
    assert {link["href"] for link in result["evidence_links"]} == {"/purchasing"}


def test_balance_insight_does_not_claim_zero_when_both_source_ledgers_are_missing():
    result = balance_insight(
        receivables={"record_count": 0, "open_balance": Decimal("0"), "overdue_balance": Decimal("0")},
        supplier_ledger={"record_count": 0, "net_balance": Decimal("0")},
    )
    assert result["status"] == "unavailable"
    assert result["metric"] is None
    assert "does not assume the balance is zero" in result["limitations"][-1]


def test_balance_insight_shows_supplier_credit_separately_from_payables():
    result = balance_insight(
        receivables={"record_count": 1, "open_balance": Decimal("0"), "overdue_balance": Decimal("0")},
        supplier_ledger={"record_count": 2, "supplier_count": 1, "net_balance": Decimal("-75")},
    )
    assert result["details"]["supplier_payables"] == "0.0000"
    assert result["details"]["supplier_credit"] == "75.0000"
    assert result["status"] == "available"
    assert "supplier credit" in result["summary"]


def test_balance_insight_returns_no_finding_only_when_sources_exist_and_net_is_zero():
    result = balance_insight(
        receivables={"record_count": 3, "open_balance": Decimal("0"), "overdue_balance": Decimal("0")},
        supplier_ledger={"record_count": 4, "supplier_count": 2, "net_balance": Decimal("0")},
    )
    assert result["status"] == "no_finding"
    assert result["metric"]["value"] == "0.0000"
    assert "source rows were present" in result["summary"]
