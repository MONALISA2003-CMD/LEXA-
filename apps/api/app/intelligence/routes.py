"""LEXA-owned intelligence API: safe capability discovery and rules-first daily brief."""
from __future__ import annotations

import re
import shutil
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from ..config import settings
from ..dependencies import require_permission
from . import CONTRACT_VERSION, POLICY_VERSION
from .daily_brief import build_daily_brief
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
        "phase": "phase3_document_intelligence",
        "capabilities": {
            "deterministic_business_insights": True,
            "deterministic_replenishment_calculations": True,
            "cross_module_daily_brief": True,
            "document_intake": True,
            "local_document_extraction": True,
            "document_human_review": True,
            "python_forecasting": False,
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
