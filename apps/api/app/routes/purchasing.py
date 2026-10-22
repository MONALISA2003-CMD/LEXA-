"""Phase 7 supplier and purchasing workflows.

All writes are tenant-scoped, audited, idempotent where externally retryable, and
use the authoritative inventory ledger when a receipt or supplier return is posted.
Supplier bills/payments create immutable supplier-ledger entries only on posting.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..branch_access import assigned_branch_ids, ensure_branch_access, ensure_location_access, require_full_branch_scope
from ..catalog import emit_event, finish_idempotency, write_audit, begin_idempotency
from ..dependencies import require_permission
from ..inventory import post_ledger, tenant_variant
from ..purchasing_rules import (
    allocate_landed_cost,
    line_amounts,
    money,
    order_status_from_receipts,
    validate_payment_allocations,
)

router = APIRouter(prefix="/purchasing", tags=["purchasing"])
ZERO = Decimal("0")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupplierCreate(Strict):
    name: str = Field(min_length=2, max_length=250)
    code: str | None = Field(default=None, min_length=2, max_length=40)
    legal_name: str | None = Field(default=None, max_length=250)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    currency_code: str = Field(default="UGX", pattern=r"^[A-Za-z]{3}$")
    payment_terms_days: int = Field(default=0, ge=0, le=3650)
    default_receiving_location_id: UUID | None = None
    tax_number: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class SupplierUpdate(Strict):
    name: str | None = Field(default=None, min_length=2, max_length=250)
    legal_name: str | None = Field(default=None, max_length=250)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    currency_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    default_receiving_location_id: UUID | None = None
    tax_number: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, pattern=r"^(ACTIVE|INACTIVE|ARCHIVED)$")

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class SupplierCostCreate(Strict):
    variant_id: UUID
    unit_cost: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    minimum_quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=20, decimal_places=6)
    currency_code: str = Field(default="UGX", pattern=r"^[A-Za-z]{3}$")
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PurchaseOrderLineIn(Strict):
    variant_id: UUID
    ordered_quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit_cost: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    tax_rate: Decimal = Field(default=ZERO, ge=0, le=100, max_digits=6, decimal_places=3)
    description: str | None = Field(default=None, max_length=300)


class PurchaseOrderCreate(Strict):
    supplier_party_id: UUID
    branch_id: UUID
    receiving_location_id: UUID
    order_date: date = Field(default_factory=date.today)
    expected_date: date | None = None
    currency_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[PurchaseOrderLineIn] = Field(min_length=1, max_length=200)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def validate_lines(self):
        variants = [line.variant_id for line in self.lines]
        if len(variants) != len(set(variants)):
            raise ValueError("A purchase order may only contain one line per product variant")
        if self.expected_date and self.expected_date < self.order_date:
            raise ValueError("Expected date cannot be before order date")
        return self


class ReceiptLineIn(Strict):
    purchase_order_line_id: UUID
    received_quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit_cost: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=6)
    variance_reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class LandedCostIn(Strict):
    cost_code: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=2, max_length=240)
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    currency_code: str = Field(pattern=r"^[A-Za-z]{3}$")
    allocation_method: str = Field(default="BY_VALUE", pattern=r"^(BY_VALUE|BY_QUANTITY|EQUALLY)$")
    reference: str | None = Field(default=None, max_length=120)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ReceiptCreate(Strict):
    received_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[ReceiptLineIn] = Field(min_length=1, max_length=200)
    landed_costs: list[LandedCostIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_lines(self):
        ids = [line.purchase_order_line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("A receipt may only include a purchase-order line once")
        return self


class PurchaseReturnLineIn(Strict):
    purchase_receipt_line_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    reason: str | None = Field(default=None, max_length=500)


class PurchaseReturnCreate(Strict):
    purchase_receipt_id: UUID
    reason: str = Field(min_length=2, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[PurchaseReturnLineIn] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_lines(self):
        ids = [line.purchase_receipt_line_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("A supplier return may only include a receipt line once")
        return self


class SupplierBillCreate(Strict):
    supplier_party_id: UUID
    bill_number: str = Field(min_length=1, max_length=100)
    bill_date: date
    due_date: date | None = None
    currency_code: str = Field(default="UGX", pattern=r"^[A-Za-z]{3}$")
    subtotal: Decimal = Field(ge=0, max_digits=20, decimal_places=2)
    tax_amount: Decimal = Field(default=ZERO, ge=0, max_digits=20, decimal_places=2)
    other_charges: Decimal = Field(default=ZERO, ge=0, max_digits=20, decimal_places=2)
    purchase_order_id: UUID | None = None
    purchase_receipt_id: UUID | None = None
    supplier_reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_total(self):
        if self.subtotal + self.tax_amount + self.other_charges <= ZERO:
            raise ValueError("Supplier bill total must be positive")
        if self.due_date and self.due_date < self.bill_date:
            raise ValueError("Due date cannot be before bill date")
        return self


class SupplierBillVarianceOverride(Strict):
    reason: str = Field(min_length=5, max_length=1000)


class PaymentAllocationIn(Strict):
    bill_id: UUID
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)


class SupplierPaymentCreate(Strict):
    supplier_party_id: UUID
    payment_number: str = Field(min_length=1, max_length=100)
    payment_date: date = Field(default_factory=date.today)
    currency_code: str = Field(default="UGX", pattern=r"^[A-Za-z]{3}$")
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    payment_method: str = Field(pattern=r"^(CASH|BANK_TRANSFER|MOBILE_MONEY|CHEQUE|CARD|OTHER)$")
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)
    allocations: list[PaymentAllocationIn] = Field(default_factory=list, max_length=200)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_allocations(self):
        # Keep the API model and route-level validation on one shared rule so
        # duplicates/over-allocation are rejected before any database mutation.
        validate_payment_allocations(
            self.amount,
            [{"bill_id": row.bill_id, "amount": row.amount} for row in self.allocations],
        )
        return self


def _mapping(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _one(db: Session, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    return _mapping(db.execute(text(sql), params).mappings().first())


def _many(db: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(text(sql), params).mappings().all()]


def _commit(db: Session, idem_row, response: dict[str, Any], resource_type: str, resource_id: UUID):
    if idem_row is not None and not isinstance(idem_row, tuple):
        finish_idempotency(db, idem_row, status_code=200, response_body=jsonable_encoder(response), resource_type=resource_type, resource_id=resource_id)
    db.commit()
    return response


def _idempotency(db, tenant_id: UUID, operation: str, key: str | None, payload: Any):
    try:
        return begin_idempotency(db, tenant_id=tenant_id, operation_type=operation, key=key, payload=payload)
    except Exception as exc:
        # CatalogValidation is deliberately converted to the same safe client response
        # as other bad idempotency keys; never disclose database details.
        message = str(exc)
        if "different request" in message:
            raise HTTPException(409, message) from exc
        raise HTTPException(400, message or "Invalid idempotency key") from exc


def _replay(replay):
    return replay[1] if replay else None


def _supplier(db: Session, tenant_id: UUID, party_id: UUID, active: bool = True) -> dict[str, Any]:
    row = _one(db, """
      SELECT p.id AS supplier_party_id,p.display_name AS name,p.legal_name,p.email,p.phone,p.status AS party_status,
             sp.currency_code,sp.payment_terms_days,sp.default_receiving_location_id,sp.tax_number,sp.notes,sp.status AS profile_status,
             s.id AS supplier_id,s.code
      FROM public.parties p
      JOIN public.supplier_profiles sp ON sp.tenant_id=p.tenant_id AND sp.supplier_party_id=p.id
      LEFT JOIN public.suppliers s ON s.tenant_id=p.tenant_id AND s.supplier_party_id=p.id AND s.status <> 'ARCHIVED'
      WHERE p.tenant_id=:tenant_id AND p.id=:party_id AND p.deleted_at IS NULL
    """, {"tenant_id": str(tenant_id), "party_id": str(party_id)})
    if not row or (active and (row["party_status"] != "ACTIVE" or row["profile_status"] != "ACTIVE")):
        raise HTTPException(404, "Supplier was not found or is inactive")
    return row


def _order(db: Session, tenant_id: UUID, order_id: UUID, lock: bool = False) -> dict[str, Any]:
    row = _one(db, """
      SELECT po.*,p.display_name AS supplier_name,l.name AS receiving_location_name,b.name AS branch_name
      FROM public.purchase_orders po
      JOIN public.parties p ON p.tenant_id=po.tenant_id AND p.id=po.supplier_party_id
      JOIN public.locations l ON l.tenant_id=po.tenant_id AND l.id=po.receiving_location_id
      JOIN public.branches b ON b.tenant_id=po.tenant_id AND b.id=po.branch_id
      WHERE po.tenant_id=:tenant_id AND po.id=:order_id
    """, {"tenant_id": str(tenant_id), "order_id": str(order_id)})
    if not row:
        raise HTTPException(404, "Purchase order not found")
    if lock:
        db.execute(text("SELECT id FROM public.purchase_orders WHERE tenant_id=:tenant_id AND id=:id FOR UPDATE"), {"tenant_id": str(tenant_id), "id": str(order_id)}).first()
        row = _one(db, "SELECT po.*,p.display_name AS supplier_name,l.name AS receiving_location_name,b.name AS branch_name FROM public.purchase_orders po JOIN public.parties p ON p.tenant_id=po.tenant_id AND p.id=po.supplier_party_id JOIN public.locations l ON l.tenant_id=po.tenant_id AND l.id=po.receiving_location_id JOIN public.branches b ON b.tenant_id=po.tenant_id AND b.id=po.branch_id WHERE po.tenant_id=:tenant_id AND po.id=:order_id", {"tenant_id": str(tenant_id), "order_id": str(order_id)})
    return row


def _order_lines(db: Session, tenant_id: UUID, order_id: UUID) -> list[dict[str, Any]]:
    return _many(db, """
      SELECT pol.*,pv.sku,pv.name AS variant_name,pr.name AS product_name
      FROM public.purchase_order_lines pol
      JOIN public.product_variants pv ON pv.tenant_id=pol.tenant_id AND pv.id=pol.variant_id
      JOIN public.products pr ON pr.tenant_id=pv.tenant_id AND pr.id=pv.product_id
      WHERE pol.tenant_id=:tenant_id AND pol.purchase_order_id=:order_id ORDER BY pol.line_number
    """, {"tenant_id": str(tenant_id), "order_id": str(order_id)})



def _many_branch_scoped(
    db: Session, sql: str, params: dict[str, Any], *, tenant_id: UUID, user_id: UUID, branch_column: str
) -> list[dict[str, Any]]:
    """Read records tied to a branch, limited to the caller's active branch assignments."""
    branch_ids = assigned_branch_ids(db, tenant_id=tenant_id, user_id=user_id)
    if not branch_ids:
        # Gives a useful setup/access response rather than an unexplained empty list.
        require_full_branch_scope(db, tenant_id=tenant_id, user_id=user_id)
        return []
    if "__BRANCH_SCOPE__" not in sql:
        raise ValueError("Branch-scoped query is missing its branch filter")
    sql = sql.replace("__BRANCH_SCOPE__", f"{branch_column} IN :accessible_branches")
    statement = text(sql).bindparams(bindparam("accessible_branches", expanding=True))
    scoped_params = {**params, "accessible_branches": [str(branch_id) for branch_id in sorted(branch_ids, key=str)]}
    return [dict(row) for row in db.execute(statement, scoped_params).mappings().all()]


