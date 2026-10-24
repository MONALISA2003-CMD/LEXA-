"""LEXA-owned intelligence API: safe capability discovery and rules-first daily brief."""
from __future__ import annotations

import re
import shutil
from decimal import Decimal
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from ..config import settings
from ..dependencies import require_permission
from ..branch_access import require_full_branch_scope
from . import CONTRACT_VERSION, POLICY_VERSION
from .daily_brief import build_daily_brief
from .forecasting import HISTORY_DAYS, FORECAST_VERSION, seasonal_weekday_forecast
from .policy import configured_provider_ids, policy_from_settings

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/capabilities")
def intelligence_capabilities(ctx=Depends(require_permission("analytics.read"))):
    """Describe available intelligence without returning secrets or business data."""
    del ctx
    policy = policy_from_settings(settings)
    configured = configured_provider_ids()
    from .policy import PAID_PROVIDER_IDS

    eligible = sorted(
        item.value for item in configured.intersection(policy.allowed_providers)
        if policy.external_providers_enabled
        and policy.confidential_external_enabled
        and (item not in PAID_PROVIDER_IDS or policy.paid_providers_enabled)
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "policy_version": POLICY_VERSION,
        "phase": "phase4_demand_forecasting_pilot",
        "capabilities": {
            "deterministic_business_insights": True,
            "deterministic_replenishment_calculations": True,
            "cross_module_daily_brief": True,
            "document_intake": True,
            "local_document_extraction": True,
            "document_human_review": True,
            "python_forecasting": True,
            "seasonal_demand_forecast": True,
            "rolling_origin_backtest": True,
            "external_model_document_extraction": False,
            "automatic_business_writes": False,
        },
        "external_ai": {
            "enabled": False,
            "execution_available": False,
            "eligible_provider_ids_for_a_later_phase": eligible,
            "paid_provider_opt_in": policy.paid_providers_enabled,
            "aggregated_business_data_approved": policy.aggregate_external_enabled,
            "confidential_business_data_approved": policy.confidential_external_enabled,
            "personal_data_external_allowed": False,
            "automatic_fallbacks": False,
        },
        "local_document_tools": {
            "pdf_text": bool(shutil.which("pdftotext")),
            "pdf_render": bool(shutil.which("pdftoppm")),
            "image_ocr": bool(shutil.which("tesseract")),
            "note": "Missing tools fall back to manual review; no external OCR or model is called.",
        },
        "durable_job_schema_version": "045_intelligence_foundation",
        "document_schema_version": "046_intelligence_documents",
        "durable_job_execution_enabled": False,
        "write_capabilities": [],
    }


@router.get("/daily-brief")
def intelligence_daily_brief(
    currency_code: str = Query(default="UGX", min_length=3, max_length=3),
    ctx=Depends(require_permission("analytics.read")),
):
    """Compose a seven-day read-only brief from LEXA's existing deterministic insights."""
    db, actor_id, tenant_id, _session_id = ctx
    business_date = db.execute(
        text("SELECT public.lexa_business_date(now(), CAST(:tenant_id AS uuid))"),
        {"tenant_id": str(tenant_id)},
    ).scalar_one_or_none()
    if not isinstance(business_date, date):
        raise HTTPException(
            status_code=503,
            detail={"code": "BUSINESS_DATE_UNAVAILABLE", "message": "LEXA could not determine this workspace's business date."},
        )
    currency = currency_code.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise HTTPException(status_code=422, detail="Enter a valid three-letter currency code.")

    # Reuse the existing handler's calculation/query path; do not introduce parallel
    # definitions of sales, gross margin, inventory risk, or working-capital balances.
    from ..routes.analytics import business_insights

    end_date = business_date
    start_date = end_date - timedelta(days=6)
    insights_payload = business_insights(
        start_date=start_date,
        end_date=end_date,
        currency_code=currency,
        focus="all",
        ctx=(db, actor_id, tenant_id, _session_id),
    )
    return build_daily_brief(
        insights_payload=insights_payload,
        as_of_date=business_date,
        currency_code=currency,
    )


