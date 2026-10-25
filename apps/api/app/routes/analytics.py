from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from ..dependencies import require_permission
from ..branch_access import require_full_branch_scope
from ..business_insights import build_balance_insight, build_margin_insight, build_sales_movement_insight, build_stock_risk_insight

router = APIRouter(prefix="/analytics", tags=["analytics"])

def out(row: Any) -> dict[str, Any]:
    d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}

@router.get("/overview")
def overview(start_date: date, end_date: date, currency_code: str = Query(..., min_length=3, max_length=3), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("""SELECT * FROM analytics_daily_business_metrics WHERE tenant_id=:t AND business_date BETWEEN :f AND :to AND currency_code=:c ORDER BY business_date"""), {"t":str(tenant_id),"f":start_date,"to":end_date,"c":currency_code.upper()}).mappings().all()
    product_margin = db.execute(text("""
        SELECT COUNT(*)::integer AS record_count, SUM(gross_margin) AS gross_profit
        FROM public.analytics_product_daily_metrics
        WHERE tenant_id = :t AND business_date BETWEEN :f AND :to AND currency_code = :c
    """), {"t": str(tenant_id), "f": start_date, "to": end_date, "c": currency_code.upper()}).mappings().one()
    gross_profit = Decimal(str(product_margin["gross_profit"])) if product_margin["record_count"] and product_margin["gross_profit"] is not None else None
    totals = {
        "sales_total": sum((Decimal(r["sales_total"]) for r in rows), Decimal(0)),
        "returns_total": sum((Decimal(r["returns_total"]) for r in rows), Decimal(0)),
        "net_sales": sum((Decimal(r["net_sales"]) for r in rows), Decimal(0)),
        "gross_profit": gross_profit,
        "gross_profit_record_count": int(product_margin["record_count"] or 0),
        "payments_collected": sum((Decimal(r["payments_collected"]) for r in rows), Decimal(0)),
        "refunds_total": sum((Decimal(r["refunds_total"]) for r in rows), Decimal(0)),
        "credit_created": sum((Decimal(r["credit_created"]) for r in rows), Decimal(0)),
        "expenses_total": sum((Decimal(r["expenses_total"]) for r in rows), Decimal(0)),
        "expense_reversals_total": sum((Decimal(r["expense_reversals_total"]) for r in rows), Decimal(0)),
        "net_cash_movement": sum((Decimal(r["net_cash_movement"]) for r in rows), Decimal(0)),
        "sale_count": sum((int(r["sale_count"]) for r in rows), 0),
    }
    return {"from_date":str(start_date),"to_date":str(end_date),"currency_code":currency_code.upper(),"totals":{k:(str(v) if isinstance(v,Decimal) else v) for k,v in totals.items()},"daily":[out(r) for r in rows]}


@router.get("/payments-by-channel")
def payments_by_channel(
    start_date: date,
    end_date: date,
    currency_code: str = Query(..., min_length=3, max_length=3),
    ctx=Depends(require_permission("analytics.read")),
):
    """Return recorded customer-sale payments grouped by the owner's payment-method names."""
    db, actor_id, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)
    rows = db.execute(text("""
        SELECT
            p.payment_channel_id AS channel_id,
            COALESCE(pc.name, 'Not specified') AS channel_name,
            COALESCE(pc.channel_type, 'OTHER') AS channel_type,
            p.currency_code,
            SUM(p.amount) AS recorded_amount,
            COUNT(p.id) AS payment_count
        FROM payments p
        JOIN sales s
          ON s.tenant_id = p.tenant_id
         AND s.transaction_id = p.transaction_id
         AND s.status = 'COMPLETED'
        LEFT JOIN payment_channels pc
          ON pc.tenant_id = p.tenant_id
         AND pc.id = p.payment_channel_id
        WHERE p.tenant_id = :tenant_id
          AND p.status = 'RECORDED'
          AND p.currency_code = :currency_code
          AND p.business_date BETWEEN :start_date AND :end_date
        GROUP BY p.payment_channel_id, COALESCE(pc.name, 'Not specified'), COALESCE(pc.channel_type, 'OTHER'), p.currency_code
        ORDER BY SUM(p.amount) DESC, channel_name ASC
        LIMIT 100
    """), {
        "tenant_id": str(tenant_id),
        "currency_code": currency_code.upper(),
        "start_date": start_date,
        "end_date": end_date,
    }).mappings().all()
    return [out(row) for row in rows]