def _ensure_order_access(db: Session, *, tenant_id: UUID, user_id: UUID, order_id: UUID, lock: bool = False) -> dict[str, Any]:
    order = _order(db, tenant_id, order_id, lock=lock)
    order_branch = UUID(str(order["branch_id"]))
    ensure_branch_access(db, tenant_id=tenant_id, user_id=user_id, branch_id=order_branch)
    location_branch = ensure_location_access(
        db, tenant_id=tenant_id, user_id=user_id, location_id=UUID(str(order["receiving_location_id"]))
    )
    if location_branch != order_branch:
        raise HTTPException(409, detail={
            "code": "PURCHASE_LOCATION_MISMATCH",
            "message": "This order is linked to a different stock location. Ask the business owner to correct the order before continuing.",
        })
    return order



def _ensure_receipt_location_matches_order(receipt: dict[str, Any], order: dict[str, Any]) -> None:
    """Prevent a receipt from moving stock into a different location than its order."""
    if UUID(str(receipt["receiving_location_id"])) != UUID(str(order["receiving_location_id"])):
        raise HTTPException(409, detail={
            "code": "PURCHASE_RECEIPT_LOCATION_MISMATCH",
            "message": "This delivery is linked to a different stock location. Ask the business owner to correct it before continuing.",
        })

def _require_workspace_finance_scope(db: Session, *, tenant_id: UUID, user_id: UUID) -> None:
    """Supplier bills/payments and their ledger are workspace-wide until entries carry a branch."""
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=user_id)

def _write_status(db: Session, tenant_id: UUID, actor: UUID, order_id: UUID, before: str | None, after: str, reason: str | None = None):
    db.execute(text("INSERT INTO public.purchase_order_status_history(tenant_id,purchase_order_id,from_status,to_status,actor_user_id,reason) VALUES(:tenant_id,:order_id,:before,:after,:actor,:reason)"), {"tenant_id": str(tenant_id), "order_id": str(order_id), "before": before, "after": after, "actor": str(actor), "reason": reason})


def _audit(db, tenant_id, actor, action, target_type, target_id, event, payload):
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action=action, target_type=target_type, target_id=target_id)
    emit_event(db, tenant_id=tenant_id, event_type=event, aggregate_type=target_type, aggregate_id=target_id, actor_user_id=actor, payload=payload)


def _receipt_lines(db: Session, tenant_id: UUID, receipt_id: UUID) -> list[dict[str, Any]]:
    return _many(db, "SELECT prl.*,pol.purchase_order_id,pol.line_number,pol.ordered_quantity,pol.received_quantity AS already_received,pv.sku,pv.name AS variant_name,pr.name AS product_name FROM public.purchase_receipt_lines prl JOIN public.purchase_order_lines pol ON pol.tenant_id=prl.tenant_id AND pol.id=prl.purchase_order_line_id JOIN public.product_variants pv ON pv.tenant_id=prl.tenant_id AND pv.id=prl.variant_id JOIN public.products pr ON pr.tenant_id=pv.tenant_id AND pr.id=pv.product_id WHERE prl.tenant_id=:tenant_id AND prl.receipt_id=:receipt_id ORDER BY pol.line_number", {"tenant_id": str(tenant_id), "receipt_id": str(receipt_id)})


@router.get("/summary")
def purchasing_summary(ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    # Supplier totals are tenant-wide until the ledger is branch-attributed.
    # Fail closed rather than expose another branch's obligations to a partial-scope user.
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor)
    # Never add balances in different currencies. Return a separate subtotal per currency.
    return _one(db, """
      SELECT (SELECT count(*) FROM public.supplier_profiles sp WHERE sp.tenant_id=:t AND sp.status='ACTIVE') AS active_suppliers,
             (SELECT count(*) FROM public.purchase_orders po WHERE po.tenant_id=:t AND po.status IN ('SUBMITTED','OPEN','PARTIALLY_RECEIVED')) AS open_purchase_orders,
             (SELECT count(*) FROM public.purchase_receipts r WHERE r.tenant_id=:t AND r.status='DRAFT') AS draft_receipts,
             (SELECT count(*) FROM public.purchase_returns r WHERE r.tenant_id=:t AND r.status IN ('REQUESTED','APPROVED')) AS pending_supplier_returns,
             (SELECT count(*) FROM public.supplier_bills b WHERE b.tenant_id=:t AND b.status='POSTED' AND b.due_date<CURRENT_DATE) AS overdue_supplier_bills,
             (SELECT coalesce(jsonb_agg(jsonb_build_object(
                 'currency_code',x.currency_code,
                 'net_balance',x.net_balance,
                 'payable',greatest(x.net_balance,0),
                 'supplier_credit',greatest(-x.net_balance,0)
               ) ORDER BY x.currency_code),'[]'::jsonb)
              FROM (SELECT e.currency_code, sum(e.debit_amount-e.credit_amount) AS net_balance
                    FROM public.supplier_ledger_entries e WHERE e.tenant_id=:t GROUP BY e.currency_code) x) AS supplier_balances_by_currency
    """, {"t": str(tenant_id)}) or {}


