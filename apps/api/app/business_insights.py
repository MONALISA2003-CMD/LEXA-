"""Explainable, read-only Phase 9 insight rules.

These helpers consume canonical analytics projections. They do not query arbitrary
SQL, call external AI providers, or mutate business records.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

ZERO = Decimal("0")
FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")


def _decimal(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _text_decimal(value: Any, *, places: Decimal = FOUR_PLACES) -> str:
    return str(_decimal(value).quantize(places, rounding=ROUND_HALF_UP))


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _base(
    *,
    insight_id: str,
    title: str,
    status: str,
    severity: str,
    summary: str,
    start_date: date,
    end_date: date,
    methodology: str,
    tables: Sequence[str],
    record_count: int,
    as_of_date: Any = None,
    refreshed_at: Any = None,
    evidence_label: str,
    evidence_href: str,
    limitations: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "id": insight_id,
        "title": title,
        "status": status,
        "severity": severity,
        "summary": summary,
        "period": {"from_date": start_date.isoformat(), "to_date": end_date.isoformat()},
        "metric": None,
        "comparison": None,
        "methodology": methodology,
        "source": {
            "tables": list(tables),
            "record_count": max(0, int(record_count or 0)),
            "as_of_date": _iso(as_of_date),
            "refreshed_at": _iso(refreshed_at),
        },
        "evidence": {"label": evidence_label, "href": evidence_href},
        "limitations": list(limitations),
    }


def build_sales_movement_insight(
    *,
    current: Mapping[str, Any],
    previous: Mapping[str, Any],
    start_date: date,
    end_date: date,
    previous_start_date: date,
    previous_end_date: date,
    currency_code: str,
    fresh: bool,
) -> dict[str, Any]:
    row_count = int(current.get("record_count") or 0)
    item = _base(
        insight_id="sales-movement",
        title="Sales movement",
        status="available",
        severity="neutral",
        summary="",
        start_date=start_date,
        end_date=end_date,
        methodology="Net sales are summed from saved daily metrics for the selected dates and currency, then compared with the immediately preceding period of equal length.",
        tables=("analytics_daily_business_metrics",),
        record_count=row_count,
        as_of_date=current.get("latest_business_date"),
        refreshed_at=current.get("refreshed_at"),
        evidence_label="Open sales reports",
        evidence_href="/reports",
        limitations=("Daily projections include dates with recorded activity; a missing projection is not treated as zero sales.",),
    )
    if row_count <= 0:
        item.update(status="unavailable", severity="unknown", summary="No saved sales metrics were found for this period and currency. LEXA has not assumed that sales were zero.")
        return item
    if not fresh:
        item.update(status="stale", severity="unknown", summary="Saved sales metrics exist, but the analytics refresh is not recent enough to support a current comparison. Refresh the reports before acting on this insight.")
        return item

    current_net = _decimal(current.get("net_sales"))
    previous_count = int(previous.get("record_count") or 0)
    item["metric"] = {"label": "Net sales", "value": _text_decimal(current_net), "unit": "money", "currency_code": currency_code}
    if previous_count <= 0:
        item.update(status="partial", severity="informational", summary=f"Net sales for the selected period are {currency_code} {_text_decimal(current_net)}. The preceding period has no saved comparison rows, so a movement rate is unavailable.")
        item["limitations"].append("The comparison period has no saved daily metric rows.")
        return item

    previous_net = _decimal(previous.get("net_sales"))
    change = current_net - previous_net
    item["comparison"] = {
        "label": "Previous period",
        "from_date": previous_start_date.isoformat(),
        "to_date": previous_end_date.isoformat(),
        "previous_value": _text_decimal(previous_net),
        "change_value": _text_decimal(change),
        "change_percent": None,
        "unit": "money",
    }
    if previous_net <= ZERO:
        item.update(status="partial", severity="informational", summary=f"Net sales are {currency_code} {_text_decimal(current_net)} for this period, compared with {currency_code} {_text_decimal(previous_net)} previously. A percentage change is not meaningful because the previous baseline was not positive.")
        item["limitations"].append("Percentage movement is omitted when the previous period has no positive net-sales baseline.")
        return item

    change_percent = (change / previous_net * Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    item["comparison"]["change_percent"] = _text_decimal(change_percent, places=TWO_PLACES)
    if change_percent <= Decimal("-10"):
        item.update(status="available", severity="attention", summary=f"Net sales are down {abs(change_percent):.2f}% against the preceding equal-length period. Review the daily report and check whether returns, lower volume or missing records explain the change.")
    elif change_percent >= Decimal("10"):
        item.update(status="available", severity="positive", summary=f"Net sales are up {change_percent:.2f}% against the preceding equal-length period. Compare the daily totals to understand which days contributed to the change.")
    else:
        item.update(status="available", severity="informational", summary=f"Net sales changed by {change_percent:+.2f}% against the preceding equal-length period. This rule flags changes of 10% or more for review; it does not explain causation by itself.")
    return item


def build_margin_insight(
    *,
    current: Mapping[str, Any],
    previous: Mapping[str, Any],
    start_date: date,
    end_date: date,
    previous_start_date: date,
    previous_end_date: date,
    currency_code: str,
    fresh: bool,
) -> dict[str, Any]:
    row_count = int(current.get("record_count") or 0)
    item = _base(
        insight_id="gross-margin-movement",
        title="Gross-margin movement",
        status="unavailable",
        severity="unknown",
        summary="Gross-margin movement cannot be calculated from the saved product metrics for this period.",
        start_date=start_date,
        end_date=end_date,
        methodology="Gross margin = net sales − COGS. Gross-margin rate = summed gross margin ÷ summed net sales × 100. This is not net profit.",
        tables=("analytics_product_daily_metrics",),
        record_count=row_count,
        as_of_date=current.get("latest_business_date"),
        refreshed_at=current.get("refreshed_at"),
        evidence_label="Review product performance",
        evidence_href="/reports",
        limitations=("Gross margin depends on the recorded cost of goods sold; it excludes operating expenses and must not be labelled net profit.",),
    )
    current_sales = _decimal(current.get("net_sales"))
    if row_count <= 0 or current_sales <= ZERO:
        item["summary"] = "There are not enough saved product sales rows with positive net sales to calculate a meaningful gross-margin rate. LEXA has not substituted zero."
        return item
    if not fresh:
        item.update(status="stale", severity="unknown", summary="Saved product metrics exist, but the analytics refresh is not recent enough to assess current gross-margin movement. Refresh reports before acting on this insight.")
        return item

    current_margin = _decimal(current.get("gross_margin"))
    current_cogs = _decimal(current.get("cogs"))
    current_rate = (current_margin / current_sales * Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    item["metric"] = {"label": "Gross-margin rate", "value": _text_decimal(current_rate, places=TWO_PLACES), "unit": "percent", "currency_code": currency_code}
    item["details"] = {"net_sales": _text_decimal(current_sales), "cogs": _text_decimal(current_cogs), "gross_margin": _text_decimal(current_margin)}

    previous_count = int(previous.get("record_count") or 0)
    previous_sales = _decimal(previous.get("net_sales"))
    if previous_count <= 0 or previous_sales <= ZERO:
        item.update(status="partial", severity="informational", summary=f"Gross margin is {currency_code} {_text_decimal(current_margin)} ({current_rate:.2f}% of net sales) for this period. A comparable prior-period rate is unavailable.")
        item["limitations"].append("The preceding period has no comparable positive-net-sales product metrics.")
        return item

    previous_margin = _decimal(previous.get("gross_margin"))
    previous_rate = (previous_margin / previous_sales * Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    change_pp = (current_rate - previous_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    item["comparison"] = {
        "label": "Previous-period gross-margin rate",
        "from_date": previous_start_date.isoformat(),
        "to_date": previous_end_date.isoformat(),
        "previous_value": _text_decimal(previous_rate, places=TWO_PLACES),
        "change_value": _text_decimal(change_pp, places=TWO_PLACES),
        "change_percent": None,
        "unit": "percentage_points",
    }
    if change_pp <= Decimal("-3"):
        item.update(status="available", severity="attention", summary=f"Gross-margin rate fell {abs(change_pp):.2f} percentage points against the preceding equal-length period. Review discounting, returns and the recorded cost of goods sold before drawing a conclusion.")
    elif change_pp >= Decimal("3"):
        item.update(status="available", severity="positive", summary=f"Gross-margin rate rose {change_pp:.2f} percentage points against the preceding equal-length period. Check the source products and cost records to understand the movement.")
    else:
        item.update(status="available", severity="informational", summary=f"Gross-margin rate changed by {change_pp:+.2f} percentage points. This rule flags changes of 3 percentage points or more; it does not claim to identify the cause.")
    return item


def build_balance_insight(
    *,
    receivables: Mapping[str, Any],
    supplier_ledger: Mapping[str, Any],
    as_of_date: date,
    currency_code: str,
) -> dict[str, Any]:
    receivable_rows = int(receivables.get("record_count") or 0)
    ledger_rows = int(supplier_ledger.get("record_count") or 0)
    receivable_balance = _decimal(receivables.get("open_balance"))
    overdue_balance = _decimal(receivables.get("overdue_balance"))
    supplier_net = _decimal(supplier_ledger.get("net_balance"))
    supplier_payable = max(supplier_net, ZERO)
    supplier_credit = max(-supplier_net, ZERO)
    item = _base(
        insight_id="working-capital-balances",
        title="Customer and supplier balances",
        status="unavailable",
        severity="unknown",
        summary="Current customer and supplier balances are unavailable because no matching receivable or supplier-ledger source rows were found for this currency.",
        start_date=as_of_date,
        end_date=as_of_date,
        methodology="Customer receivables are the saved open/partially-paid receivable balances joined to sales in the selected currency. Supplier balance is the sum of supplier-ledger debits minus credits in that currency. Supplier credits are shown separately; currencies are never added together.",
        tables=("receivables", "sales", "supplier_ledger_entries"),
        record_count=receivable_rows + ledger_rows,
        as_of_date=as_of_date,
        refreshed_at=None,
        evidence_label="Review finance balances",
        evidence_href="/accounting",
        limitations=(
            "These are current balance snapshots, not movements limited to the selected sales reporting dates.",
            "An entered or posted business record is not proof that a customer, bank or supplier has independently confirmed settlement.",
        ),
    )
    if receivable_rows <= 0 and ledger_rows <= 0:
        item["limitations"].append("No matching source records were found for this currency; LEXA does not assume the balance is zero.")
        return item

    item["metric"] = {
        "label": "Open customer receivables",
        "value": _text_decimal(receivable_balance),
        "unit": "money",
        "currency_code": currency_code,
    }
    item["details"] = {
        "customer_receivables": _text_decimal(receivable_balance),
        "overdue_receivables": _text_decimal(overdue_balance),
        "supplier_payables": _text_decimal(supplier_payable),
        "supplier_credit": _text_decimal(supplier_credit),
        "overdue_receivable_count": int(receivables.get("overdue_count") or 0),
        "customers_with_open_balance": int(receivables.get("open_customer_count") or 0),
        "suppliers_with_ledger_entries": int(supplier_ledger.get("supplier_count") or 0),
    }
    item["evidence_links"] = [
        {"label": "Review supplier balances", "href": "/purchasing"},
    ]

    if overdue_balance > ZERO:
        item.update(
            status="available",
            severity="attention",
            summary=f"As of {as_of_date.isoformat()}, {currency_code} {_text_decimal(overdue_balance)} in customer receivables is past due. Open customer receivables total {currency_code} {_text_decimal(receivable_balance)}; supplier payables are {currency_code} {_text_decimal(supplier_payable)} and supplier credits are {currency_code} {_text_decimal(supplier_credit)}.",
        )
    elif receivable_balance > ZERO or supplier_payable > ZERO:
        item.update(
            status="available",
            severity="informational",
            summary=f"As of {as_of_date.isoformat()}, open customer receivables are {currency_code} {_text_decimal(receivable_balance)}, supplier payables are {currency_code} {_text_decimal(supplier_payable)}, and supplier credits are {currency_code} {_text_decimal(supplier_credit)}. Check the source ledgers for due dates and allocation details.",
        )
    elif supplier_credit > ZERO:
        item.update(
            status="available",
            severity="informational",
            summary=f"No open customer receivables or net supplier payable were found in {currency_code}; the supplier ledger instead shows {currency_code} {_text_decimal(supplier_credit)} in supplier credit.",
        )
    else:
        item.update(
            status="no_finding",
            severity="informational",
            summary=f"No open customer receivables or net supplier payables were found in {currency_code} as of {as_of_date.isoformat()}. The source rows were present and reconciled to a zero net balance for these scopes.",
        )
    return item


def build_stock_risk_insight(
    *,
    snapshot_date: date | None,
    as_of_date: date,
    stock_summary: Mapping[str, Any] | None,
    examples: Sequence[Mapping[str, Any]] = (),
    stale_after_days: int = 2,
) -> dict[str, Any]:
    item = _base(
        insight_id="stock-risk",
        title="Stock needing attention",
        status="unavailable",
        severity="unknown",
        summary="Current stock-risk information is unavailable because no saved inventory-health snapshot was found.",
        start_date=as_of_date,
        end_date=as_of_date,
        methodology="Flags available quantity at or below zero, stock cover of seven days or less, or on-hand stock with no recorded sales in the last 30 days. These are review prompts, not purchase orders.",
        tables=("analytics_inventory_health_metrics", "inventory_balances", "inventory_transactions"),
        record_count=int((stock_summary or {}).get("record_count") or 0),
        as_of_date=snapshot_date,
        refreshed_at=snapshot_date,
        evidence_label="Review stock health",
        evidence_href="/inventory",
        limitations=("Stock age is an estimate from recorded movements, not FIFO accounting valuation.", "Suggestions do not create or approve purchase orders."),
    )
    if snapshot_date is None or not stock_summary or int(stock_summary.get("record_count") or 0) <= 0:
        return item
    age_days = (as_of_date - snapshot_date).days
    if age_days > stale_after_days:
        item.update(status="stale", severity="unknown", summary=f"The latest inventory-health snapshot is dated {snapshot_date.isoformat()}, which is {age_days} days old. LEXA will not present those counts as current stock advice. Refresh inventory analytics to check again.")
        item["limitations"].append(f"The latest stock snapshot is older than the {stale_after_days}-day freshness limit.")
        return item

    summary = {
        "out_of_stock": int(stock_summary.get("out_of_stock_count") or 0),
        "low_cover": int(stock_summary.get("low_cover_count") or 0),
        "slow_moving": int(stock_summary.get("slow_moving_count") or 0),
        "items_needing_review": int(stock_summary.get("items_needing_review") or 0),
    }
    item["details"] = summary
    item["examples"] = [dict(row) for row in examples[:5]]
    item["metric"] = {"label": "Items needing review", "value": str(summary["items_needing_review"]), "unit": "items"}
    if summary["items_needing_review"] == 0:
        item.update(status="no_finding", severity="informational", summary=f"No stockout, seven-day-or-less stock-cover, or zero-sales-in-30-days flags were found in the snapshot dated {snapshot_date.isoformat()}. This is not a guarantee that all stock records are correct.")
    else:
        severity = "critical" if summary["out_of_stock"] else "attention"
        item.update(status="available", severity=severity, summary=f"The {snapshot_date.isoformat()} snapshot flags {summary['items_needing_review']} item/location rows for review: {summary['out_of_stock']} out of stock, {summary['low_cover']} with seven days or less of cover, and {summary['slow_moving']} with no recorded sales in 30 days. Counts can overlap; review the source records before ordering.")
    return item
