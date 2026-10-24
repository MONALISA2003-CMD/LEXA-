"""Tenant- and branch-scoped document intake and human review API.

The API stores a bounded original file, extracts text locally, and produces
untrusted candidate fields. It never creates or posts accounting/purchasing rows.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any, Literal
from urllib.parse import quote, unquote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..branch_access import assigned_branch_ids, ensure_branch_access
from ..dependencies import require_permission
from .document_extraction import ALLOWED_MIME_TYPES, DOCUMENT_TYPES, MAX_FILE_BYTES, extract_document

router = APIRouter(prefix="/intelligence/documents", tags=["intelligence-documents"])
logger = logging.getLogger("lexa.intelligence.documents")
_ALLOWED_REVIEW_FIELDS = frozenset({
    "supplier_name", "customer_name", "invoice_number", "receipt_number",
    "purchase_order_number", "invoice_date", "due_date", "subtotal",
    "tax_amount", "total", "tax_id", "currency_code",
})
_TEXT_FIELDS = frozenset({
    "supplier_name", "customer_name", "invoice_number", "receipt_number",
    "purchase_order_number", "tax_id",
})
_MONEY_FIELDS = frozenset({"subtotal", "tax_amount", "total"})
_DATE_FIELDS = frozenset({"invoice_date", "due_date"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DocumentReviewRequest(StrictModel):
    action: Literal["CONFIRM", "REJECT"]
    confirmed_fields: dict[str, str | None] | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_request(self):
        if self.action == "REJECT" and len((self.reason or "").strip()) < 3:
            raise ValueError("Provide a short reason when rejecting a document")
        if self.action == "CONFIRM" and not isinstance(self.confirmed_fields, dict):
            raise ValueError("Confirming a document requires the fields checked by a person")
        return self


def _safe_filename(value: str) -> str:
    decoded = unquote(str(value or ""))
    decoded = decoded.replace("\\", "/")
    base = PurePosixPath(decoded).name
    base = "".join(char for char in base if char.isprintable() and ord(char) >= 32).strip()
    base = re.sub(r"\s+", " ", base)[:180].strip(" .")
    if not base or base in {".", ".."}:
        raise HTTPException(status_code=422, detail={"code": "DOCUMENT_FILENAME_INVALID", "message": "Choose a document with a valid file name."})
    return base


async def _read_bounded_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid content length") from exc
        if declared <= 0:
            raise HTTPException(status_code=422, detail="The selected file is empty")
        if declared > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail={"code": "DOCUMENT_TOO_LARGE", "message": "Choose a file no larger than 10 MB."})

    parts: list[bytes] = []
    seen = 0
    async for chunk in request.stream():
        seen += len(chunk)
        if seen > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail={"code": "DOCUMENT_TOO_LARGE", "message": "Choose a file no larger than 10 MB."})
        parts.append(chunk)
    if seen <= 0:
        raise HTTPException(status_code=422, detail="The selected file is empty")
    return b"".join(parts)


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _document_out(row: Any, *, include_text_preview: bool = False) -> dict[str, Any]:
    value = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    candidate = _json_obj(value.get("candidate_fields"))
    confirmed = _json_obj(value.get("confirmed_fields")) if value.get("confirmed_fields") is not None else None
    created = value.get("created_at")
    updated = value.get("updated_at")
    reviewed = value.get("reviewed_at")
    out: dict[str, Any] = {
        "id": str(value["id"]),
        "branch_id": str(value["branch_id"]),
        "document_type": value["document_type"],
        "status": value["status"],
        "original_filename": value["original_filename"],
        "content_type": value["content_type"],
        "size_bytes": int(value["size_bytes"]),
        "content_sha256": str(value["content_sha256"]).strip(),
        "extraction_status": value["extraction_status"],
        "extraction_method": value["extraction_method"],
        "candidate_fields": candidate,
        "confirmed_fields": confirmed,
        "review_reason": value.get("review_reason"),
        "created_at": created.isoformat() if isinstance(created, datetime) else str(created),
        "updated_at": updated.isoformat() if isinstance(updated, datetime) else str(updated),
        "reviewed_at": reviewed.isoformat() if isinstance(reviewed, datetime) else (str(reviewed) if reviewed else None),
        "can_review": value["status"] == "NEEDS_REVIEW",
        "original_file_available": True,
    }
    if include_text_preview:
        out["extracted_text_preview"] = str(value.get("extracted_text") or "")[:2500]
    return out


def _normalise_confirmed_fields(raw: dict[str, str | None] | None) -> dict[str, str | None]:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="Enter the fields you reviewed against the original document.")
    unknown = set(raw) - _ALLOWED_REVIEW_FIELDS
    if unknown:
        raise HTTPException(status_code=422, detail={"code": "DOCUMENT_FIELD_NOT_SUPPORTED", "message": "One or more fields are not supported for document review."})
    result: dict[str, str | None] = {}
    for key, value in raw.items():
        if value is None or not str(value).strip():
            result[key] = None
            continue
        clean = str(value).strip()
        if key in _TEXT_FIELDS:
            if len(clean) > 180 or any(ord(char) < 32 for char in clean):
                raise HTTPException(status_code=422, detail=f"The {key.replace('_', ' ')} field is too long or contains invalid characters.")
            result[key] = clean
        elif key == "currency_code":
            code = clean.upper()
            if not re.fullmatch(r"[A-Z]{3}", code):
                raise HTTPException(status_code=422, detail="Currency must be a three-letter code such as UGX.")
            result[key] = code
        elif key in _MONEY_FIELDS:
            amount = clean.replace(",", "")
            try:
                parsed = Decimal(amount)
            except InvalidOperation as exc:
                raise HTTPException(status_code=422, detail=f"Enter a valid amount for {key.replace('_', ' ')}.") from exc
            if not parsed.is_finite() or parsed < 0 or abs(parsed) >= Decimal("1000000000000000"):
                raise HTTPException(status_code=422, detail=f"The amount for {key.replace('_', ' ')} is outside the supported range.")
            result[key] = format(parsed.quantize(Decimal("0.01")), "f")
        elif key in _DATE_FIELDS:
            try:
                result[key] = date.fromisoformat(clean).isoformat()
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"Enter {key.replace('_', ' ')} as YYYY-MM-DD.") from exc
    return result


def _required_fields(document_type: str) -> tuple[str, ...]:
    return {
        "SUPPLIER_INVOICE": ("supplier_name", "invoice_number", "invoice_date", "currency_code", "total"),
        "EXPENSE_RECEIPT": ("invoice_date", "currency_code", "total"),
        "CUSTOMER_INVOICE": ("customer_name", "invoice_number", "invoice_date", "currency_code", "total"),
        "PURCHASE_ORDER": ("supplier_name", "purchase_order_number", "currency_code", "total"),
        "OTHER": (),
    }[document_type]


def _load_document(db: Any, *, tenant_id: UUID, user_id: UUID, document_id: UUID) -> dict[str, Any]:
    row = db.execute(text("""
        SELECT id, tenant_id, branch_id, document_type, status, original_filename,
               content_type, size_bytes, content_sha256, extraction_status, extraction_method,
               extracted_text, candidate_fields, confirmed_fields, review_reason,
               created_at, updated_at, reviewed_at
          FROM public.intelligence_documents
         WHERE tenant_id = :tenant_id AND id = :document_id
         LIMIT 1
    """), {"tenant_id": str(tenant_id), "document_id": str(document_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="This document was not found in the current workspace.")
    ensure_branch_access(db, tenant_id=tenant_id, user_id=user_id, branch_id=row["branch_id"])
    return dict(row)


@router.post("/intake")
async def intake_document(
    request: Request,
    document_type: str = Header(alias="X-Document-Type"),
    branch_id: UUID = Header(alias="X-Branch-ID"),
    filename: str = Header(alias="X-Document-Filename"),
    ctx=Depends(require_permission("intelligence.documents.intake")),
):
    """Store a bounded PDF/image and return local extraction candidates for review."""
    db, user_id, tenant_id, _session_id = ctx
    doc_type = document_type.strip().upper()
    if doc_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail={"code": "DOCUMENT_TYPE_UNSUPPORTED", "message": "Choose a supported document type."})
    ensure_branch_access(db, tenant_id=tenant_id, user_id=user_id, branch_id=branch_id)
    safe_name = _safe_filename(filename)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail={"code": "DOCUMENT_TYPE_UNSUPPORTED", "message": "Upload a PDF, JPG, PNG or WebP file."})
    content = await _read_bounded_body(request)
    digest = hashlib.sha256(content).hexdigest()
    existing = db.execute(text("""
        SELECT id, tenant_id, branch_id, document_type, status, original_filename,
               content_type, size_bytes, content_sha256, extraction_status, extraction_method,
               extracted_text, candidate_fields, confirmed_fields, review_reason,
               created_at, updated_at, reviewed_at
          FROM public.intelligence_documents
         WHERE tenant_id = :tenant_id AND branch_id = :branch_id AND content_sha256 = :digest
         LIMIT 1
    """), {"tenant_id": str(tenant_id), "branch_id": str(branch_id), "digest": digest}).mappings().first()
    if existing:
        result = _document_out(existing)
        result["duplicate"] = True
        return result

    try:
        extracted = extract_document(content, content_type, doc_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "DOCUMENT_EXTRACTION_INPUT_INVALID", "message": str(exc)}) from exc
    candidate_json = json.dumps(extracted["candidate_fields"], ensure_ascii=False, separators=(",", ":"))
    try:
        inserted = db.execute(text("""
            INSERT INTO public.intelligence_documents (
                tenant_id, branch_id, document_type, status, original_filename,
                content_type, size_bytes, content_sha256, content_bytes,
                extraction_status, extraction_method, extracted_text, candidate_fields,
                created_by_user_id
            ) VALUES (
                :tenant_id, :branch_id, :document_type, 'NEEDS_REVIEW', :filename,
                :content_type, :size_bytes, :digest, :content,
                :extraction_status, :extraction_method, :extracted_text, CAST(:candidate_fields AS jsonb),
                :user_id
            )
            RETURNING id
        """), {
            "tenant_id": str(tenant_id), "branch_id": str(branch_id), "document_type": doc_type,
            "filename": safe_name, "content_type": content_type, "size_bytes": len(content),
            "digest": digest, "content": content, "extraction_status": extracted["extraction_status"],
            "extraction_method": extracted["extraction_method"], "extracted_text": extracted["extracted_text"],
            "candidate_fields": candidate_json, "user_id": str(user_id),
        }).scalar_one()
        db.commit()
    except IntegrityError as exc:
        # The uniqueness constraint is the final arbiter across API replicas. If two
        # requests race on the same file hash, return the saved row instead of making
        # a duplicate or surfacing an opaque 500 response.
        db.rollback()
        duplicate = db.execute(text("""
            SELECT id, tenant_id, branch_id, document_type, status, original_filename,
                   content_type, size_bytes, content_sha256, extraction_status, extraction_method,
                   extracted_text, candidate_fields, confirmed_fields, review_reason,
                   created_at, updated_at, reviewed_at
              FROM public.intelligence_documents
             WHERE tenant_id = :tenant_id AND branch_id = :branch_id AND content_sha256 = :digest
             LIMIT 1
        """), {"tenant_id": str(tenant_id), "branch_id": str(branch_id), "digest": digest}).mappings().first()
        if not duplicate:
            logger.warning("intelligence_document_insert_conflict tenant_id=%s branch_id=%s", tenant_id, branch_id)
            raise HTTPException(status_code=409, detail={"code": "DOCUMENT_SAVE_CONFLICT", "message": "LEXA could not save this document yet. Please refresh the document list and try again."}) from exc
        result = _document_out(duplicate)
        result["duplicate"] = True
        return result
    logger.info("intelligence_document_intake document_id=%s tenant_id=%s type=%s bytes=%s extraction=%s", inserted, tenant_id, doc_type, len(content), extracted["extraction_status"])
    row = _load_document(db, tenant_id=tenant_id, user_id=user_id, document_id=UUID(str(inserted)))
    row["id"] = inserted
    result = _document_out(row)
    result["duplicate"] = False
    result["message"] = "Document saved for review. Extracted fields are unverified and no business transaction was created."
    return result


@router.get("")
def list_documents(
    limit: int = Query(default=30, ge=1, le=100),
    branch_id: UUID | None = None,
    status: Literal["NEEDS_REVIEW", "CONFIRMED", "REJECTED"] | None = None,
    ctx=Depends(require_permission("intelligence.documents.read")),
):
    db, user_id, tenant_id, _session_id = ctx
    assigned = assigned_branch_ids(db, tenant_id=tenant_id, user_id=user_id)
    if branch_id is not None:
        ensure_branch_access(db, tenant_id=tenant_id, user_id=user_id, branch_id=branch_id)
        assigned = {branch_id}
    if not assigned:
        return {"items": [], "count": 0}
    where = ["tenant_id = :tenant_id", "branch_id = ANY(:branch_ids)"]
    params: dict[str, Any] = {"tenant_id": str(tenant_id), "branch_ids": list(assigned), "limit": limit}
    if status:
        where.append("status = :status")
        params["status"] = status
    rows = db.execute(text(f"""
        SELECT id, tenant_id, branch_id, document_type, status, original_filename,
               content_type, size_bytes, content_sha256, extraction_status, extraction_method,
               candidate_fields, confirmed_fields, review_reason, created_at, updated_at, reviewed_at
          FROM public.intelligence_documents
         WHERE {' AND '.join(where)}
         ORDER BY created_at DESC, id DESC
         LIMIT :limit
    """), params).mappings().all()
    items = [_document_out(row) for row in rows]
    return {"items": items, "count": len(items)}


@router.get("/{document_id}")
def get_document(document_id: UUID, ctx=Depends(require_permission("intelligence.documents.read"))):
    db, user_id, tenant_id, _session_id = ctx
    row = _load_document(db, tenant_id=tenant_id, user_id=user_id, document_id=document_id)
    return _document_out(row, include_text_preview=True)


@router.get("/{document_id}/file")
def get_document_file(document_id: UUID, ctx=Depends(require_permission("intelligence.documents.read"))):
    db, user_id, tenant_id, _session_id = ctx
    row = _load_document(db, tenant_id=tenant_id, user_id=user_id, document_id=document_id)
    content = db.execute(text("""
        SELECT content_bytes FROM public.intelligence_documents
         WHERE tenant_id = :tenant_id AND id = :document_id
         LIMIT 1
    """), {"tenant_id": str(tenant_id), "document_id": str(document_id)}).scalar_one_or_none()
    if content is None:
        raise HTTPException(status_code=404, detail="The original document could not be found.")
    return Response(
        content=bytes(content),
        media_type=row["content_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row['original_filename'], safe='')}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{document_id}/review")
def review_document(
    document_id: UUID,
    body: DocumentReviewRequest,
    ctx=Depends(require_permission("intelligence.documents.review")),
):
    """Record a human decision. Confirmation prepares a handoff, not a ledger write."""
    db, user_id, tenant_id, _session_id = ctx
    row = _load_document(db, tenant_id=tenant_id, user_id=user_id, document_id=document_id)
    if row["status"] != "NEEDS_REVIEW":
        raise HTTPException(status_code=409, detail={"code": "DOCUMENT_ALREADY_REVIEWED", "message": "This document has already been reviewed and cannot be changed through this action."})

    confirmed: dict[str, str | None] | None = None
    if body.action == "CONFIRM":
        confirmed = _normalise_confirmed_fields(body.confirmed_fields)
        missing = [key.replace("_", " ") for key in _required_fields(row["document_type"]) if not confirmed.get(key)]
        if missing:
            raise HTTPException(status_code=422, detail={"code": "DOCUMENT_REQUIRED_FIELDS_MISSING", "message": "Check these required fields before confirming: " + ", ".join(missing) + "."})
        status = "CONFIRMED"
        fingerprint = hashlib.sha256(json.dumps(confirmed, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    else:
        confirmed = None
        status = "REJECTED"
        fingerprint = None

    reason = (body.reason or "").strip() or None
    db.execute(text("""
        UPDATE public.intelligence_documents
           SET status=:status, confirmed_fields=CAST(:confirmed_fields AS jsonb),
               reviewed_by_user_id=:user_id, reviewed_at=now(), review_reason=:reason,
               updated_at=now()
         WHERE tenant_id=:tenant_id AND branch_id=:branch_id AND id=:document_id AND status='NEEDS_REVIEW'
    """), {
        "status": status, "confirmed_fields": json.dumps(confirmed, separators=(",", ":")) if confirmed is not None else None,
        "user_id": str(user_id), "reason": reason, "tenant_id": str(tenant_id),
        "branch_id": str(row["branch_id"]), "document_id": str(document_id),
    })
    db.execute(text("""
        INSERT INTO public.intelligence_document_reviews (
            tenant_id, branch_id, document_id, action, reason, fields_fingerprint, actor_user_id
        ) VALUES (:tenant_id, :branch_id, :document_id, :action, :reason, :fingerprint, :user_id)
    """), {
        "tenant_id": str(tenant_id), "branch_id": str(row["branch_id"]),
        "document_id": str(document_id), "action": body.action, "reason": reason,
        "fingerprint": fingerprint, "user_id": str(user_id),
    })
    db.commit()
    logger.info("intelligence_document_review document_id=%s tenant_id=%s action=%s", document_id, tenant_id, body.action)
    refreshed = _load_document(db, tenant_id=tenant_id, user_id=user_id, document_id=document_id)
    result = _document_out(refreshed, include_text_preview=True)
    result["transaction_created"] = False
    result["next_step"] = (
        "Review the confirmed values and use the normal Purchasing or Finance workflow to create a draft transaction. LEXA has not created or posted a business record."
        if body.action == "CONFIRM" else "This document was rejected. No business transaction was created."
    )
    return result