@router.get("/suppliers")
def list_suppliers(q: str | None = None, status: str = Query("ACTIVE", pattern=r"^(ACTIVE|INACTIVE|ARCHIVED|ALL)$"), limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    query = """
      SELECT p.id AS supplier_party_id,p.display_name AS name,p.legal_name,p.email,p.phone,p.status AS party_status,
             sp.currency_code,sp.payment_terms_days,sp.default_receiving_location_id,sp.tax_number,sp.notes,sp.status AS profile_status,
             sp.created_at,sp.updated_at,s.id AS supplier_id,s.code,
             (SELECT coalesce(sum(e.debit_amount-e.credit_amount),0) FROM public.supplier_ledger_entries e WHERE e.tenant_id=sp.tenant_id AND e.supplier_party_id=sp.supplier_party_id AND e.currency_code=sp.currency_code) AS net_balance
      FROM public.supplier_profiles sp JOIN public.parties p ON p.tenant_id=sp.tenant_id AND p.id=sp.supplier_party_id
      LEFT JOIN public.suppliers s ON s.tenant_id=sp.tenant_id AND s.supplier_party_id=sp.supplier_party_id AND s.status<>'ARCHIVED'
      WHERE sp.tenant_id=:t AND (:status='ALL' OR sp.status=:status) AND (:q IS NULL OR p.display_name ILIKE :like OR p.email ILIKE :like OR s.code ILIKE :like)
      ORDER BY p.display_name LIMIT :limit
    """
    return _many(db, query, {"t": str(tenant_id), "status": status, "q": q, "like": f"%{q.strip()}%" if q and q.strip() else None, "limit": limit})


@router.post("/suppliers")
def create_supplier(body: SupplierCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    payload = body.model_dump(mode="json")
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier.create", idempotency_key, payload)
    if replay: return replay[1]
    if body.default_receiving_location_id:
        ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=body.default_receiving_location_id)
    name = body.name.strip()
    code = (body.code or "SUP-" + uuid4().hex[:8]).strip().upper()
    party_id, supplier_id = uuid4(), uuid4()
    try:
        db.execute(text("INSERT INTO public.parties(id,tenant_id,party_type,display_name,legal_name,email,phone,status,metadata) VALUES(:id,:t,'ORGANIZATION',:name,:legal,:email,:phone,'ACTIVE','{}'::jsonb)"), {"id": str(party_id), "t": str(tenant_id), "name": name, "legal": body.legal_name.strip() if body.legal_name else None, "email": body.email.strip().lower() if body.email else None, "phone": body.phone.strip() if body.phone else None})
        db.execute(text("INSERT INTO public.party_roles(tenant_id,party_id,role_type,status,metadata) VALUES(:t,:p,'SUPPLIER','ACTIVE','{}'::jsonb) ON CONFLICT DO NOTHING"), {"t": str(tenant_id), "p": str(party_id)})
        db.execute(text("INSERT INTO public.supplier_profiles(tenant_id,supplier_party_id,currency_code,payment_terms_days,default_receiving_location_id,tax_number,notes,status) VALUES(:t,:p,:cc,:terms,:loc,:tax,:notes,'ACTIVE')"), {"t": str(tenant_id), "p": str(party_id), "cc": body.currency_code, "terms": body.payment_terms_days, "loc": str(body.default_receiving_location_id) if body.default_receiving_location_id else None, "tax": body.tax_number, "notes": body.notes})
        db.execute(text("INSERT INTO public.suppliers(id,tenant_id,name,code,email,phone,currency,status,supplier_party_id) VALUES(:id,:t,:name,:code,:email,:phone,:cc,'ACTIVE',:p)"), {"id": str(supplier_id), "t": str(tenant_id), "name": name, "code": code, "email": body.email.strip().lower() if body.email else None, "phone": body.phone.strip() if body.phone else None, "cc": body.currency_code, "p": str(party_id)})
    except Exception as exc:
        db.rollback()
        # Never leak raw constraint/SQL details to the browser.
        raise HTTPException(409, "Supplier code or identity conflicts with an existing record") from exc
    response = _supplier(db, tenant_id, party_id, active=False)
    response["supplier_party_id"] = str(party_id); response["supplier_id"] = str(supplier_id)
    _audit(db, tenant_id, actor, "purchasing.supplier.created", "supplier", party_id, "purchasing.supplier.created.v1", {"supplier_party_id": str(party_id), "code": code})
    return _commit(db, idem, response, "supplier", party_id)


@router.patch("/suppliers/{supplier_party_id}")
def update_supplier(supplier_party_id: UUID, body: SupplierUpdate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    payload = {"supplier_party_id": str(supplier_party_id), **body.model_dump(exclude_unset=True, mode="json")}
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier.update", idempotency_key, payload)
    if replay: return replay[1]
    current = _supplier(db, tenant_id, supplier_party_id, active=False)
    values = body.model_dump(exclude_unset=True)
    if not values: return _commit(db, idem, current, "supplier", supplier_party_id)
    if "default_receiving_location_id" in values and values["default_receiving_location_id"]:
        ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=values["default_receiving_location_id"])
    if values.get("currency_code") and values["currency_code"].upper() != current["currency_code"]:
        used = db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM public.purchase_orders WHERE tenant_id=:t AND supplier_party_id=:p)
              OR EXISTS(SELECT 1 FROM public.supplier_bills WHERE tenant_id=:t AND supplier_party_id=:p)
              OR EXISTS(SELECT 1 FROM public.supplier_payments WHERE tenant_id=:t AND supplier_party_id=:p)
              OR EXISTS(SELECT 1 FROM public.supplier_ledger_entries WHERE tenant_id=:t AND supplier_party_id=:p)
              OR EXISTS(SELECT 1 FROM public.supplier_variant_costs WHERE tenant_id=:t AND supplier_party_id=:p)
        """), {"t": str(tenant_id), "p": str(supplier_party_id)}).scalar_one()
        if used: raise HTTPException(409, "Supplier currency is locked after purchasing activity; use an approved FX/revaluation workflow")
    if values.get("status") == "ARCHIVED":
        used = db.execute(text("""
          SELECT EXISTS(SELECT 1 FROM public.purchase_orders WHERE tenant_id=:t AND supplier_party_id=:p AND status NOT IN ('CANCELLED','CLOSED'))
              OR EXISTS(SELECT 1 FROM public.purchase_returns r JOIN public.purchase_receipts pr ON pr.tenant_id=r.tenant_id AND pr.id=r.purchase_receipt_id AND r.receiving_location_id=pr.receiving_location_id JOIN public.purchase_orders po ON po.tenant_id=pr.tenant_id AND po.id=pr.purchase_order_id WHERE r.tenant_id=:t AND po.supplier_party_id=:p AND r.status IN ('REQUESTED','APPROVED'))
              OR EXISTS(SELECT 1 FROM public.supplier_bills WHERE tenant_id=:t AND supplier_party_id=:p AND status='DRAFT')
              OR EXISTS(SELECT 1 FROM public.supplier_payments WHERE tenant_id=:t AND supplier_party_id=:p AND status='DRAFT')
              OR EXISTS(SELECT 1 FROM public.supplier_ledger_entries WHERE tenant_id=:t AND supplier_party_id=:p
                        GROUP BY tenant_id,supplier_party_id,currency_code HAVING sum(debit_amount-credit_amount) <> 0)
        """), {"t": str(tenant_id), "p": str(supplier_party_id)}).scalar_one()
        if used: raise HTTPException(409, "Supplier has open purchasing work or a non-zero supplier balance and cannot be archived")
    party_fields = {k: values[k] for k in ("name", "legal_name", "email", "phone", "status") if k in values}
    profile_fields = {k: values[k] for k in ("currency_code", "payment_terms_days", "default_receiving_location_id", "tax_number", "notes", "status") if k in values}
    if party_fields.get("status") == "ARCHIVED":
        party_fields["status"] = "INACTIVE"
    if "name" in party_fields: party_fields["display_name"] = party_fields.pop("name")
    if "email" in party_fields and party_fields["email"]: party_fields["email"] = party_fields["email"].strip().lower()
    if "currency_code" in profile_fields and profile_fields["currency_code"]: profile_fields["currency_code"] = profile_fields["currency_code"].upper()
    if party_fields:
        assignments = ",".join(f"{column}=:{column}" for column in party_fields)
        db.execute(text(f"UPDATE public.parties SET {assignments},updated_at=now() WHERE tenant_id=:t AND id=:p"), party_fields | {"t": str(tenant_id), "p": str(supplier_party_id)})
    if profile_fields:
        assignments = ",".join(f"{column}=:{column}" for column in profile_fields)
        db.execute(text(f"UPDATE public.supplier_profiles SET {assignments},updated_at=now() WHERE tenant_id=:t AND supplier_party_id=:p"), profile_fields | {"t": str(tenant_id), "p": str(supplier_party_id)})
    sync = {k: values[k] for k in ("name", "email", "phone", "currency_code", "status") if k in values}
    if sync:
        columns = {"name": "name", "email": "email", "phone": "phone", "currency_code": "currency", "status": "status"}
        args = {columns[k]: (v.upper() if k == "currency_code" and v else v) for k, v in sync.items()}
        assignments = ",".join(f"{k}=:{k}" for k in args)
        db.execute(text(f"UPDATE public.suppliers SET {assignments},updated_at=now() WHERE tenant_id=:t AND supplier_party_id=:p"), args | {"t": str(tenant_id), "p": str(supplier_party_id)})
    _audit(db, tenant_id, actor, "purchasing.supplier.updated", "supplier", supplier_party_id, "purchasing.supplier.updated.v1", {"fields": sorted(values.keys())})
    response = _supplier(db, tenant_id, supplier_party_id, active=False)
    return _commit(db, idem, response, "supplier", supplier_party_id)


@router.get("/suppliers/{supplier_party_id}/costs")
def supplier_costs(supplier_party_id: UUID, variant_id: UUID | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    _supplier(db, tenant_id, supplier_party_id, active=False)
    return _many(db, """
      SELECT c.*,pv.sku,pv.name AS variant_name,pr.name AS product_name
      FROM public.supplier_variant_costs c JOIN public.product_variants pv ON pv.tenant_id=c.tenant_id AND pv.id=c.variant_id
      JOIN public.products pr ON pr.tenant_id=pv.tenant_id AND pr.id=pv.product_id
      WHERE c.tenant_id=:t AND c.supplier_party_id=:p AND (:variant_id IS NULL OR c.variant_id=:variant_id)
      ORDER BY c.effective_from DESC LIMIT :limit
    """, {"t": str(tenant_id), "p": str(supplier_party_id), "variant_id": str(variant_id) if variant_id else None, "limit": limit})


@router.post("/suppliers/{supplier_party_id}/costs")
def set_supplier_cost(supplier_party_id: UUID, body: SupplierCostCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier_cost.create", idempotency_key, {"supplier_party_id": str(supplier_party_id), **body.model_dump(mode="json")})
    if replay: return replay[1]
    supplier = _supplier(db, tenant_id, supplier_party_id)
    tenant_variant(db, tenant_id, body.variant_id)
    if body.currency_code != supplier["currency_code"]: raise HTTPException(422, "Supplier price currency must match the supplier currency; foreign-exchange purchasing is not enabled")
    now = datetime.now(timezone.utc)
    db.execute(text("UPDATE public.supplier_variant_costs SET effective_to=:now WHERE tenant_id=:t AND supplier_party_id=:p AND variant_id=:v AND effective_to IS NULL AND minimum_quantity=:min_qty AND currency_code=:cc"), {"now": now, "t": str(tenant_id), "p": str(supplier_party_id), "v": str(body.variant_id), "min_qty": body.minimum_quantity, "cc": body.currency_code})
    row = _one(db, "INSERT INTO public.supplier_variant_costs(tenant_id,supplier_party_id,variant_id,currency_code,unit_cost,minimum_quantity,effective_from) VALUES(:t,:p,:v,:cc,:cost,:min_qty,:now) RETURNING *", {"t": str(tenant_id), "p": str(supplier_party_id), "v": str(body.variant_id), "cc": body.currency_code, "cost": body.unit_cost, "min_qty": body.minimum_quantity, "now": now})
    _audit(db, tenant_id, actor, "purchasing.supplier_cost.created", "supplier_cost", row["id"], "purchasing.supplier_cost.created.v1", {"supplier_party_id": str(supplier_party_id), "variant_id": str(body.variant_id), "currency_code": body.currency_code})
    return _commit(db, idem, row, "supplier_cost", UUID(str(row["id"])))


@router.get("/purchase-orders")
def list_purchase_orders(status: str | None = None, supplier_party_id: UUID | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    return _many_branch_scoped(db, """
      SELECT po.*,p.display_name AS supplier_name,b.name AS branch_name,l.name AS receiving_location_name,
        (SELECT count(*) FROM public.purchase_order_lines pol WHERE pol.tenant_id=po.tenant_id AND pol.purchase_order_id=po.id) AS line_count,
        (SELECT coalesce(sum(pol.received_quantity),0) FROM public.purchase_order_lines pol WHERE pol.tenant_id=po.tenant_id AND pol.purchase_order_id=po.id) AS received_units
      FROM public.purchase_orders po JOIN public.parties p ON p.tenant_id=po.tenant_id AND p.id=po.supplier_party_id
      JOIN public.branches b ON b.tenant_id=po.tenant_id AND b.id=po.branch_id
      JOIN public.locations l ON l.tenant_id=po.tenant_id AND l.id=po.receiving_location_id
      JOIN public.warehouses wh ON wh.tenant_id=l.tenant_id AND wh.id=l.warehouse_id AND wh.branch_id=po.branch_id
      WHERE po.tenant_id=:t AND __BRANCH_SCOPE__ AND (:status IS NULL OR po.status=:status) AND (:supplier IS NULL OR po.supplier_party_id=:supplier)
      ORDER BY po.created_at DESC LIMIT :limit
    """, {"t": str(tenant_id), "status": status, "supplier": str(supplier_party_id) if supplier_party_id else None, "limit": limit}, tenant_id=tenant_id, user_id=actor, branch_column="po.branch_id")


@router.post("/purchase-orders")
def create_purchase_order(body: PurchaseOrderCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.manage"))):
    db, actor, tenant_id, _ = ctx
    payload = body.model_dump(mode="json")
    idem, replay = _idempotency(db, tenant_id, "purchasing.purchase_order.create", idempotency_key, payload)
    if replay: return replay[1]
    supplier = _supplier(db, tenant_id, body.supplier_party_id)
    currency = body.currency_code or supplier["currency_code"]
    if currency != supplier["currency_code"]: raise HTTPException(422, "Purchase order currency must match the supplier currency; FX is not enabled")
    location_branch = ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=body.receiving_location_id)
    if location_branch != body.branch_id: raise HTTPException(422, "Receiving location must belong to the selected branch")
    for line in body.lines: tenant_variant(db, tenant_id, line.variant_id)
    order_id = uuid4()
    po_number = f"PO-{date.today():%Y%m%d}-{order_id.hex[:8].upper()}"
    amounts = [line_amounts(line.ordered_quantity, line.unit_cost, line.tax_rate) for line in body.lines]
    subtotal, taxes = sum((x[0] for x in amounts), ZERO), sum((x[1] for x in amounts), ZERO)
    db.execute(text("INSERT INTO public.purchase_orders(id,tenant_id,po_number,supplier_party_id,branch_id,receiving_location_id,status,order_date,expected_date,currency_code,notes,subtotal,tax_amount,total,created_by) VALUES(:id,:t,:number,:supplier,:branch,:loc,'DRAFT',:order_date,:expected,:cc,:notes,:subtotal,:tax,:total,:actor)"), {"id": str(order_id), "t": str(tenant_id), "number": po_number, "supplier": str(body.supplier_party_id), "branch": str(body.branch_id), "loc": str(body.receiving_location_id), "order_date": body.order_date, "expected": body.expected_date, "cc": currency, "notes": body.notes, "subtotal": subtotal, "tax": taxes, "total": subtotal + taxes, "actor": str(actor)})
    for index, (line, amounts_line) in enumerate(zip(body.lines, amounts), start=1):
        line_subtotal, line_tax, line_total = amounts_line
        db.execute(text("INSERT INTO public.purchase_order_lines(tenant_id,purchase_order_id,line_number,variant_id,ordered_quantity,received_quantity,unit_cost,tax_rate,tax_amount,line_subtotal,line_total,description) VALUES(:t,:po,:n,:variant,:qty,0,:cost,:rate,:tax,:sub,:total,:description)"), {"t": str(tenant_id), "po": str(order_id), "n": index, "variant": str(line.variant_id), "qty": line.ordered_quantity, "cost": line.unit_cost, "rate": line.tax_rate, "tax": line_tax, "sub": line_subtotal, "total": line_total, "description": line.description})
    _write_status(db, tenant_id, actor, order_id, None, "DRAFT", "created")
    _audit(db, tenant_id, actor, "purchasing.purchase_order.created", "purchase_order", order_id, "purchasing.purchase_order.created.v1", {"po_number": po_number, "supplier_party_id": str(body.supplier_party_id), "total": str(subtotal + taxes)})
    response = {"id": str(order_id), "po_number": po_number, "status": "DRAFT", "currency_code": currency, "subtotal": str(subtotal), "tax_amount": str(taxes), "total": str(subtotal + taxes)}
    return _commit(db, idem, response, "purchase_order", order_id)


@router.get("/purchase-orders/{order_id}")
def get_purchase_order(order_id: UUID, ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    row = _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=order_id)
    row["lines"] = _order_lines(db, tenant_id, order_id)
    row["status_history"] = _many(db, "SELECT id,from_status,to_status,actor_user_id,reason,created_at FROM public.purchase_order_status_history WHERE tenant_id=:t AND purchase_order_id=:id ORDER BY created_at,id", {"t": str(tenant_id), "id": str(order_id)})
    row["receipts"] = _many(db, "SELECT id,receipt_number,status,received_at,posted_at,landed_cost_total FROM public.purchase_receipts WHERE tenant_id=:t AND purchase_order_id=:id ORDER BY created_at DESC", {"t": str(tenant_id), "id": str(order_id)})
    return row


def _transition_order(db: Session, tenant_id: UUID, actor: UUID, order_id: UUID, target: str, allowed: set[str], reason: str | None = None, idem_row=None):
    row = _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=order_id, lock=True)
    before = row["status"]
    if before not in allowed: raise HTTPException(409, f"Cannot move purchase order from {before} to {target}")
    db.execute(text("UPDATE public.purchase_orders SET status=:target,updated_at=now(),submitted_by=CASE WHEN :target='SUBMITTED' THEN :actor ELSE submitted_by END,submitted_at=CASE WHEN :target='SUBMITTED' THEN now() ELSE submitted_at END,approved_by=CASE WHEN :target='OPEN' THEN :actor ELSE approved_by END,approved_at=CASE WHEN :target='OPEN' THEN now() ELSE approved_at END,cancelled_by=CASE WHEN :target='CANCELLED' THEN :actor ELSE cancelled_by END,cancelled_at=CASE WHEN :target='CANCELLED' THEN now() ELSE cancelled_at END,closed_by=CASE WHEN :target='CLOSED' THEN :actor ELSE closed_by END,closed_at=CASE WHEN :target='CLOSED' THEN now() ELSE closed_at END WHERE tenant_id=:t AND id=:id"), {"target": target, "actor": str(actor), "t": str(tenant_id), "id": str(order_id)})
    _write_status(db, tenant_id, actor, order_id, before, target, reason)
    _audit(db, tenant_id, actor, f"purchasing.purchase_order.{target.lower()}", "purchase_order", order_id, f"purchasing.purchase_order.{target.lower()}.v1", {"from_status": before, "to_status": target, "reason": reason})
    response = {"id": str(order_id), "status": target}
    return _commit(db, idem_row, response, "purchase_order", order_id)


def _transition_idem(db, tenant_id: UUID, order_id: UUID, operation: str, reason: str | None, key: str | None):
    idem, replay = _idempotency(db, tenant_id, f"purchasing.purchase_order.{operation}", key, {"order_id": str(order_id), "reason": reason})
    if replay: return idem, replay[1]
    return idem, None


@router.post("/purchase-orders/{order_id}/submit")
def submit_purchase_order(order_id: UUID, body: dict[str, Any] | None = None, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.manage"))):
    db, actor, tenant_id, _ = ctx
    reason = (body or {}).get("reason")
    idem, replay = _transition_idem(db, tenant_id, order_id, "submit", reason, idempotency_key)
    if replay: return replay[1]
    if not _order_lines(db, tenant_id, order_id): raise HTTPException(422, "Purchase order must contain lines before submission")
    return _transition_order(db, tenant_id, actor, order_id, "SUBMITTED", {"DRAFT"}, reason, idem)


@router.post("/purchase-orders/{order_id}/approve")
def approve_purchase_order(order_id: UUID, body: dict[str, Any] | None = None, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.approve"))):
    db, actor, tenant_id, _ = ctx
    reason = (body or {}).get("reason")
    idem, replay = _transition_idem(db, tenant_id, order_id, "approve", reason, idempotency_key)
    if replay: return replay[1]
    return _transition_order(db, tenant_id, actor, order_id, "OPEN", {"SUBMITTED"}, reason, idem)


@router.post("/purchase-orders/{order_id}/cancel")
def cancel_purchase_order(order_id: UUID, body: dict[str, Any] | None = None, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.manage"))):
    db, actor, tenant_id, _ = ctx
    reason = (body or {}).get("reason")
    idem, replay = _transition_idem(db, tenant_id, order_id, "cancel", reason, idempotency_key)
    if replay: return replay[1]
    received = db.execute(text("SELECT coalesce(sum(received_quantity),0) FROM public.purchase_order_lines WHERE tenant_id=:t AND purchase_order_id=:id"), {"t": str(tenant_id), "id": str(order_id)}).scalar_one()
    if Decimal(str(received or 0)) > ZERO: raise HTTPException(409, "A purchase order with received stock cannot be cancelled; close it or resolve the remaining quantities")
    return _transition_order(db, tenant_id, actor, order_id, "CANCELLED", {"DRAFT", "SUBMITTED", "OPEN"}, reason, idem)


@router.post("/purchase-orders/{order_id}/close")
def close_purchase_order(order_id: UUID, body: dict[str, Any] | None = None, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.approve"))):
    db, actor, tenant_id, _ = ctx
    reason = (body or {}).get("reason")
    idem, replay = _transition_idem(db, tenant_id, order_id, "close", reason, idempotency_key)
    if replay: return replay[1]
    return _transition_order(db, tenant_id, actor, order_id, "CLOSED", {"FULLY_RECEIVED", "PARTIALLY_RECEIVED", "OPEN"}, reason, idem)


@router.post("/purchase-orders/{order_id}/receipts")
def create_receipt(order_id: UUID, body: ReceiptCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.receive"))):
    db, actor, tenant_id, _ = ctx
    idem, replay = _idempotency(db, tenant_id, "purchasing.receipt.create", idempotency_key, body.model_dump(mode="json") | {"order_id": str(order_id)})
    if replay: return replay[1]
    order = _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=order_id, lock=True)
    if order["status"] not in {"OPEN", "PARTIALLY_RECEIVED"}: raise HTTPException(409, "Only an approved, not-yet-complete purchase order can receive stock")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=order["receiving_location_id"])
    line_rows = {UUID(str(row["id"])): row for row in _order_lines(db, tenant_id, order_id)}
    for line in body.lines:
        po_line = line_rows.get(line.purchase_order_line_id)
        if not po_line: raise HTTPException(422, "Receipt line is not part of this purchase order")
        remaining = Decimal(str(po_line["ordered_quantity"])) - Decimal(str(po_line["received_quantity"]))
        if line.received_quantity > remaining: raise HTTPException(409, f"Received quantity exceeds the remaining ordered quantity for {po_line['sku']}")
        if line.unit_cost is not None and line.unit_cost != Decimal(str(po_line["unit_cost"])) and not (line.variance_reason and line.variance_reason.strip()):
            raise HTTPException(422, "A cost difference from the purchase order requires a variance reason")
        if line.unit_cost is None and Decimal(str(po_line["unit_cost"])) <= ZERO: raise HTTPException(422, "Purchase order unit cost is invalid")
    if any(cost.currency_code != order["currency_code"] for cost in body.landed_costs): raise HTTPException(422, "Landed-cost currency must match the purchase order currency; FX conversion is not enabled")
    receipt_id = uuid4(); receipt_number = f"GRN-{date.today():%Y%m%d}-{receipt_id.hex[:8].upper()}"
    received_at = body.received_at or datetime.now(timezone.utc)
    db.execute(text("INSERT INTO public.purchase_receipts(id,tenant_id,receipt_number,purchase_order_id,receiving_location_id,status,received_at,notes,created_by) VALUES(:id,:t,:number,:po,:loc,'DRAFT',:received_at,:notes,:actor)"), {"id": str(receipt_id), "t": str(tenant_id), "number": receipt_number, "po": str(order_id), "loc": str(order["receiving_location_id"]), "received_at": received_at, "notes": body.notes, "actor": str(actor)})
    receipt_line_ids: dict[UUID, UUID] = {}
    for item in body.lines:
        source = line_rows[item.purchase_order_line_id]
        unit_cost = item.unit_cost or Decimal(str(source["unit_cost"]))
        line_id = uuid4(); receipt_line_ids[item.purchase_order_line_id] = line_id
        db.execute(text("INSERT INTO public.purchase_receipt_lines(id,tenant_id,receipt_id,purchase_order_line_id,variant_id,received_quantity,unit_cost,base_unit_cost,landed_cost_amount,variance_reason,notes) VALUES(:id,:t,:receipt,:po_line,:variant,:qty,:cost,:base,0,:reason,:notes)"), {"id": str(line_id), "t": str(tenant_id), "receipt": str(receipt_id), "po_line": str(item.purchase_order_line_id), "variant": str(source["variant_id"]), "qty": item.received_quantity, "cost": unit_cost, "base": unit_cost, "reason": item.variance_reason, "notes": item.notes})
    total_landed = ZERO
    for cost in body.landed_costs:
        cost_id = uuid4(); total_landed += cost.amount
        db.execute(text("INSERT INTO public.purchase_landed_costs(id,tenant_id,receipt_id,cost_code,description,amount,currency_code,allocation_method,reference,created_by) VALUES(:id,:t,:receipt,:code,:description,:amount,:cc,:method,:reference,:actor)"), {"id": str(cost_id), "t": str(tenant_id), "receipt": str(receipt_id), "code": cost.cost_code.strip().upper(), "description": cost.description.strip(), "amount": money(cost.amount), "cc": cost.currency_code, "method": cost.allocation_method, "reference": cost.reference, "actor": str(actor)})
    db.execute(text("UPDATE public.purchase_receipts SET landed_cost_total=:cost,landed_cost_allocation_method=:method WHERE tenant_id=:t AND id=:id"), {"cost": money(total_landed), "method": body.landed_costs[0].allocation_method if body.landed_costs else "BY_VALUE", "t": str(tenant_id), "id": str(receipt_id)})
    _audit(db, tenant_id, actor, "purchasing.receipt.created", "purchase_receipt", receipt_id, "purchasing.receipt.created.v1", {"receipt_number": receipt_number, "purchase_order_id": str(order_id), "line_count": len(body.lines), "landed_cost_total": str(money(total_landed))})
    response = {"id": str(receipt_id), "receipt_number": receipt_number, "status": "DRAFT", "purchase_order_id": str(order_id), "line_count": len(body.lines), "landed_cost_total": str(money(total_landed))}
    return _commit(db, idem, response, "purchase_receipt", receipt_id)


@router.get("/receipts")
def list_receipts(status: str | None = None, purchase_order_id: UUID | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    return _many_branch_scoped(db, "SELECT r.*,po.po_number,p.display_name AS supplier_name,l.name AS location_name,po.currency_code,(SELECT count(*) FROM public.purchase_receipt_lines rl WHERE rl.tenant_id=r.tenant_id AND rl.receipt_id=r.id) AS line_count FROM public.purchase_receipts r JOIN public.purchase_orders po ON po.tenant_id=r.tenant_id AND po.id=r.purchase_order_id AND r.receiving_location_id=po.receiving_location_id JOIN public.parties p ON p.tenant_id=po.tenant_id AND p.id=po.supplier_party_id JOIN public.locations l ON l.tenant_id=r.tenant_id AND l.id=r.receiving_location_id JOIN public.warehouses wh ON wh.tenant_id=l.tenant_id AND wh.id=l.warehouse_id AND wh.branch_id=po.branch_id WHERE r.tenant_id=:t AND __BRANCH_SCOPE__ AND (:status IS NULL OR r.status=:status) AND (:po IS NULL OR r.purchase_order_id=:po) ORDER BY r.created_at DESC LIMIT :limit", {"t": str(tenant_id), "status": status, "po": str(purchase_order_id) if purchase_order_id else None, "limit": limit}, tenant_id=tenant_id, user_id=actor, branch_column="po.branch_id")


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: UUID, ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    row = _one(db, "SELECT r.*,po.po_number,po.currency_code,po.supplier_party_id,po.branch_id,p.display_name AS supplier_name,l.name AS location_name FROM public.purchase_receipts r JOIN public.purchase_orders po ON po.tenant_id=r.tenant_id AND po.id=r.purchase_order_id AND r.receiving_location_id=po.receiving_location_id JOIN public.parties p ON p.tenant_id=po.tenant_id AND p.id=po.supplier_party_id JOIN public.locations l ON l.tenant_id=r.tenant_id AND l.id=r.receiving_location_id JOIN public.warehouses wh ON wh.tenant_id=l.tenant_id AND wh.id=l.warehouse_id AND wh.branch_id=po.branch_id WHERE r.tenant_id=:t AND r.id=:id", {"t": str(tenant_id), "id": str(receipt_id)})
    if not row: raise HTTPException(404, "Purchase receipt not found")
    ensure_branch_access(db, tenant_id=tenant_id, user_id=actor, branch_id=UUID(str(row["branch_id"])))
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=UUID(str(row["receiving_location_id"])))
    row["lines"] = _receipt_lines(db, tenant_id, receipt_id)
    row["landed_costs"] = _many(db, "SELECT * FROM public.purchase_landed_costs WHERE tenant_id=:t AND receipt_id=:id ORDER BY created_at,id", {"t": str(tenant_id), "id": str(receipt_id)})
    row["allocations"] = _many(db, "SELECT a.*,c.cost_code,c.description,l.purchase_order_line_id FROM public.purchase_landed_cost_allocations a JOIN public.purchase_landed_costs c ON c.tenant_id=a.tenant_id AND c.id=a.landed_cost_id JOIN public.purchase_receipt_lines l ON l.tenant_id=a.tenant_id AND l.id=a.receipt_line_id WHERE a.tenant_id=:t AND c.receipt_id=:id ORDER BY c.created_at,l.created_at", {"t": str(tenant_id), "id": str(receipt_id)})
    return row


@router.post("/receipts/{receipt_id}/post")
def post_receipt(receipt_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.receive"))):
    db, actor, tenant_id, _ = ctx
    idem, replay = _idempotency(db, tenant_id, "purchasing.receipt.post", idempotency_key, {"receipt_id": str(receipt_id)})
    if replay: return replay[1]
    receipt = _one(db, "SELECT * FROM public.purchase_receipts WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(receipt_id)})
    if not receipt: raise HTTPException(404, "Purchase receipt not found")
    if receipt["status"] != "DRAFT": raise HTTPException(409, "Only a draft receipt can be posted")
    order = _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=receipt["purchase_order_id"], lock=True)
    _ensure_receipt_location_matches_order(receipt, order)
    if order["status"] not in {"OPEN", "PARTIALLY_RECEIVED"}: raise HTTPException(409, "Purchase order is no longer open for receiving")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=receipt["receiving_location_id"])
    lines = _receipt_lines(db, tenant_id, receipt_id)
    costs = _many(db, "SELECT * FROM public.purchase_landed_costs WHERE tenant_id=:t AND receipt_id=:id ORDER BY created_at,id FOR UPDATE", {"t": str(tenant_id), "id": str(receipt_id)})
    total_by_line: dict[UUID, Decimal] = {UUID(str(line["id"])): ZERO for line in lines}
    for cost in costs:
        allocations = allocate_landed_cost(cost["amount"], [{"id": UUID(str(line["id"])), "quantity": line["received_quantity"], "base_unit_cost": line["base_unit_cost"]} for line in lines], cost["allocation_method"])
        for allocation in allocations:
            db.execute(text("INSERT INTO public.purchase_landed_cost_allocations(tenant_id,landed_cost_id,receipt_line_id,allocated_amount,allocation_method) VALUES(:t,:cost,:line,:amount,:method) ON CONFLICT(tenant_id,landed_cost_id,receipt_line_id) DO NOTHING"), {"t": str(tenant_id), "cost": str(cost["id"]), "line": str(allocation["receipt_line_id"]), "amount": allocation["allocated_amount"], "method": cost["allocation_method"]})
            total_by_line[UUID(str(allocation["receipt_line_id"]))] += allocation["allocated_amount"]
    for line in lines:
        po_line = _one(db, "SELECT * FROM public.purchase_order_lines WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(line["purchase_order_line_id"])})
        remaining = Decimal(str(po_line["ordered_quantity"])) - Decimal(str(po_line["received_quantity"]))
        if Decimal(str(line["received_quantity"])) > remaining: raise HTTPException(409, "A concurrent receipt used part of this order line's remaining quantity")
        landed = money(total_by_line[UUID(str(line["id"]))])
        effective_unit_cost = (Decimal(str(line["base_unit_cost"])) + landed / Decimal(str(line["received_quantity"]))).quantize(Decimal("0.000001"))
        db.execute(text("UPDATE public.purchase_receipt_lines SET landed_cost_amount=:landed,unit_cost=:cost WHERE tenant_id=:t AND id=:id"), {"landed": landed, "cost": effective_unit_cost, "t": str(tenant_id), "id": str(line["id"])})
        post_ledger(db, tenant_id=tenant_id, actor_user_id=actor, location_id=receipt["receiving_location_id"], variant_id=line["variant_id"], quantity_delta=Decimal(str(line["received_quantity"])), unit_cost=effective_unit_cost, transaction_type="PURCHASE_RECEIPT", reference_type="purchase_receipt", reference_id=receipt_id, metadata={"receipt_number": receipt["receipt_number"], "purchase_order_id": str(order["id"]), "purchase_order_line_id": str(line["purchase_order_line_id"]), "base_unit_cost": str(line["base_unit_cost"]), "landed_cost_amount": str(landed)}, idempotency_key=f"purchasing:receipt:{receipt_id}:line:{line['id']}")
        db.execute(text("UPDATE public.purchase_order_lines SET received_quantity=received_quantity+:qty,updated_at=now() WHERE tenant_id=:t AND id=:id"), {"qty": line["received_quantity"], "t": str(tenant_id), "id": str(line["purchase_order_line_id"])})
    db.execute(text("UPDATE public.purchase_receipts SET status='POSTED',posted_by=:actor,posted_at=now() WHERE tenant_id=:t AND id=:id"), {"actor": str(actor), "t": str(tenant_id), "id": str(receipt_id)})
    current_lines = _order_lines(db, tenant_id, order["id"])
    new_status = order_status_from_receipts(current_lines)
    db.execute(text("UPDATE public.purchase_orders SET status=:status,updated_at=now() WHERE tenant_id=:t AND id=:id"), {"status": new_status, "t": str(tenant_id), "id": str(order["id"])})
    _write_status(db, tenant_id, actor, order["id"], order["status"], new_status, f"receipt {receipt['receipt_number']} posted")
    _audit(db, tenant_id, actor, "purchasing.receipt.posted", "purchase_receipt", receipt_id, "purchasing.receipt.posted.v1", {"receipt_number": receipt["receipt_number"], "purchase_order_id": str(order["id"]), "landed_cost_total": str(receipt["landed_cost_total"])})
    response = {"id": str(receipt_id), "status": "POSTED", "purchase_order_id": str(order["id"]), "purchase_order_status": new_status, "lines_posted": len(lines), "landed_cost_total": str(receipt["landed_cost_total"])}
    return _commit(db, idem, response, "purchase_receipt", receipt_id)


@router.post("/receipts/{receipt_id}/cancel")
def cancel_receipt(receipt_id: UUID, body: dict[str, Any] | None = None, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.receive"))):
    db, actor, tenant_id, _ = ctx
    reason = (body or {}).get("reason")
    idem, replay = _idempotency(db, tenant_id, "purchasing.receipt.cancel", idempotency_key, {"receipt_id": str(receipt_id), "reason": reason})
    if replay: return replay[1]
    receipt = _one(db, "SELECT * FROM public.purchase_receipts WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(receipt_id)})
    if not receipt: raise HTTPException(404, "Purchase receipt not found")
    order = _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=receipt["purchase_order_id"])
    _ensure_receipt_location_matches_order(receipt, order)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=receipt["receiving_location_id"])
    if receipt["status"] != "DRAFT": raise HTTPException(409, "Only a draft receipt can be cancelled; posted stock must be corrected with a reversal")
    db.execute(text("UPDATE public.purchase_receipts SET status='CANCELLED' WHERE tenant_id=:t AND id=:id"), {"t": str(tenant_id), "id": str(receipt_id)})
    _audit(db, tenant_id, actor, "purchasing.receipt.cancelled", "purchase_receipt", receipt_id, "purchasing.receipt.cancelled.v1", {"reason": reason})
    return _commit(db, idem, {"id": str(receipt_id), "status": "CANCELLED"}, "purchase_receipt", receipt_id)


@router.get("/returns")
def list_returns(status: str | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    return _many_branch_scoped(db, "SELECT r.*,pr.receipt_number,po.po_number,p.display_name AS supplier_name,po.currency_code,(SELECT coalesce(sum(rl.quantity*rl.supplier_credit_unit_cost),0) FROM public.purchase_return_lines rl WHERE rl.tenant_id=r.tenant_id AND rl.purchase_return_id=r.id) AS return_value FROM public.purchase_returns r JOIN public.purchase_receipts pr ON pr.tenant_id=r.tenant_id AND pr.id=r.purchase_receipt_id AND r.receiving_location_id=pr.receiving_location_id JOIN public.purchase_orders po ON po.tenant_id=pr.tenant_id AND po.id=pr.purchase_order_id AND pr.receiving_location_id=po.receiving_location_id JOIN public.parties p ON p.tenant_id=po.tenant_id AND p.id=po.supplier_party_id JOIN public.locations l ON l.tenant_id=r.tenant_id AND l.id=r.receiving_location_id JOIN public.warehouses wh ON wh.tenant_id=l.tenant_id AND wh.id=l.warehouse_id AND wh.branch_id=po.branch_id WHERE r.tenant_id=:t AND __BRANCH_SCOPE__ AND (:status IS NULL OR r.status=:status) ORDER BY r.created_at DESC LIMIT :limit", {"t": str(tenant_id), "status": status, "limit": limit}, tenant_id=tenant_id, user_id=actor, branch_column="po.branch_id")


@router.post("/returns")
def create_return(body: PurchaseReturnCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.returns.manage"))):
    db, actor, tenant_id, _ = ctx
    idem, replay = _idempotency(db, tenant_id, "purchasing.return.create", idempotency_key, body.model_dump(mode="json"))
    if replay: return replay[1]
    receipt = _one(db, "SELECT * FROM public.purchase_receipts WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(body.purchase_receipt_id)})
    if not receipt or receipt["status"] != "POSTED": raise HTTPException(409, "Returns require a posted goods receipt")
    order = _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=receipt["purchase_order_id"])
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=receipt["receiving_location_id"])
    _ensure_receipt_location_matches_order(receipt, order)
    source_lines = {UUID(str(row["id"])): row for row in _receipt_lines(db, tenant_id, body.purchase_receipt_id)}
    total = ZERO
    resolved = []
    for item in body.lines:
        line = source_lines.get(item.purchase_receipt_line_id)
        if not line: raise HTTPException(422, "Return line does not belong to the selected posted receipt")
        already = Decimal(str(db.execute(text("SELECT coalesce(sum(prl.quantity),0) FROM public.purchase_return_lines prl JOIN public.purchase_returns r ON r.tenant_id=prl.tenant_id AND r.id=prl.purchase_return_id WHERE prl.tenant_id=:t AND prl.purchase_receipt_line_id=:line AND r.status IN ('REQUESTED','APPROVED','POSTED')"), {"t": str(tenant_id), "line": str(item.purchase_receipt_line_id)}).scalar_one()))
        outstanding = Decimal(str(line["received_quantity"])) - already
        if item.quantity > outstanding: raise HTTPException(409, f"Return quantity exceeds remaining receipted quantity for {line['sku']}")
        effective_cost = Decimal(str(line["unit_cost"]))
        supplier_credit_cost = Decimal(str(line.get("base_unit_cost") or line["unit_cost"]))
        total += item.quantity * supplier_credit_cost
        resolved.append((item, line, effective_cost, supplier_credit_cost))
    return_id = uuid4(); return_number = f"SRET-{date.today():%Y%m%d}-{return_id.hex[:8].upper()}"
    db.execute(text("INSERT INTO public.purchase_returns(id,tenant_id,return_number,purchase_receipt_id,receiving_location_id,status,reason,notes,created_by) VALUES(:id,:t,:number,:receipt,:loc,'REQUESTED',:reason,:notes,:actor)"), {"id": str(return_id), "t": str(tenant_id), "number": return_number, "receipt": str(body.purchase_receipt_id), "loc": str(receipt["receiving_location_id"]), "reason": body.reason.strip(), "notes": body.notes, "actor": str(actor)})
    for item, line, cost, supplier_credit_cost in resolved:
        db.execute(text("INSERT INTO public.purchase_return_lines(tenant_id,purchase_return_id,purchase_receipt_line_id,variant_id,quantity,unit_cost,supplier_credit_unit_cost,reason) VALUES(:t,:r,:source,:variant,:qty,:cost,:supplier_cost,:reason)"), {"t": str(tenant_id), "r": str(return_id), "source": str(item.purchase_receipt_line_id), "variant": str(line["variant_id"]), "qty": item.quantity, "cost": cost, "supplier_cost": supplier_credit_cost, "reason": item.reason})
    _audit(db, tenant_id, actor, "purchasing.return.requested", "purchase_return", return_id, "purchasing.return.requested.v1", {"return_number": return_number, "receipt_id": str(body.purchase_receipt_id), "value": str(money(total))})
    response = {"id": str(return_id), "return_number": return_number, "status": "REQUESTED", "value": str(money(total)), "currency_code": order["currency_code"]}
    return _commit(db, idem, response, "purchase_return", return_id)


@router.get("/returns/{return_id}")
def get_return(return_id: UUID, ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    row = _one(db, "SELECT r.*,pr.receipt_number,po.po_number,po.currency_code,po.supplier_party_id,po.branch_id,p.display_name AS supplier_name FROM public.purchase_returns r JOIN public.purchase_receipts pr ON pr.tenant_id=r.tenant_id AND pr.id=r.purchase_receipt_id AND r.receiving_location_id=pr.receiving_location_id JOIN public.purchase_orders po ON po.tenant_id=pr.tenant_id AND po.id=pr.purchase_order_id AND pr.receiving_location_id=po.receiving_location_id JOIN public.parties p ON p.tenant_id=po.tenant_id AND p.id=po.supplier_party_id JOIN public.locations l ON l.tenant_id=r.tenant_id AND l.id=r.receiving_location_id JOIN public.warehouses wh ON wh.tenant_id=l.tenant_id AND wh.id=l.warehouse_id AND wh.branch_id=po.branch_id WHERE r.tenant_id=:t AND r.id=:id", {"t": str(tenant_id), "id": str(return_id)})
    if not row: raise HTTPException(404, "Supplier return not found")
    ensure_branch_access(db, tenant_id=tenant_id, user_id=actor, branch_id=UUID(str(row["branch_id"])))
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=UUID(str(row["receiving_location_id"])))
    row["lines"] = _many(db, "SELECT rl.*,pv.sku,pv.name AS variant_name,pr.name AS product_name FROM public.purchase_return_lines rl JOIN public.product_variants pv ON pv.tenant_id=rl.tenant_id AND pv.id=rl.variant_id JOIN public.products pr ON pr.tenant_id=pv.tenant_id AND pr.id=pv.product_id WHERE rl.tenant_id=:t AND rl.purchase_return_id=:id ORDER BY rl.created_at", {"t": str(tenant_id), "id": str(return_id)})
    return row


@router.post("/returns/{return_id}/cancel")
def cancel_return(return_id: UUID, body: dict[str, Any] | None = None, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.returns.manage"))):
    db, actor, tenant_id, _ = ctx
    reason = (body or {}).get("reason")
    idem, replay = _idempotency(db, tenant_id, "purchasing.return.cancel", idempotency_key, {"return_id": str(return_id), "reason": reason})
    if replay: return replay[1]
    row = _one(db, "SELECT * FROM public.purchase_returns WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(return_id)})
    if not row: raise HTTPException(404, "Supplier return not found")
    source_receipt = _one(db, "SELECT receiving_location_id,purchase_order_id FROM public.purchase_receipts WHERE tenant_id=:t AND id=:id", {"t": str(tenant_id), "id": str(row["purchase_receipt_id"])})
    if not source_receipt: raise HTTPException(404, "The original delivery for this return was not found")
    _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=source_receipt["purchase_order_id"])
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=source_receipt["receiving_location_id"])
    if UUID(str(row["receiving_location_id"])) != UUID(str(source_receipt["receiving_location_id"])):
        raise HTTPException(409, detail={"code": "PURCHASE_RETURN_LOCATION_MISMATCH", "message": "This return is linked to a different stock location. Ask the business owner to correct it before continuing."})
    if row["status"] != "REQUESTED": raise HTTPException(409, "Only a requested supplier return can be cancelled; approved or posted returns require controlled reversal")
    db.execute(text("UPDATE public.purchase_returns SET status='CANCELLED',updated_at=now() WHERE tenant_id=:t AND id=:id"), {"t": str(tenant_id), "id": str(return_id)})
    _audit(db, tenant_id, actor, "purchasing.return.cancelled", "purchase_return", return_id, "purchasing.return.cancelled.v1", {"return_number": row["return_number"], "reason": reason})
    return _commit(db, idem, {"id": str(return_id), "status": "CANCELLED"}, "purchase_return", return_id)


@router.post("/returns/{return_id}/approve")
def approve_return(return_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.approve"))):
    db, actor, tenant_id, _ = ctx
    idem, replay = _idempotency(db, tenant_id, "purchasing.return.approve", idempotency_key, {"return_id": str(return_id)})
    if replay: return replay[1]
    row = _one(db, "SELECT * FROM public.purchase_returns WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(return_id)})
    if not row: raise HTTPException(404, "Supplier return not found")
    source_receipt = _one(db, "SELECT receiving_location_id,purchase_order_id FROM public.purchase_receipts WHERE tenant_id=:t AND id=:id", {"t": str(tenant_id), "id": str(row["purchase_receipt_id"])})
    if not source_receipt: raise HTTPException(404, "The original delivery for this return was not found")
    _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=source_receipt["purchase_order_id"])
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=source_receipt["receiving_location_id"])
    if UUID(str(row["receiving_location_id"])) != UUID(str(source_receipt["receiving_location_id"])):
        raise HTTPException(409, detail={"code": "PURCHASE_RETURN_LOCATION_MISMATCH", "message": "This return is linked to a different stock location. Ask the business owner to correct it before continuing."})
    if row["status"] != "REQUESTED": raise HTTPException(409, "Only a requested supplier return can be approved")
    db.execute(text("UPDATE public.purchase_returns SET status='APPROVED',approved_by=:actor,approved_at=now(),updated_at=now() WHERE tenant_id=:t AND id=:id"), {"actor": str(actor), "t": str(tenant_id), "id": str(return_id)})
    _audit(db, tenant_id, actor, "purchasing.return.approved", "purchase_return", return_id, "purchasing.return.approved.v1", {"return_number": row["return_number"]})
    return _commit(db, idem, {"id": str(return_id), "status": "APPROVED"}, "purchase_return", return_id)


@router.post("/returns/{return_id}/post")
def post_return(return_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.receive"))):
    db, actor, tenant_id, _ = ctx
    idem, replay = _idempotency(db, tenant_id, "purchasing.return.post", idempotency_key, {"return_id": str(return_id)})
    if replay: return replay[1]
    row = _one(db, "SELECT * FROM public.purchase_returns WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(return_id)})
    if not row: raise HTTPException(404, "Supplier return not found")
    if row["status"] != "APPROVED": raise HTTPException(409, "Supplier return must be approved before posting")
    receipt = _one(db, "SELECT * FROM public.purchase_receipts WHERE tenant_id=:t AND id=:id", {"t": str(tenant_id), "id": str(row["purchase_receipt_id"])})
    if not receipt:
        raise HTTPException(404, "The original delivery for this return was not found")
    order = _ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=receipt["purchase_order_id"])
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row["receiving_location_id"])
    if UUID(str(row["receiving_location_id"])) != UUID(str(receipt["receiving_location_id"])) or UUID(str(receipt["receiving_location_id"])) != UUID(str(order["receiving_location_id"])):
        raise HTTPException(409, detail={"code": "PURCHASE_RETURN_LOCATION_MISMATCH", "message": "This return is linked to a different stock location. Ask the business owner to correct it before continuing."})
    lines = _many(db, "SELECT * FROM public.purchase_return_lines WHERE tenant_id=:t AND purchase_return_id=:id ORDER BY id FOR UPDATE", {"t": str(tenant_id), "id": str(return_id)})
    total = ZERO
    for line in lines:
        inv = post_ledger(db, tenant_id=tenant_id, actor_user_id=actor, location_id=row["receiving_location_id"], variant_id=line["variant_id"], quantity_delta=-Decimal(str(line["quantity"])), unit_cost=Decimal(str(line["unit_cost"])), transaction_type="PURCHASE_RETURN", reference_type="purchase_return", reference_id=return_id, metadata={"return_number": row["return_number"], "purchase_receipt_id": str(receipt["id"]), "receipt_line_id": str(line["purchase_receipt_line_id"])}, idempotency_key=f"purchasing:return:{return_id}:line:{line['id']}")
        total += Decimal(str(line["quantity"])) * Decimal(str(line.get("supplier_credit_unit_cost") or line["unit_cost"]))
    db.execute(text("UPDATE public.purchase_returns SET status='POSTED',posted_by=:actor,posted_at=now(),updated_at=now() WHERE tenant_id=:t AND id=:id"), {"actor": str(actor), "t": str(tenant_id), "id": str(return_id)})
    db.execute(text("INSERT INTO public.supplier_ledger_entries(tenant_id,supplier_party_id,currency_code,entry_type,source_type,source_id,reference,debit_amount,credit_amount,actor_user_id,metadata) VALUES(:t,:supplier,:cc,'RETURN_CREDIT','purchase_return',:source,:ref,0,:amount,:actor,:metadata::jsonb) ON CONFLICT(tenant_id,source_type,source_id,entry_type) DO NOTHING"), {"t": str(tenant_id), "supplier": str(order["supplier_party_id"]), "cc": order["currency_code"], "source": str(return_id), "ref": row["return_number"], "amount": money(total), "actor": str(actor), "metadata": __import__("json").dumps({"receipt_id": str(receipt["id"]), "inventory_return_posted": True})})
    _audit(db, tenant_id, actor, "purchasing.return.posted", "purchase_return", return_id, "purchasing.return.posted.v1", {"return_number": row["return_number"], "credit_amount": str(money(total))})
    response = {"id": str(return_id), "status": "POSTED", "supplier_credit": str(money(total)), "currency_code": order["currency_code"]}
    return _commit(db, idem, response, "purchase_return", return_id)


@router.get("/supplier-bills")
def list_supplier_bills(status: str | None = None, supplier_party_id: UUID | None = None, due_before: date | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    return _many(db, "SELECT b.*,p.display_name AS supplier_name,coalesce((SELECT sum(a.amount) FROM public.supplier_payment_allocations a JOIN public.supplier_payments sp ON sp.tenant_id=a.tenant_id AND sp.id=a.payment_id WHERE a.tenant_id=b.tenant_id AND a.bill_id=b.id AND sp.status='POSTED'),0) AS paid_amount,b.total-coalesce((SELECT sum(a.amount) FROM public.supplier_payment_allocations a JOIN public.supplier_payments sp ON sp.tenant_id=a.tenant_id AND sp.id=a.payment_id WHERE a.tenant_id=b.tenant_id AND a.bill_id=b.id AND sp.status='POSTED'),0) AS allocated_outstanding FROM public.supplier_bills b JOIN public.parties p ON p.tenant_id=b.tenant_id AND p.id=b.supplier_party_id WHERE b.tenant_id=:t AND (:status IS NULL OR b.status=:status) AND (:supplier IS NULL OR b.supplier_party_id=:supplier) AND (:due_before IS NULL OR b.due_date<=:due_before) ORDER BY b.due_date,b.created_at DESC LIMIT :limit", {"t": str(tenant_id), "status": status, "supplier": str(supplier_party_id) if supplier_party_id else None, "due_before": due_before, "limit": limit})


@router.post("/supplier-bills")
def create_supplier_bill(body: SupplierBillCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.bills.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier_bill.create", idempotency_key, body.model_dump(mode="json"))
    if replay: return replay[1]
    supplier = _supplier(db, tenant_id, body.supplier_party_id)
    if supplier["currency_code"] != body.currency_code: raise HTTPException(422, "Supplier bill currency must match supplier currency; FX is not enabled")
    order = None
    if body.purchase_order_id:
        order = _order(db, tenant_id, body.purchase_order_id)
        if order["supplier_party_id"] != body.supplier_party_id: raise HTTPException(422, "Purchase order belongs to a different supplier")
        if order["currency_code"] != body.currency_code: raise HTTPException(422, "Bill currency must match purchase order currency")
    if body.purchase_receipt_id:
        receipt = _one(db, "SELECT * FROM public.purchase_receipts WHERE tenant_id=:t AND id=:id", {"t": str(tenant_id), "id": str(body.purchase_receipt_id)})
        if not receipt or receipt["status"] != "POSTED": raise HTTPException(422, "Supplier bills may only be linked to a posted receipt")
        receipt_order = _order(db, tenant_id, receipt["purchase_order_id"])
        if receipt_order["supplier_party_id"] != body.supplier_party_id or receipt_order["currency_code"] != body.currency_code: raise HTTPException(422, "Receipt belongs to another supplier or currency")
        if order and order["id"] != receipt["purchase_order_id"]: raise HTTPException(422, "Linked purchase order and receipt do not match")
        if not order: order = receipt_order
    total = money(body.subtotal + body.tax_amount + body.other_charges)
    due_date = body.due_date or (body.bill_date + timedelta(days=int(supplier["payment_terms_days"])))
    match_status, match_variance, match_checked_at = "NOT_LINKED", ZERO, None
    if body.purchase_order_id and not body.purchase_receipt_id:
        match_status = "WAITING_RECEIPT"
    if body.purchase_receipt_id:
        expected_subtotal = Decimal(str(db.execute(text("SELECT coalesce(sum(received_quantity*base_unit_cost),0) FROM public.purchase_receipt_lines WHERE tenant_id=:t AND receipt_id=:receipt"), {"t": str(tenant_id), "receipt": str(body.purchase_receipt_id)}).scalar_one()))
        match_variance = money(body.subtotal - expected_subtotal)
        match_status = "MATCHED" if abs(match_variance) <= Decimal("0.01") else "VARIANCE"
        match_checked_at = datetime.now(timezone.utc)
    bill_id = uuid4()
    db.execute(text("INSERT INTO public.supplier_bills(id,tenant_id,supplier_party_id,purchase_order_id,purchase_receipt_id,bill_number,bill_date,due_date,currency_code,subtotal,tax_amount,other_charges,total,status,supplier_reference,match_status,match_variance,match_checked_at,notes,created_by) VALUES(:id,:t,:supplier,:po,:receipt,:number,:bill_date,:due,:cc,:subtotal,:tax,:other,:total,'DRAFT',:reference,:match_status,:match_variance,:match_checked_at,:notes,:actor)"), {"id": str(bill_id), "t": str(tenant_id), "supplier": str(body.supplier_party_id), "po": str(order["id"]) if order else None, "receipt": str(body.purchase_receipt_id) if body.purchase_receipt_id else None, "number": body.bill_number.strip(), "bill_date": body.bill_date, "due": due_date, "cc": body.currency_code, "subtotal": money(body.subtotal), "tax": money(body.tax_amount), "other": money(body.other_charges), "total": total, "reference": body.supplier_reference, "match_status": match_status, "match_variance": match_variance, "match_checked_at": match_checked_at, "notes": body.notes, "actor": str(actor)})
    _audit(db, tenant_id, actor, "purchasing.supplier_bill.created", "supplier_bill", bill_id, "purchasing.supplier_bill.created.v1", {"bill_number": body.bill_number, "total": str(total)})
    response = {"id": str(bill_id), "bill_number": body.bill_number, "status": "DRAFT", "total": str(total), "currency_code": body.currency_code, "due_date": due_date.isoformat(), "match_status": match_status, "match_variance": str(match_variance)}
    return _commit(db, idem, response, "supplier_bill", bill_id)


@router.post("/supplier-bills/{bill_id}/post")
def post_supplier_bill(bill_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.bills.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier_bill.post", idempotency_key, {"bill_id": str(bill_id)})
    if replay: return replay[1]
    bill = _one(db, "SELECT * FROM public.supplier_bills WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(bill_id)})
    if not bill: raise HTTPException(404, "Supplier bill not found")
    if bill["status"] != "DRAFT": raise HTTPException(409, "Only a draft supplier bill can be posted")
    if bill["match_status"] in {"VARIANCE", "WAITING_RECEIPT"}:
        raise HTTPException(409, "Supplier invoice cannot post until goods receipt is available and reconciled, or an authorised reviewer records an explicit exception.")
    _supplier(db, tenant_id, bill["supplier_party_id"], active=False)
    db.execute(text("UPDATE public.supplier_bills SET status='POSTED',posted_by=:actor,posted_at=now(),updated_at=now() WHERE tenant_id=:t AND id=:id"), {"actor": str(actor), "t": str(tenant_id), "id": str(bill_id)})
    db.execute(text("INSERT INTO public.supplier_ledger_entries(tenant_id,supplier_party_id,currency_code,entry_type,source_type,source_id,reference,debit_amount,credit_amount,actor_user_id,metadata) VALUES(:t,:supplier,:cc,'BILL','supplier_bill',:source,:ref,:amount,0,:actor,:metadata::jsonb) ON CONFLICT(tenant_id,source_type,source_id,entry_type) DO NOTHING"), {"t": str(tenant_id), "supplier": str(bill["supplier_party_id"]), "cc": bill["currency_code"], "source": str(bill_id), "ref": bill["bill_number"], "amount": bill["total"], "actor": str(actor), "metadata": __import__("json").dumps({"purchase_order_id": str(bill["purchase_order_id"]) if bill["purchase_order_id"] else None, "purchase_receipt_id": str(bill["purchase_receipt_id"]) if bill["purchase_receipt_id"] else None})})
    _audit(db, tenant_id, actor, "purchasing.supplier_bill.posted", "supplier_bill", bill_id, "purchasing.supplier_bill.posted.v1", {"bill_number": bill["bill_number"], "amount": str(bill["total"])})
    response = {"id": str(bill_id), "status": "POSTED", "payable_added": str(bill["total"]), "currency_code": bill["currency_code"]}
    return _commit(db, idem, response, "supplier_bill", bill_id)


@router.post("/supplier-bills/{bill_id}/accept-variance")
def accept_supplier_bill_variance(bill_id: UUID, body: SupplierBillVarianceOverride, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.approve"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier_bill.accept_variance", idempotency_key, {"bill_id": str(bill_id), "reason": body.reason.strip()})
    if replay: return replay[1]
    bill = _one(db, "SELECT * FROM public.supplier_bills WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(bill_id)})
    if not bill: raise HTTPException(404, "Supplier bill not found")
    if bill["status"] != "DRAFT": raise HTTPException(409, "Only a draft supplier bill variance can be reviewed")
    if bill["match_status"] not in {"VARIANCE", "WAITING_RECEIPT"}: raise HTTPException(409, "This supplier bill has no outstanding receipt-match exception to approve")
    reason = body.reason.strip()
    if len(reason) < 5: raise HTTPException(422, "A meaningful invoice-match exception reason is required")
    prior_match_status = bill["match_status"]
    db.execute(text("UPDATE public.supplier_bills SET match_status='OVERRIDDEN',match_reason=:reason,match_reviewed_by=:actor,updated_at=now() WHERE tenant_id=:t AND id=:id"), {"reason": reason, "actor": str(actor), "t": str(tenant_id), "id": str(bill_id)})
    _audit(db, tenant_id, actor, "purchasing.supplier_bill.match_exception_approved", "supplier_bill", bill_id, "purchasing.supplier_bill.match_exception_approved.v1", {"prior_match_status": prior_match_status, "match_variance": str(bill["match_variance"]), "reason": reason})
    response = {"id": str(bill_id), "match_status": "OVERRIDDEN", "previous_match_status": prior_match_status, "match_variance": str(bill["match_variance"]), "reason": reason}
    return _commit(db, idem, response, "supplier_bill", bill_id)


@router.post("/supplier-bills/{bill_id}/void")
def void_supplier_bill(bill_id: UUID, body: dict[str, Any] | None = None, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.bills.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    reason = (body or {}).get("reason")
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier_bill.void", idempotency_key, {"bill_id": str(bill_id), "reason": reason})
    if replay: return replay[1]
    bill = _one(db, "SELECT * FROM public.supplier_bills WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(bill_id)})
    if not bill: raise HTTPException(404, "Supplier bill not found")
    if bill["status"] != "DRAFT": raise HTTPException(409, "A posted bill cannot be voided; create an approved supplier debit/credit adjustment instead")
    db.execute(text("UPDATE public.supplier_bills SET status='VOID',updated_at=now() WHERE tenant_id=:t AND id=:id"), {"t": str(tenant_id), "id": str(bill_id)})
    _audit(db, tenant_id, actor, "purchasing.supplier_bill.voided", "supplier_bill", bill_id, "purchasing.supplier_bill.voided.v1", {"reason": reason})
    return _commit(db, idem, {"id": str(bill_id), "status": "VOID"}, "supplier_bill", bill_id)


@router.get("/supplier-payments")
def list_supplier_payments(status: str | None = None, supplier_party_id: UUID | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    return _many(db, "SELECT py.*,p.display_name AS supplier_name,(SELECT coalesce(sum(a.amount),0) FROM public.supplier_payment_allocations a WHERE a.tenant_id=py.tenant_id AND a.payment_id=py.id) AS allocated_amount,py.amount-(SELECT coalesce(sum(a.amount),0) FROM public.supplier_payment_allocations a WHERE a.tenant_id=py.tenant_id AND a.payment_id=py.id) AS unallocated_amount FROM public.supplier_payments py JOIN public.parties p ON p.tenant_id=py.tenant_id AND p.id=py.supplier_party_id WHERE py.tenant_id=:t AND (:status IS NULL OR py.status=:status) AND (:supplier IS NULL OR py.supplier_party_id=:supplier) ORDER BY py.payment_date DESC,py.created_at DESC LIMIT :limit", {"t": str(tenant_id), "status": status, "supplier": str(supplier_party_id) if supplier_party_id else None, "limit": limit})


@router.post("/supplier-payments")
def create_supplier_payment(body: SupplierPaymentCreate, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.payments.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier_payment.create", idempotency_key, body.model_dump(mode="json"))
    if replay: return replay[1]
    supplier = _supplier(db, tenant_id, body.supplier_party_id, active=False)
    if supplier["currency_code"] != body.currency_code: raise HTTPException(422, "Payment currency must match the supplier currency; FX is not enabled")
    allocations = sum((a.amount for a in body.allocations), ZERO)
    if allocations > body.amount: raise HTTPException(422, "Allocated amount cannot exceed payment amount")
    payment_id = uuid4()
    db.execute(text("INSERT INTO public.supplier_payments(id,tenant_id,supplier_party_id,payment_number,payment_date,currency_code,amount,payment_method,reference,notes,status,created_by) VALUES(:id,:t,:supplier,:number,:date,:cc,:amount,:method,:reference,:notes,'DRAFT',:actor)"), {"id": str(payment_id), "t": str(tenant_id), "supplier": str(body.supplier_party_id), "number": body.payment_number.strip(), "date": body.payment_date, "cc": body.currency_code, "amount": money(body.amount), "method": body.payment_method, "reference": body.reference, "notes": body.notes, "actor": str(actor)})
    for allocation in body.allocations:
        bill = _one(db, "SELECT * FROM public.supplier_bills WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(allocation.bill_id)})
        if not bill or bill["status"] != "POSTED": raise HTTPException(422, "Payment can only allocate to a posted bill in this tenant")
        if bill["supplier_party_id"] != body.supplier_party_id or bill["currency_code"] != body.currency_code: raise HTTPException(422, "Payment allocation supplier/currency must match the bill")
        db.execute(text("INSERT INTO public.supplier_payment_allocations(tenant_id,payment_id,bill_id,amount) VALUES(:t,:payment,:bill,:amount)"), {"t": str(tenant_id), "payment": str(payment_id), "bill": str(bill["id"]), "amount": money(allocation.amount)})
    _audit(db, tenant_id, actor, "purchasing.supplier_payment.created", "supplier_payment", payment_id, "purchasing.supplier_payment.created.v1", {"payment_number": body.payment_number, "amount": str(money(body.amount)), "allocations": len(body.allocations)})
    response = {"id": str(payment_id), "payment_number": body.payment_number, "status": "DRAFT", "amount": str(money(body.amount)), "allocated_amount": str(money(allocations)), "unallocated_amount": str(money(body.amount - allocations)), "currency_code": body.currency_code}
    return _commit(db, idem, response, "supplier_payment", payment_id)


@router.post("/supplier-payments/{payment_id}/post")
def post_supplier_payment(payment_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.payments.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier_payment.post", idempotency_key, {"payment_id": str(payment_id)})
    if replay: return replay[1]
    payment = _one(db, "SELECT * FROM public.supplier_payments WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(payment_id)})
    if not payment: raise HTTPException(404, "Supplier payment not found")
    if payment["status"] != "DRAFT": raise HTTPException(409, "Only a draft supplier payment can be posted")
    allocations = _many(db, "SELECT a.*,b.status AS bill_status,b.supplier_party_id AS bill_supplier,b.currency_code AS bill_currency,b.total FROM public.supplier_payment_allocations a JOIN public.supplier_bills b ON b.tenant_id=a.tenant_id AND b.id=a.bill_id WHERE a.tenant_id=:t AND a.payment_id=:id ORDER BY a.bill_id FOR UPDATE OF b", {"t": str(tenant_id), "id": str(payment_id)})
    total_allocated = sum((Decimal(str(a["amount"])) for a in allocations), ZERO)
    if total_allocated > Decimal(str(payment["amount"])): raise HTTPException(409, "Payment allocations exceed the payment amount")
    for allocation in allocations:
        if allocation["bill_status"] != "POSTED" or allocation["bill_supplier"] != payment["supplier_party_id"] or allocation["bill_currency"] != payment["currency_code"]: raise HTTPException(409, "A payment allocation no longer matches a posted bill for this supplier and currency")
        paid_before = Decimal(str(db.execute(text("SELECT coalesce(sum(a.amount),0) FROM public.supplier_payment_allocations a JOIN public.supplier_payments p ON p.tenant_id=a.tenant_id AND p.id=a.payment_id WHERE a.tenant_id=:t AND a.bill_id=:bill AND p.status='POSTED'"), {"t": str(tenant_id), "bill": str(allocation["bill_id"])}).scalar_one()))
        available = Decimal(str(allocation["total"])) - paid_before
        if Decimal(str(allocation["amount"])) > available: raise HTTPException(409, "Payment allocation exceeds the bill's outstanding balance")
    db.execute(text("UPDATE public.supplier_payments SET status='POSTED',posted_by=:actor,posted_at=now() WHERE tenant_id=:t AND id=:id"), {"actor": str(actor), "t": str(tenant_id), "id": str(payment_id)})
    db.execute(text("INSERT INTO public.supplier_ledger_entries(tenant_id,supplier_party_id,currency_code,entry_type,source_type,source_id,reference,debit_amount,credit_amount,actor_user_id,metadata) VALUES(:t,:supplier,:cc,'PAYMENT','supplier_payment',:source,:ref,0,:amount,:actor,:metadata::jsonb) ON CONFLICT(tenant_id,source_type,source_id,entry_type) DO NOTHING"), {"t": str(tenant_id), "supplier": str(payment["supplier_party_id"]), "cc": payment["currency_code"], "source": str(payment_id), "ref": payment["payment_number"], "amount": payment["amount"], "actor": str(actor), "metadata": __import__("json").dumps({"payment_method": payment["payment_method"], "reference": payment["reference"], "allocated_amount": str(money(total_allocated))})})
    _audit(db, tenant_id, actor, "purchasing.supplier_payment.posted", "supplier_payment", payment_id, "purchasing.supplier_payment.posted.v1", {"payment_number": payment["payment_number"], "amount": str(payment["amount"]), "allocated_amount": str(money(total_allocated))})
    response = {"id": str(payment_id), "status": "POSTED", "supplier_balance_credit": str(payment["amount"]), "allocated_amount": str(money(total_allocated)), "advance_amount": str(money(Decimal(str(payment["amount"])) - total_allocated)), "currency_code": payment["currency_code"]}
    return _commit(db, idem, response, "supplier_payment", payment_id)


@router.post("/supplier-payments/{payment_id}/void")
def void_supplier_payment(payment_id: UUID, body: dict[str, Any] | None = None, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("purchasing.payments.manage"))):
    db, actor, tenant_id, _ = ctx
    _require_workspace_finance_scope(db, tenant_id=tenant_id, user_id=actor)
    reason = (body or {}).get("reason")
    idem, replay = _idempotency(db, tenant_id, "purchasing.supplier_payment.void", idempotency_key, {"payment_id": str(payment_id), "reason": reason})
    if replay: return replay[1]
    payment = _one(db, "SELECT * FROM public.supplier_payments WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(payment_id)})
    if not payment: raise HTTPException(404, "Supplier payment not found")
    if payment["status"] != "DRAFT": raise HTTPException(409, "A posted payment cannot be voided; use an approved reversal workflow")
    db.execute(text("UPDATE public.supplier_payments SET status='VOID' WHERE tenant_id=:t AND id=:id"), {"t": str(tenant_id), "id": str(payment_id)})
    _audit(db, tenant_id, actor, "purchasing.supplier_payment.voided", "supplier_payment", payment_id, "purchasing.supplier_payment.voided.v1", {"reason": reason})
    return _commit(db, idem, {"id": str(payment_id), "status": "VOID"}, "supplier_payment", payment_id)


@router.get("/supplier-balances")
def supplier_balances(supplier_party_id: UUID | None = None, currency_code: str | None = None, include_zero: bool = False, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor)
    if currency_code and not __import__("re").fullmatch(r"[A-Za-z]{3}", currency_code): raise HTTPException(422, "Currency code must be a three-letter code")
    return _many(db, """
      WITH ledger AS (
        SELECT supplier_party_id,currency_code,sum(debit_amount) AS debits,sum(credit_amount) AS credits,
               max(occurred_at) AS last_activity,count(*) AS entry_count
        FROM public.supplier_ledger_entries WHERE tenant_id=:t
        GROUP BY supplier_party_id,currency_code
      )
      SELECT p.id AS supplier_party_id,p.display_name AS supplier_name,sp.payment_terms_days,l.currency_code,
             l.debits,l.credits,l.debits-l.credits AS net_balance,
             greatest(l.debits-l.credits,0) AS payable,
             greatest(l.credits-l.debits,0) AS supplier_credit,
             l.last_activity,l.entry_count,
             (SELECT count(*) FROM public.supplier_bills b WHERE b.tenant_id=sp.tenant_id AND b.supplier_party_id=sp.supplier_party_id AND b.currency_code=l.currency_code AND b.status='POSTED' AND b.due_date<CURRENT_DATE
               AND b.total>(SELECT coalesce(sum(a.amount),0) FROM public.supplier_payment_allocations a JOIN public.supplier_payments py ON py.tenant_id=a.tenant_id AND py.id=a.payment_id WHERE a.tenant_id=b.tenant_id AND a.bill_id=b.id AND py.status='POSTED')) AS overdue_bills
      FROM ledger l JOIN public.supplier_profiles sp ON sp.tenant_id=:t AND sp.supplier_party_id=l.supplier_party_id
      JOIN public.parties p ON p.tenant_id=sp.tenant_id AND p.id=sp.supplier_party_id
      WHERE (:supplier IS NULL OR l.supplier_party_id=:supplier) AND (:cc IS NULL OR upper(l.currency_code)=upper(:cc)) AND (:include_zero OR l.debits<>l.credits)
      ORDER BY abs(l.debits-l.credits) DESC,p.display_name LIMIT :limit
    """, {"t": str(tenant_id), "supplier": str(supplier_party_id) if supplier_party_id else None, "cc": currency_code.upper() if currency_code else None, "include_zero": include_zero, "limit": limit})


@router.get("/supplier-ledger/{supplier_party_id}")
def supplier_ledger(supplier_party_id: UUID, currency_code: str | None = None, limit: int = Query(200, ge=1, le=1000), ctx=Depends(require_permission("purchasing.read"))):
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor)
    _supplier(db, tenant_id, supplier_party_id, active=False)
    rows = _many(db, "SELECT * FROM public.supplier_ledger_entries WHERE tenant_id=:t AND supplier_party_id=:p AND (:cc IS NULL OR upper(currency_code)=upper(:cc)) ORDER BY occurred_at,id LIMIT :limit", {"t": str(tenant_id), "p": str(supplier_party_id), "cc": currency_code.upper() if currency_code else None, "limit": limit})
    running: dict[str, Decimal] = {}
    for row in reversed(rows):
        cc = row["currency_code"]
        running[cc] = money(running.get(cc, ZERO) + Decimal(str(row["debit_amount"])) - Decimal(str(row["credit_amount"])))
        row["running_balance"] = str(running[cc])
    return list(reversed(rows))