@router.get("/daily")
def daily(start_date: date, end_date: date, currency_code: str = Query(..., min_length=3, max_length=3), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows=db.execute(text("SELECT business_date,currency_code,sales_total,returns_total,net_sales,payments_collected,refunds_total,credit_created,expenses_total,expense_reversals_total,net_cash_movement,sale_count,return_count,payment_count,expense_count FROM analytics_daily_business_metrics WHERE tenant_id=:t AND business_date BETWEEN :f AND :to AND currency_code=:c ORDER BY business_date"),{"t":str(tenant_id),"f":start_date,"to":end_date,"c":currency_code.upper()}).mappings().all()
    return [out(r) for r in rows]

@router.get("/products")
def products(start_date: date, end_date: date, currency_code: str = Query(..., min_length=3, max_length=3), limit: int = Query(default=100, ge=1, le=500), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows=db.execute(text("""SELECT a.business_date,a.variant_id,a.product_id,pv.sku,p.name product_name,pv.name variant_name,a.units_sold,a.sales_amount,a.discount_amount,a.tax_amount,a.returns_units,a.returns_amount,a.net_sales,a.cogs,a.gross_margin,a.currency_code FROM analytics_product_daily_metrics a JOIN product_variants pv ON pv.tenant_id=a.tenant_id AND pv.id=a.variant_id JOIN products p ON p.tenant_id=a.tenant_id AND p.id=a.product_id WHERE a.tenant_id=:t AND a.business_date BETWEEN :f AND :to AND a.currency_code=:c ORDER BY a.net_sales DESC LIMIT :limit"""),{"t":str(tenant_id),"f":start_date,"to":end_date,"c":currency_code.upper(),"limit":limit}).mappings().all()
    return [out(r) for r in rows]

@router.get("/products/summary")
def product_summary(
    start_date: date,
    end_date: date,
    currency_code: str = Query(..., min_length=3, max_length=3),
    limit: int = Query(default=5, ge=1, le=100),
    ctx=Depends(require_permission("analytics.read")),
):
    """Return range-aggregated product results rather than ranking daily rows."""
    db, actor_id, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)
    rows = db.execute(text("""
        SELECT
            a.variant_id,
            a.product_id,
            pv.sku,
            p.name AS product_name,
            pv.name AS variant_name,
            SUM(a.units_sold) AS units_sold,
            SUM(a.sales_amount) AS sales_amount,
            SUM(a.discount_amount) AS discount_amount,
            SUM(a.tax_amount) AS tax_amount,
            SUM(a.returns_units) AS returns_units,
            SUM(a.returns_amount) AS returns_amount,
            SUM(a.net_sales) AS net_sales,
            SUM(a.cogs) AS cogs,
            SUM(a.gross_margin) AS gross_margin,
            a.currency_code
        FROM analytics_product_daily_metrics a
        JOIN product_variants pv ON pv.tenant_id = a.tenant_id AND pv.id = a.variant_id
        JOIN products p ON p.tenant_id = a.tenant_id AND p.id = a.product_id
        WHERE a.tenant_id = :tenant_id
          AND a.business_date BETWEEN :start_date AND :end_date
          AND a.currency_code = :currency_code
        GROUP BY a.variant_id, a.product_id, pv.sku, p.name, pv.name, a.currency_code
        ORDER BY SUM(a.net_sales) DESC, p.name ASC, pv.sku ASC
        LIMIT :limit
    """), {
        "tenant_id": str(tenant_id),
        "start_date": start_date,
        "end_date": end_date,
        "currency_code": currency_code.upper(),
        "limit": limit,
    }).mappings().all()
    return [out(row) for row in rows]


@router.get("/customers")
def customers(limit: int = Query(default=100, ge=1, le=500), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows=db.execute(text("""SELECT a.customer_party_id,p.display_name customer_name,a.first_sale_date,a.last_sale_date,a.sale_count,a.total_sales,a.total_returns,a.net_sales,a.total_paid,a.outstanding_balance,a.average_sale_value FROM analytics_customer_purchase_patterns a JOIN parties p ON p.tenant_id=a.tenant_id AND p.id=a.customer_party_id WHERE a.tenant_id=:t ORDER BY a.net_sales DESC LIMIT :limit"""),{"t":str(tenant_id),"limit":limit}).mappings().all()
    return [out(r) for r in rows]

@router.get("/inventory-health")
def inventory_health(limit: int = Query(default=100, ge=1, le=500), ctx=Depends(require_permission("analytics.read"))):
    db, actor_id, tenant_id, _ = ctx
    rows=db.execute(text("""SELECT a.snapshot_date,a.location_id,l.name location_name,a.variant_id,pv.sku,p.name product_name,pv.name variant_name,a.on_hand,a.reserved,a.available,a.stock_value,a.units_sold_30d,a.daily_velocity,a.days_cover FROM analytics_inventory_health_metrics a JOIN locations l ON l.tenant_id=a.tenant_id AND l.id=a.location_id JOIN product_variants pv ON pv.tenant_id=a.tenant_id AND pv.id=a.variant_id JOIN products p ON p.tenant_id=a.tenant_id AND p.id=pv.product_id WHERE a.tenant_id=:t AND a.location_id IN (SELECT loc.id FROM locations loc JOIN warehouses w ON w.id=loc.warehouse_id AND w.tenant_id=loc.tenant_id JOIN membership_branch_assignments mba ON mba.tenant_id=loc.tenant_id AND mba.branch_id=w.branch_id JOIN tenant_memberships tm ON tm.id=mba.membership_id AND tm.tenant_id=mba.tenant_id WHERE loc.tenant_id=:t AND tm.user_id=:u AND tm.status='ACTIVE' AND mba.status='ACTIVE' AND loc.status='ACTIVE' AND w.status='ACTIVE') ORDER BY a.days_cover NULLS LAST,a.stock_value DESC LIMIT :limit"""),{"t":str(tenant_id),"u":str(actor_id),"limit":limit}).mappings().all()
    return [out(r) for r in rows]

@router.get("/inventory-value-by-location")
def inventory_value_by_location(ctx=Depends(require_permission("analytics.read"))):
    """Aggregate the latest complete stock valuation snapshot by accessible location."""
    db, actor_id, tenant_id, _ = ctx
    rows = db.execute(text("""
        SELECT a.snapshot_date, a.location_id, l.name AS location_name,
               SUM(a.stock_value) AS stock_value,
               COUNT(DISTINCT a.variant_id) AS product_count
        FROM analytics_inventory_health_metrics a
        JOIN locations l ON l.tenant_id = a.tenant_id AND l.id = a.location_id
        JOIN warehouses w ON w.tenant_id = l.tenant_id AND w.id = l.warehouse_id
        WHERE a.tenant_id = :tenant_id
          AND a.snapshot_date = (
              SELECT MAX(latest.snapshot_date)
              FROM analytics_inventory_health_metrics latest
              WHERE latest.tenant_id = :tenant_id
          )
          AND l.status = 'ACTIVE' AND w.status = 'ACTIVE'
          AND EXISTS (
              SELECT 1 FROM membership_branch_assignments mba
              JOIN tenant_memberships tm ON tm.id = mba.membership_id AND tm.tenant_id = mba.tenant_id
              JOIN branches b ON b.tenant_id = mba.tenant_id AND b.id = mba.branch_id
              WHERE mba.tenant_id = a.tenant_id
                AND mba.branch_id = w.branch_id
                AND mba.status = 'ACTIVE' AND tm.user_id = :actor_id
                AND tm.status = 'ACTIVE' AND b.status = 'ACTIVE'
          )
        GROUP BY a.snapshot_date, a.location_id, l.name
        ORDER BY SUM(a.stock_value) DESC, l.name ASC
        LIMIT 200
    """), {"tenant_id": str(tenant_id), "actor_id": str(actor_id)}).mappings().all()
    return [out(row) for row in rows]


@router.get("/branches")
def branches(start_date: date, end_date: date, currency_code: str = Query(..., min_length=3, max_length=3), ctx=Depends(require_permission("analytics.read"))):
    db, actor_id, tenant_id, _ = ctx
    rows=db.execute(text("""SELECT a.branch_id,b.name branch_name,a.business_date,a.currency_code,a.sales_total,a.returns_total,a.net_sales,a.payments_collected,a.credit_created,a.sale_count FROM analytics_branch_daily_metrics a JOIN branches b ON b.tenant_id=a.tenant_id AND b.id=a.branch_id WHERE a.tenant_id=:t AND a.business_date BETWEEN :f AND :to AND a.currency_code=:c AND EXISTS (SELECT 1 FROM membership_branch_assignments mba JOIN tenant_memberships tm ON tm.id=mba.membership_id AND tm.tenant_id=mba.tenant_id WHERE mba.tenant_id=a.tenant_id AND mba.branch_id=a.branch_id AND mba.status='ACTIVE' AND tm.user_id=:u AND tm.status='ACTIVE' AND b.status='ACTIVE') ORDER BY a.business_date DESC,a.net_sales DESC"""),{"t":str(tenant_id),"u":str(actor_id),"f":start_date,"to":end_date,"c":currency_code.upper()}).mappings().all()
    return [out(r) for r in rows]



@router.get("/branches/summary")
def branch_summary(start_date: date, end_date: date, currency_code: str = Query(..., min_length=3, max_length=3), ctx=Depends(require_permission("analytics.read"))):
    """Aggregate branch sales only for active branches assigned to the current user."""
    db, actor_id, tenant_id, _ = ctx
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="The start date must be on or before the end date.")
    if (end_date - start_date).days + 1 > 366:
        raise HTTPException(status_code=422, detail="Choose a reporting period of 366 days or less.")
    currency = currency_code.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise HTTPException(status_code=422, detail="Enter a valid three-letter currency code.")
    rows = db.execute(text("""
        SELECT a.branch_id::text AS branch_id, b.name AS branch_name, a.currency_code,
               COALESCE(SUM(a.sales_total),0) AS sales_total, COALESCE(SUM(a.returns_total),0) AS returns_total,
               COALESCE(SUM(a.net_sales),0) AS net_sales, COALESCE(SUM(a.payments_collected),0) AS payments_collected,
               COALESCE(SUM(a.credit_created),0) AS credit_created, COALESCE(SUM(a.sale_count),0)::integer AS sale_count,
               COUNT(DISTINCT a.business_date)::integer AS days_with_data
        FROM public.analytics_branch_daily_metrics a
        JOIN public.branches b ON b.tenant_id=a.tenant_id AND b.id=a.branch_id
        WHERE a.tenant_id=:tenant_id AND a.business_date BETWEEN :start_date AND :end_date
          AND a.currency_code=:currency_code AND b.status='ACTIVE'
          AND EXISTS (
            SELECT 1 FROM public.membership_branch_assignments mba
            JOIN public.tenant_memberships tm ON tm.id=mba.membership_id AND tm.tenant_id=mba.tenant_id
            WHERE mba.tenant_id=a.tenant_id AND mba.branch_id=a.branch_id
              AND mba.status='ACTIVE' AND tm.user_id=:actor_id AND tm.status='ACTIVE'
          )
        GROUP BY a.branch_id,b.name,a.currency_code ORDER BY SUM(a.net_sales) DESC,b.name ASC
    """), {"tenant_id":str(tenant_id),"actor_id":str(actor_id),"start_date":start_date,"end_date":end_date,"currency_code":currency}).mappings().all()
    return [out(row) for row in rows]


@router.get("/insights")
def business_insights(
    start_date: date,
    end_date: date,
    currency_code: str = Query(..., min_length=3, max_length=3),
    focus: Literal["all", "sales", "margin", "stock", "balances"] = Query(default="all"),
    ctx=Depends(require_permission("analytics.read")),
):
    """Return bounded deterministic insights with explicit freshness and source evidence.

    The endpoint is read-only. It never runs model-provided SQL, calls an external
    AI provider, creates a purchase order, or mutates business records.
    """
    db, actor_id, tenant_id, _ = ctx
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="The start date must be on or before the end date.")
    period_days = (end_date - start_date).days + 1
    if period_days > 366:
        raise HTTPException(status_code=422, detail="Choose a reporting period of 366 days or less.")
    currency = currency_code.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise HTTPException(status_code=422, detail="Enter a valid three-letter currency code.")

    # Analytics projections in this endpoint are tenant-wide. Fail closed instead
    # of showing cross-branch rollups to someone who can only see part of a workspace.
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)

    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    current_params = {"tenant_id": str(tenant_id), "from_date": start_date, "to_date": end_date, "currency": currency}
    previous_params = {"tenant_id": str(tenant_id), "from_date": previous_start, "to_date": previous_end, "currency": currency}

    daily_sql = text("""
        SELECT COUNT(*)::integer AS record_count,
               MAX(business_date) AS latest_business_date,
               MAX(refreshed_at) AS refreshed_at,
               COALESCE(SUM(net_sales), 0) AS net_sales,
               COALESCE(SUM(sales_total), 0) AS sales_total,
               COALESCE(SUM(returns_total), 0) AS returns_total,
               COALESCE(SUM(payments_collected), 0) AS payments_collected,
               COALESCE(SUM(sale_count), 0)::integer AS sale_count
        FROM public.analytics_daily_business_metrics
        WHERE tenant_id = :tenant_id
          AND business_date BETWEEN :from_date AND :to_date
          AND currency_code = :currency
    """)
    product_sql = text("""
        SELECT COUNT(*)::integer AS record_count,
               MAX(business_date) AS latest_business_date,
               MAX(refreshed_at) AS refreshed_at,
               COALESCE(SUM(net_sales), 0) AS net_sales,
               COALESCE(SUM(cogs), 0) AS cogs,
               COALESCE(SUM(gross_margin), 0) AS gross_margin
        FROM public.analytics_product_daily_metrics
        WHERE tenant_id = :tenant_id
          AND business_date BETWEEN :from_date AND :to_date
          AND currency_code = :currency
    """)
    current_daily = dict(db.execute(daily_sql, current_params).mappings().one())
    previous_daily = dict(db.execute(daily_sql, previous_params).mappings().one())
    current_products = dict(db.execute(product_sql, current_params).mappings().one())
    previous_products = dict(db.execute(product_sql, previous_params).mappings().one())

    refresh = db.execute(text("""
        SELECT MAX(completed_at) AS last_successful_refresh_at
        FROM public.analytics_refresh_runs
        WHERE tenant_id = :tenant_id AND status = 'SUCCEEDED'
    """), {"tenant_id": str(tenant_id)}).mappings().one()
    last_refresh_at = refresh["last_successful_refresh_at"]
    now = datetime.now(timezone.utc)

    def recent(value: Any, *, hours: int = 72) -> bool:
        if not isinstance(value, datetime):
            return False
        normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return normalized >= now - timedelta(hours=hours)

    daily_is_fresh = recent(last_refresh_at) and recent(current_daily.get("refreshed_at"))
    product_is_fresh = recent(last_refresh_at) and recent(current_products.get("refreshed_at"))

    receivables_summary = dict(db.execute(text("""
        SELECT COUNT(*)::integer AS record_count,
               COUNT(*) FILTER (
                   WHERE r.status IN ('OPEN', 'PARTIALLY_PAID') AND COALESCE(r.balance, 0) > 0
               )::integer AS open_count,
               COUNT(DISTINCT r.customer_party_id) FILTER (
                   WHERE r.status IN ('OPEN', 'PARTIALLY_PAID') AND COALESCE(r.balance, 0) > 0
               )::integer AS open_customer_count,
               COALESCE(SUM(r.balance) FILTER (
                   WHERE r.status IN ('OPEN', 'PARTIALLY_PAID') AND COALESCE(r.balance, 0) > 0
               ), 0) AS open_balance,
               COUNT(*) FILTER (
                   WHERE r.status IN ('OPEN', 'PARTIALLY_PAID')
                     AND COALESCE(r.balance, 0) > 0 AND r.due_at < now()
               )::integer AS overdue_count,
               COALESCE(SUM(r.balance) FILTER (
                   WHERE r.status IN ('OPEN', 'PARTIALLY_PAID')
                     AND COALESCE(r.balance, 0) > 0 AND r.due_at < now()
               ), 0) AS overdue_balance
        FROM public.receivables r
        JOIN public.sales s ON s.tenant_id = r.tenant_id AND s.id = r.sale_id
        WHERE r.tenant_id = :tenant_id AND s.currency_code = :currency
    """), {"tenant_id": str(tenant_id), "currency": currency}).mappings().one())
    supplier_ledger_summary = dict(db.execute(text("""
        SELECT COUNT(*)::integer AS record_count,
               COUNT(DISTINCT supplier_party_id)::integer AS supplier_count,
               COALESCE(SUM(debit_amount - credit_amount), 0) AS net_balance
        FROM public.supplier_ledger_entries
        WHERE tenant_id = :tenant_id AND currency_code = :currency
    """), {"tenant_id": str(tenant_id), "currency": currency}).mappings().one())

    stock_latest = db.execute(text("""
        SELECT MAX(a.snapshot_date)
        FROM public.analytics_inventory_health_metrics a
        JOIN public.locations l ON l.tenant_id = a.tenant_id AND l.id = a.location_id
        JOIN public.warehouses w ON w.tenant_id = l.tenant_id AND w.id = l.warehouse_id
        JOIN public.branches b ON b.tenant_id = w.tenant_id AND b.id = w.branch_id
        WHERE a.tenant_id = :tenant_id
          AND l.status = 'ACTIVE' AND w.status = 'ACTIVE' AND b.status = 'ACTIVE'
    """), {"tenant_id": str(tenant_id)}).scalar_one_or_none()

    stock_summary: dict[str, Any] | None = None
    stock_examples: list[dict[str, Any]] = []
    if stock_latest is not None:
        stock_summary = dict(db.execute(text("""
            SELECT COUNT(*)::integer AS record_count,
                   COUNT(*) FILTER (WHERE a.available <= 0)::integer AS out_of_stock_count,
                   COUNT(*) FILTER (WHERE a.available > 0 AND a.days_cover IS NOT NULL AND a.days_cover <= 7)::integer AS low_cover_count,
                   COUNT(*) FILTER (WHERE a.on_hand > 0 AND COALESCE(a.units_sold_30d, 0) = 0)::integer AS slow_moving_count,
                   COUNT(*) FILTER (
                       WHERE a.available <= 0
                          OR (a.days_cover IS NOT NULL AND a.days_cover <= 7)
                          OR (a.on_hand > 0 AND COALESCE(a.units_sold_30d, 0) = 0)
                   )::integer AS items_needing_review
            FROM public.analytics_inventory_health_metrics a
            JOIN public.locations l ON l.tenant_id = a.tenant_id AND l.id = a.location_id
            JOIN public.warehouses w ON w.tenant_id = l.tenant_id AND w.id = l.warehouse_id
            JOIN public.branches b ON b.tenant_id = w.tenant_id AND b.id = w.branch_id
            WHERE a.tenant_id = :tenant_id AND a.snapshot_date = :snapshot_date
              AND l.status = 'ACTIVE' AND w.status = 'ACTIVE' AND b.status = 'ACTIVE'
        """), {"tenant_id": str(tenant_id), "snapshot_date": stock_latest}).mappings().one())
        stock_examples = [dict(row) for row in db.execute(text("""
            SELECT a.location_id, l.name AS location_name, a.variant_id,
                   p.name AS product_name, pv.name AS variant_name, pv.sku,
                   a.on_hand, a.reserved, a.available, a.units_sold_30d, a.days_cover
            FROM public.analytics_inventory_health_metrics a
            JOIN public.locations l ON l.tenant_id = a.tenant_id AND l.id = a.location_id
            JOIN public.warehouses w ON w.tenant_id = l.tenant_id AND w.id = l.warehouse_id
            JOIN public.branches b ON b.tenant_id = w.tenant_id AND b.id = w.branch_id
            JOIN public.product_variants pv ON pv.tenant_id = a.tenant_id AND pv.id = a.variant_id
            JOIN public.products p ON p.tenant_id = pv.tenant_id AND p.id = pv.product_id
            WHERE a.tenant_id = :tenant_id AND a.snapshot_date = :snapshot_date
              AND l.status = 'ACTIVE' AND w.status = 'ACTIVE' AND b.status = 'ACTIVE'
              AND (a.available <= 0 OR (a.days_cover IS NOT NULL AND a.days_cover <= 7)
                   OR (a.on_hand > 0 AND COALESCE(a.units_sold_30d, 0) = 0))
            ORDER BY CASE WHEN a.available <= 0 THEN 0
                          WHEN a.days_cover IS NOT NULL AND a.days_cover <= 7 THEN 1 ELSE 2 END,
                     a.available ASC, p.name ASC
            LIMIT 5
        """), {"tenant_id": str(tenant_id), "snapshot_date": stock_latest}).mappings().all()]
        for example in stock_examples:
            example["on_hand"] = str(example["on_hand"])
            example["reserved"] = str(example["reserved"])
            example["available"] = str(example["available"])
            example["units_sold_30d"] = str(example["units_sold_30d"])
            example["days_cover"] = None if example["days_cover"] is None else str(example["days_cover"])

    all_insights = [
        build_sales_movement_insight(
            current=current_daily,
            previous=previous_daily,
            start_date=start_date,
            end_date=end_date,
            previous_start_date=previous_start,
            previous_end_date=previous_end,
            currency_code=currency,
            fresh=daily_is_fresh,
        ),
        build_margin_insight(
            current=current_products,
            previous=previous_products,
            start_date=start_date,
            end_date=end_date,
            previous_start_date=previous_start,
            previous_end_date=previous_end,
            currency_code=currency,
            fresh=product_is_fresh,
        ),
        build_balance_insight(
            receivables=receivables_summary,
            supplier_ledger=supplier_ledger_summary,
            as_of_date=date.today(),
            currency_code=currency,
        ),
        build_stock_risk_insight(
            snapshot_date=stock_latest,
            as_of_date=date.today(),
            stock_summary=stock_summary,
            examples=stock_examples,
        ),
    ]
    chosen = all_insights if focus == "all" else [item for item in all_insights if item["id"] == {"sales": "sales-movement", "margin": "gross-margin-movement", "stock": "stock-risk", "balances": "working-capital-balances"}[focus]]
    return {
        "rule_version": "lexa-business-insights-1.0",
        "advisory_only": True,
        "external_ai_used": False,
        "scope": "all active workspace branches",
        "currency_code": currency,
        "period": {"from_date": start_date.isoformat(), "to_date": end_date.isoformat()},
        "comparison_period": {"from_date": previous_start.isoformat(), "to_date": previous_end.isoformat()},
        "last_successful_refresh_at": last_refresh_at.isoformat() if last_refresh_at else None,
        "insights": chosen,
        "note": "These are deterministic, source-linked review prompts. They do not execute business actions or replace the underlying reports.",
    }

@router.post("/refresh")
def refresh(start_date: date, end_date: date, ctx=Depends(require_permission("analytics.refresh"))):
    db, actor_id, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)
    run_id=db.execute(text("SELECT refresh_analytics(:t,:f,:to)"),{"t":str(tenant_id),"f":start_date,"to":end_date}).scalar_one()
    db.commit()
    return {"run_id":str(run_id),"status":"SUCCEEDED"}