@router.get("/demand-forecast")
def intelligence_demand_forecast(
    horizon_days: int = Query(default=14, ge=7, le=28),
    ctx=Depends(require_permission("analytics.read")),
):
    """Return advisory, tenant-wide SKU demand baselines with freshness and backtest evidence.

    This endpoint intentionally uses only recorded unit sales and a fresh, successful
    analytics refresh that covers the complete 56-day history window. It does not
    infer sales zeros from a missing/stale projection, call external AI, or mutate stock.
    """
    db, actor_id, tenant_id, _session_id = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)

    business_date = db.execute(
        text("SELECT public.lexa_business_date(now(), CAST(:tenant_id AS uuid))"),
        {"tenant_id": str(tenant_id)},
    ).scalar_one_or_none()
    if not isinstance(business_date, date):
        raise HTTPException(
            status_code=503,
            detail={"code": "BUSINESS_DATE_UNAVAILABLE", "message": "LEXA could not determine this workspace's business date."},
        )

    history_start = business_date - timedelta(days=HISTORY_DAYS - 1)
    refresh_row = db.execute(text("""
        SELECT MAX(completed_at) AS completed_at
        FROM public.analytics_refresh_runs
        WHERE tenant_id = :tenant_id
          AND status = 'SUCCEEDED'
          AND from_date <= :history_start
          AND to_date >= :business_date
          AND completed_at >= now() - INTERVAL '72 hours'
    """), {
        "tenant_id": str(tenant_id),
        "history_start": history_start,
        "business_date": business_date,
    }).mappings().one()
    refresh_at = refresh_row["completed_at"]
    base = {
        "schema_version": "phase4.demand_forecast.v1",
        "forecast_version": FORECAST_VERSION,
        "as_of_date": business_date.isoformat(),
        "scope": "workspace-wide across all active branches; caller must have full branch scope",
        "history_from_date": history_start.isoformat(),
        "history_to_date": business_date.isoformat(),
        "history_days_required": HISTORY_DAYS,
        "horizon_days": horizon_days,
        "history_coverage_verified": bool(refresh_at),
        "history_refresh_completed_at": refresh_at.isoformat() if refresh_at else None,
        "source_tables": ["analytics_product_daily_metrics", "analytics_refresh_runs"],
        "advisory_only": True,
        "external_ai_used": False,
        "business_writes_performed": False,
        "stockout_censoring_corrected": False,
        "limitations": [
            "This is an explainable weekday-seasonal baseline, not a trained or independently validated production model.",
            "Recorded sales can understate underlying demand during stockouts; this pilot does not correct for stockout-censored sales.",
            "Historical same-weekday ranges are descriptive ranges, not calibrated statistical prediction intervals.",
            "Forecasts do not create purchase orders, change reorder points, reserve stock, or mutate inventory.",
        ],
    }
    if not refresh_at:
        return {
            **base,
            "status": "unavailable",
            "reason_code": "FRESH_COMPLETE_HISTORY_REQUIRED",
            "message": "A successful analytics refresh covering all 56 days and completed in the last 72 hours is required. LEXA has not inferred missing history as zero demand.",
            "items": [],
            "excluded_items": [],
        }

    # Quantities are summed across transaction currencies because units are a
    # dimensionless measure. No money values are combined across currencies here.
    rows = db.execute(text("""
        WITH top_variants AS (
            SELECT tenant_id, variant_id, product_id, SUM(units_sold) AS observed_units
            FROM public.analytics_product_daily_metrics
            WHERE tenant_id = :tenant_id
              AND business_date BETWEEN :history_start AND :business_date
            GROUP BY tenant_id, variant_id, product_id
            HAVING SUM(units_sold) > 0
            ORDER BY SUM(units_sold) DESC, variant_id
            LIMIT 30
        )
        SELECT a.variant_id::text AS variant_id,
               a.product_id::text AS product_id,
               pv.sku,
               p.name AS product_name,
               pv.name AS variant_name,
               a.business_date,
               SUM(a.units_sold) AS units_sold
        FROM top_variants tv
        JOIN public.analytics_product_daily_metrics a
          ON a.tenant_id = tv.tenant_id
         AND a.variant_id = tv.variant_id
         AND a.product_id = tv.product_id
         AND a.business_date BETWEEN :history_start AND :business_date
        JOIN public.product_variants pv
          ON pv.tenant_id = a.tenant_id AND pv.id = a.variant_id
        JOIN public.products p
          ON p.tenant_id = a.tenant_id AND p.id = a.product_id
        GROUP BY a.variant_id, a.product_id, pv.sku, p.name, pv.name, a.business_date
        ORDER BY p.name, pv.name, a.business_date
    """), {
        "tenant_id": str(tenant_id),
        "history_start": history_start,
        "business_date": business_date,
    }).mappings().all()

    if not rows:
        return {
            **base,
            "status": "unavailable",
            "reason_code": "NO_RECORDED_DEMAND_HISTORY",
            "message": "No product demand rows were found in the fully refreshed window. LEXA has not generated zero forecasts for items without evidence of recorded demand.",
            "items": [],
            "excluded_items": [],
        }

    by_variant: dict[str, dict[str, object]] = {}
    for row in rows:
        variant_id = str(row["variant_id"])
        item = by_variant.setdefault(variant_id, {
            "variant_id": variant_id,
            "product_id": str(row["product_id"]),
            "sku": row["sku"],
            "product_name": row["product_name"],
            "variant_name": row["variant_name"],
            "daily_units": {},
        })
        daily_units = item["daily_units"]
        assert isinstance(daily_units, dict)
        daily_units[row["business_date"]] = daily_units.get(row["business_date"], Decimal(0)) + Decimal(str(row["units_sold"]))

    items: list[dict[str, object]] = []
    excluded_items: list[dict[str, str | None]] = []
    for item in by_variant.values():
        observations = item["daily_units"]
        assert isinstance(observations, dict)
        # Filling absent days with zero is permissible only after the fresh full-window
        # refresh gate above proves the projection has been recalculated for all dates.
        series = [observations.get(history_start + timedelta(days=offset), Decimal(0)) for offset in range(HISTORY_DAYS)]
        model = seasonal_weekday_forecast(
            series,
            history_start=history_start,
            as_of_date=business_date,
            horizon_days=horizon_days,
        )
        if model["status"] == "unavailable":
            excluded_items.append({
                "product_name": str(item["product_name"]),
                "variant_name": str(item["variant_name"]),
                "sku": str(item["sku"]) if item["sku"] is not None else None,
                "reason_code": str(model.get("reason_code") or "INSUFFICIENT_HISTORY"),
                "message": str(model.get("message") or "Not enough history for a reliable baseline."),
            })
            continue
        items.append({
            "variant_id": item["variant_id"],
            "product_id": item["product_id"],
            "sku": item["sku"],
            "product_name": item["product_name"],
            "variant_name": item["variant_name"],
            **model,
        })

    if not items:
        return {
            **base,
            "status": "unavailable",
            "reason_code": "NO_ELIGIBLE_DEMAND_SERIES",
            "message": "The refreshed history did not contain enough active demand for any of the selected variants.",
            "items": [],
            "excluded_items": excluded_items[:30],
        }
    return {
        **base,
        "status": "partial" if excluded_items or any(item.get("status") == "partial" for item in items) else "available",
        "reason_code": None,
        "message": "Forecasts are planning evidence only. Compare the rolling-origin metrics with the last-week baseline before relying on a series.",
        "items": items,
        "excluded_items": excluded_items[:30],
    }
