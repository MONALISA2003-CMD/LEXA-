"""Local Uganda tax estimates and manual URA fiscal-document recordkeeping.

No outbound network calls are performed by this router. It never submits to
EFRIS, accepts card/mobile-money payments, or changes an official registration.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..branch_access import require_full_branch_scope
from ..catalog import write_audit
from ..dependencies import require_permission
from ..uganda_tax_2026 import (
    calculate_presumptive_tax,
    calculate_paye,
    calculate_vat,
    calculate_withholding,
    tax_reference_payload,
)

router = APIRouter(prefix="/compliance", tags=["local-tax-and-manual-fiscal-records"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaxEstimateRequest(Strict):
    tax_type: Literal["VAT", "PRESUMPTIVE", "PAYE", "WHT_SUPPLY", "WHT_PROFESSIONAL"]
    amount: Decimal = Field(ge=0, max_digits=20, decimal_places=4, description="VAT base/price, annual turnover, monthly chargeable PAYE income, or withholding payment amount")
    currency_code: str = Field(default="UGX", pattern=r"^[A-Za-z]{3}$")
    price_includes_tax: bool = False
    records_kept: bool = True
    resident_taxpayer: bool = True
    employee_residency: Literal["RESIDENT", "NON_RESIDENT"] = "RESIDENT"
    business_sector: str = Field(default="GENERAL", max_length=50)
    withholding_agent: bool = False
    payee_residency: Literal["RESIDENT", "NON_RESIDENT"] = "RESIDENT"

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return str(value or "UGX").strip().upper()

    @field_validator("business_sector", mode="before")
    @classmethod
    def normalize_sector(cls, value: str) -> str:
        return str(value or "GENERAL").strip().upper().replace(" ", "_")


class ManualFiscalDocumentRequest(Strict):
    document_type: Literal["INVOICE", "RECEIPT", "CREDIT_NOTE", "DEBIT_NOTE"]
    issue_date: date
    currency_code: str = Field(pattern=r"^[A-Za-z]{3}$")
    fdn: str = Field(min_length=1, max_length=40, description="FDN copied from the official document returned by URA")
    document_number: str | None = Field(default=None, max_length=100)
    verification_code: str | None = Field(default=None, max_length=160)
    qr_code: str | None = Field(default=None, max_length=4000)
    sale_id: UUID | None = None

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return str(value or "").strip().upper()

    @field_validator("fdn")
    @classmethod
    def require_trimmed_fdn(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Enter the FDN exactly as shown on the official URA document")
        return cleaned

    @field_validator("document_number", "verification_code")
    @classmethod
    def trim_optional_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


@router.get("/tax-reference")
def get_tax_reference(ctx=Depends(require_permission("tax.read"))):
    # Reference is local static data; no URA/API fetch is attempted.
    return tax_reference_payload()


@router.post("/tax-estimate")
def tax_estimate(body: TaxEstimateRequest, ctx=Depends(require_permission("tax.read"))):
    """Run an attributed local estimate without changing saved transactions."""
    try:
        if body.currency_code != "UGX":
            raise ValueError("Uganda statutory tax estimates in this calculator must be entered in UGX")
        if body.tax_type == "VAT":
            result = calculate_vat(body.amount, price_includes_tax=body.price_includes_tax)
            result["tax_type"] = "VAT"
            result["currency_code"] = body.currency_code
        elif body.tax_type == "PRESUMPTIVE":
            result = calculate_presumptive_tax(
                body.amount,
                records_kept=body.records_kept,
                resident_taxpayer=body.resident_taxpayer,
                sector=body.business_sector,
            )
            result["currency_code"] = body.currency_code
        elif body.tax_type == "PAYE":
            result = calculate_paye(body.amount, residency=body.employee_residency)
            result["currency_code"] = body.currency_code
        else:
            kind = "TAXABLE_SUPPLY" if body.tax_type == "WHT_SUPPLY" else "PROFESSIONAL_OR_MANAGEMENT"
            result = calculate_withholding(
                body.amount,
                withholding_agent=body.withholding_agent,
                withholding_kind=kind,
                payee_residency=body.payee_residency,
            )
            result["currency_code"] = body.currency_code
        result["is_estimate"] = True
        result["no_external_submission"] = True
        result["reference_date"] = "2026-10-23"
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/manual-fiscal-documents", status_code=201)
def create_manual_fiscal_document(
    body: ManualFiscalDocumentRequest,
    ctx=Depends(require_permission("efris.manage")),
):
    """Store a document the owner separately obtained from URA; never submit it."""
    db, actor_id, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)

    duplicate_fdn = db.execute(text("""
        SELECT id FROM public.fiscal_documents
        WHERE tenant_id=:tenant_id AND fdn=:fdn
        LIMIT 1
    """), {"tenant_id": str(tenant_id), "fdn": body.fdn}).scalar_one_or_none()
    if duplicate_fdn:
        raise HTTPException(409, "This FDN is already recorded in this workspace")

    source_type = "MANUAL_URA_RECORD"
    source_id = uuid4()
    if body.sale_id:
        sale = db.execute(text("""
            SELECT id, currency_code, status
            FROM public.sales
            WHERE tenant_id=:tenant_id AND id=:sale_id
        """), {"tenant_id": str(tenant_id), "sale_id": str(body.sale_id)}).mappings().first()
        if not sale:
            raise HTTPException(404, "Sale not found in this workspace")
        if sale["status"] != "COMPLETED":
            raise HTTPException(409, "Only a completed sale can be linked to an official URA document")
        if str(sale["currency_code"]).upper() != body.currency_code:
            raise HTTPException(422, "Document currency must match the linked sale currency")
        source_type = "SALE"
        source_id = body.sale_id
        existing = db.execute(text("""
            SELECT id FROM public.fiscal_documents
            WHERE tenant_id=:tenant_id AND source_type='SALE'
              AND source_id=:source_id AND document_type=:document_type
        """), {"tenant_id": str(tenant_id), "source_id": str(source_id), "document_type": body.document_type}).scalar_one_or_none()
        if existing:
            raise HTTPException(409, "A fiscal-document record of this type already exists for that sale")

    metadata = {
        "record_method": "MANUAL_URA_PORTAL",
        "verification_status": "NOT_VERIFIED_BY_LEXA",
        "external_submission": False,
    }
    try:
        document_id = db.execute(text("""
            INSERT INTO public.fiscal_documents(
              tenant_id,source_type,source_id,document_type,currency_code,issue_date,
              status,document_number,fdn,verification_code,qr_code,metadata
            ) VALUES (
              :tenant_id,:source_type,:source_id,:document_type,:currency_code,:issue_date,
              'DRAFT',:document_number,:fdn,:verification_code,:qr_code,CAST(:metadata AS jsonb)
            ) RETURNING id
        """), {
            "tenant_id": str(tenant_id), "source_type": source_type, "source_id": str(source_id),
            "document_type": body.document_type, "currency_code": body.currency_code,
            "issue_date": body.issue_date, "document_number": body.document_number, "fdn": body.fdn,
            "verification_code": body.verification_code, "qr_code": body.qr_code,
            "metadata": json.dumps(metadata),
        }).scalar_one()
        write_audit(
            db, tenant_id=tenant_id, actor_user_id=actor_id,
            action="compliance.fiscal_document.manual_record",
            target_type="fiscal_document", target_id=document_id, outcome="SUCCESS",
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A matching fiscal-document record already exists") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, "The manual fiscal-document record could not be saved") from exc

    return {
        "id": str(document_id),
        "document_type": body.document_type,
        "issue_date": body.issue_date.isoformat(),
        "currency_code": body.currency_code,
        "fdn": body.fdn,
        "document_number": body.document_number,
        "verification_code": body.verification_code,
        "status": "DRAFT",
        "record_method": "MANUAL_URA_PORTAL",
        "verification_status": "NOT_VERIFIED_BY_LEXA",
        "external_submission": False,
        "message": "Saved as a manual record only. LEXA has not contacted URA or verified this document.",
    }
