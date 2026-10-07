from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from ..dependencies import require_permission

router = APIRouter(prefix="/analytics", tags=["analytics"])

def out(row: Any) -> dict[str, Any]:
    d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}

@router.get("/overview")
def overview(start_date: date, end_date: date, currency_code: str = Query(default="UGX", min_length=3, max_length=3), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.execute(text("""SELECT * FROM analytics_daily_business_metrics WHERE tenant_id=:t AND business_date BETWEEN :f AND :to AND currency_code=:c ORDER BY business_date"""), {"t":str(tenant_id),"f":start_date,"to":end_date,"c":currency_code.upper()}).mappings().all()
    totals = {
        "sales_total": sum((Decimal(r["sales_total"]) for r in rows), Decimal(0)),
        "returns_total": sum((Decimal(r["returns_total"]) for r in rows), Decimal(0)),
        "net_sales": sum((Decimal(r["net_sales"]) for r in rows), Decimal(0)),
        "payments_collected": sum((Decimal(r["payments_collected"]) for r in rows), Decimal(0)),
        "refunds_total": sum((Decimal(r["refunds_total"]) for r in rows), Decimal(0)),
        "credit_created": sum((Decimal(r["credit_created"]) for r in rows), Decimal(0)),
        "expenses_total": sum((Decimal(r["expenses_total"]) for r in rows), Decimal(0)),
        "net_cash_movement": sum((Decimal(r["net_cash_movement"]) for r in rows), Decimal(0)),
        "sale_count": sum((int(r["sale_count"]) for r in rows), 0),
    }
    return {"from_date":str(start_date),"to_date":str(end_date),"currency_code":currency_code.upper(),"totals":{k:(str(v) if isinstance(v,Decimal) else v) for k,v in totals.items()},"daily":[out(r) for r in rows]}

@router.get("/daily")
def daily(start_date: date, end_date: date, currency_code: str = Query(default="UGX", min_length=3, max_length=3), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    rows=db.execute(text("SELECT business_date,currency_code,sales_total,returns_total,net_sales,payments_collected,refunds_total,credit_created,expenses_total,net_cash_movement,sale_count,return_count,payment_count,expense_count FROM analytics_daily_business_metrics WHERE tenant_id=:t AND business_date BETWEEN :f AND :to AND currency_code=:c ORDER BY business_date"),{"t":str(tenant_id),"f":start_date,"to":end_date,"c":currency_code.upper()}).mappings().all()
    return [out(r) for r in rows]

@router.get("/products")
def products(start_date: date, end_date: date, currency_code: str = Query(default="UGX", min_length=3, max_length=3), limit: int = Query(default=100, ge=1, le=500), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    rows=db.execute(text("""SELECT a.business_date,a.variant_id,a.product_id,pv.sku,p.name product_name,pv.name variant_name,a.units_sold,a.sales_amount,a.discount_amount,a.tax_amount,a.returns_units,a.returns_amount,a.net_sales,a.cogs,a.gross_margin,a.currency_code FROM analytics_product_daily_metrics a JOIN product_variants pv ON pv.tenant_id=a.tenant_id AND pv.id=a.variant_id JOIN products p ON p.tenant_id=a.tenant_id AND p.id=a.product_id WHERE a.tenant_id=:t AND a.business_date BETWEEN :f AND :to AND a.currency_code=:c ORDER BY a.net_sales DESC LIMIT :limit"""),{"t":str(tenant_id),"f":start_date,"to":end_date,"c":currency_code.upper(),"limit":limit}).mappings().all()
    return [out(r) for r in rows]

@router.get("/customers")
def customers(limit: int = Query(default=100, ge=1, le=500), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    rows=db.execute(text("""SELECT a.customer_party_id,p.display_name customer_name,a.first_sale_date,a.last_sale_date,a.sale_count,a.total_sales,a.total_returns,a.net_sales,a.total_paid,a.outstanding_balance,a.average_sale_value FROM analytics_customer_purchase_patterns a JOIN parties p ON p.tenant_id=a.tenant_id AND p.id=a.customer_party_id WHERE a.tenant_id=:t ORDER BY a.net_sales DESC LIMIT :limit"""),{"t":str(tenant_id),"limit":limit}).mappings().all()
    return [out(r) for r in rows]

@router.get("/inventory-health")
def inventory_health(limit: int = Query(default=100, ge=1, le=500), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    rows=db.execute(text("""SELECT a.snapshot_date,a.location_id,l.name location_name,a.variant_id,pv.sku,p.name product_name,pv.name variant_name,a.on_hand,a.reserved,a.available,a.stock_value,a.units_sold_30d,a.daily_velocity,a.days_cover FROM analytics_inventory_health_metrics a JOIN locations l ON l.tenant_id=a.tenant_id AND l.id=a.location_id JOIN product_variants pv ON pv.tenant_id=a.tenant_id AND pv.id=a.variant_id JOIN products p ON p.tenant_id=a.tenant_id AND p.id=pv.product_id WHERE a.tenant_id=:t ORDER BY a.days_cover NULLS LAST,a.stock_value DESC LIMIT :limit"""),{"t":str(tenant_id),"limit":limit}).mappings().all()
    return [out(r) for r in rows]

@router.get("/branches")
def branches(start_date: date, end_date: date, currency_code: str = Query(default="UGX", min_length=3, max_length=3), ctx=Depends(require_permission("analytics.read"))):
    db, _, tenant_id, _ = ctx
    rows=db.execute(text("""SELECT a.branch_id,b.name branch_name,a.business_date,a.currency_code,a.sales_total,a.returns_total,a.net_sales,a.payments_collected,a.credit_created,a.sale_count FROM analytics_branch_daily_metrics a JOIN branches b ON b.tenant_id=a.tenant_id AND b.id=a.branch_id WHERE a.tenant_id=:t AND a.business_date BETWEEN :f AND :to AND a.currency_code=:c ORDER BY a.business_date DESC,a.net_sales DESC"""),{"t":str(tenant_id),"f":start_date,"to":end_date,"c":currency_code.upper()}).mappings().all()
    return [out(r) for r in rows]

@router.post("/refresh")
def refresh(start_date: date, end_date: date, ctx=Depends(require_permission("analytics.refresh"))):
    db, _, tenant_id, _ = ctx
    run_id=db.execute(text("SELECT refresh_analytics(:t,:f,:to)"),{"t":str(tenant_id),"f":start_date,"to":end_date}).scalar_one()
    db.commit()
    return {"run_id":str(run_id),"status":"SUCCEEDED"}
