from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalog import begin_idempotency, emit_event, finish_idempotency, write_audit
from ..commerce_rules import calculate_line_tax, ensure_unique_return_line_ids, original_sale_inventory_unit_cost, remaining_refund_balance, prorate_return_line_amounts, safe_payment_channel_label, safe_payment_reference
from ..branch_access import ensure_branch_access, ensure_location_access, require_full_branch_scope
from ..dependencies import require_permission
from ..inventory import post_ledger, tenant_location, tenant_variant
from ..models import Branch, BusinessProfile, BusinessTransaction, Party, PartyRole, TransactionLine

router = APIRouter(prefix="/commerce", tags=["commerce"])

MONEY = Decimal("0.0001")
CHANNEL_TYPES = {"CASH", "MOBILE_MONEY", "BANK", "CARD", "CHEQUE", "OTHER"}


def q(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def out(row: Any) -> dict[str, Any]:
    """Serialize both SQLAlchemy Row and RowMapping result objects safely."""
    if row is None:
        return {}
    values = row if isinstance(row, Mapping) else row._mapping
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in values.items()}


def require_business_currency(db: Session, tenant_id: UUID) -> str:
    """Return the explicitly saved business currency or stop money workflows.

    A fallback such as UGX silently changes the meaning of every total, balance,
    payment channel, receivable and journal. Setup must be completed explicitly.
    """
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id))
    currency = str(profile.currency_code or "").strip().upper() if profile else ""
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise HTTPException(409, "Set a valid business currency in Settings before recording sales or viewing currency-based totals.")
    return currency


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerCreate(Strict):
    display_name: str = Field(min_length=1, max_length=250)
    party_type: str = Field(default="PERSON", pattern=r"^(PERSON|ORGANIZATION)$")
    legal_name: str | None = Field(default=None, max_length=250)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    credit_limit: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None


class ChannelCreate(Strict):
    name: str = Field(min_length=1, max_length=160, description="A friendly label such as MTN Line 1 or Stanbic")
    channel_type: str = Field(min_length=2, max_length=30)
    provider: str | None = Field(default=None, max_length=100, description="Optional institution or service name; never enter account details or credentials")
    currency_code: str = Field(pattern=r"^[A-Za-z]{3}$")

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return str(value or "").strip().upper()

    @model_validator(mode="after")
    def validate_type(self):
        self.name, self.provider = safe_payment_channel_label(self.name, self.provider)
        self.channel_type = self.channel_type.upper().strip()
        if self.channel_type not in CHANNEL_TYPES:
            raise ValueError("Choose a supported payment method category")
        if not self.name:
            raise ValueError("Enter a name for this payment method")
        return self


class ChannelDeactivate(Strict):
    reason: str = Field(default="No longer used", min_length=3, max_length=300)


class SaleLineIn(Strict):
    variant_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class PaymentAllocationIn(Strict):
    payment_channel_id: UUID
    amount: Decimal = Field(gt=0)
    reference: str | None = Field(default=None, max_length=120)

    @field_validator("reference")
    @classmethod
    def reference_is_not_a_secret(cls, value: str | None) -> str | None:
        return safe_payment_reference(value)


class SaleCreate(Strict):
    customer_party_id: UUID | None = None
    branch_id: UUID | None = None
    location_id: UUID | None = None
    currency_code: str = Field(pattern=r"^[A-Za-z]{3}$")
    business_date: date = Field(default_factory=date.today)
    lines: list[SaleLineIn] = Field(min_length=1)
    payments: list[PaymentAllocationIn] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return str(value or "").strip().upper()


class PaymentCreate(Strict):
    payment_channel_id: UUID
    amount: Decimal = Field(gt=0)
    business_date: date = Field(default_factory=date.today)
    reference: str | None = Field(default=None, max_length=120)

    @field_validator("reference")
    @classmethod
    def reference_is_not_a_secret(cls, value: str | None) -> str | None:
        return safe_payment_reference(value)


class ActualIn(Strict):
    actual_amount: Decimal = Field(ge=0)
    notes: str | None = None


class ResolveIn(Strict):
    status: str = Field(pattern=r"^(RESOLVED|ACKNOWLEDGED)$")
    notes: str | None = None


class ReconciliationCreate(Strict):
    business_date: date = Field(default_factory=date.today)
    notes: str | None = None


def _idempotency(db: Session, tenant_id: UUID, key: str | None, operation: str, payload: Any):
    try:
        row, cached = begin_idempotency(db, tenant_id=tenant_id, operation_type=operation, key=key, payload=payload)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    if cached:
        status_code, body = cached
        return row, cached, status_code, body
    return row, None, None, None


def _finish(db: Session, idem, status_code: int, body: dict[str, Any], resource_type: str, resource_id: UUID):
    finish_idempotency(db, idem, status_code=status_code, response_body=body, resource_type=resource_type, resource_id=resource_id)


def _tenant_party(db: Session, tenant_id: UUID, party_id: UUID | None) -> Party | None:
    if party_id is None:
        return None
    row = db.scalar(select(Party).where(Party.id == party_id, Party.tenant_id == tenant_id, Party.status == "ACTIVE", Party.deleted_at.is_(None)))
    if not row:
        raise HTTPException(400, "Customer does not belong to this workspace")
    return row


def _tenant_branch(db: Session, tenant_id: UUID, branch_id: UUID | None) -> Branch | None:
    if branch_id is None:
        return None
    row = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.tenant_id == tenant_id, Branch.status == "ACTIVE"))
    if not row:
        raise HTTPException(400, "Branch does not belong to this workspace")
    return row


def _channel(db: Session, tenant_id: UUID, channel_id: UUID, currency: str | None = None):
    row = db.execute(text("""
      SELECT id,tenant_id,name,channel_type,provider,currency_code,active,created_at,updated_at
      FROM payment_channels WHERE tenant_id=:tenant_id AND id=:id
    """), {"tenant_id": str(tenant_id), "id": str(channel_id)}).mappings().first()
    if not row or not row["active"]:
        raise HTTPException(400, "Payment channel does not exist or is inactive")
    if row["channel_type"] not in CHANNEL_TYPES:
        raise HTTPException(500, "Payment channel configuration is invalid")
    if currency and row["currency_code"].upper() != currency.upper():
        raise HTTPException(400, "Payment channel currency does not match the sale currency")
    return row


def _emit(db: Session, tenant_id: UUID, actor: UUID, action: str, event: str, aggregate_type: str, aggregate_id: UUID, payload: dict[str, Any], request_id: str | None):
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action=action, target_type=aggregate_type, target_id=aggregate_id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type=event, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload=jsonable_encoder(payload), actor_user_id=actor, correlation_id=request_id)


@router.get("/dashboard")
def dashboard(business_date: date | None = None, ctx=Depends(require_permission("sales.read"))):
    db, actor_id, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)
    # The tenant's business calendar is authoritative, not the API host's UTC date.
    today = business_date or db.execute(
        text("SELECT public.lexa_business_date(now(), :tenant_id)"),
        {"tenant_id": str(tenant_id)},
    ).scalar_one()
    # A tenant's profile currency is the reporting currency shown on the
    # Command Centre. Do not add values from different currencies together.
    currency_code = require_business_currency(db, tenant_id)
    # Revenue follows the date the sale was completed, using the tenant's
    # business calendar. Collection is a separate measure: payments recorded
    # on the business date, including later receivable payments, are summed
    # from the payments ledger rather than copied from sale.amount_paid.
    sales = db.execute(text("""
      SELECT COALESCE(SUM(s.total),0) sales,
             COALESCE((
               SELECT SUM(p.amount)
               FROM public.payments AS p
               WHERE p.tenant_id=:tenant_id
                 AND p.currency_code=:currency_code
                 AND p.status='RECORDED'
                 AND p.business_date=:business_date
             ),0) collected,
             COALESCE(SUM(s.amount_due),0) credit
      FROM public.sales AS s
      WHERE s.tenant_id=:tenant_id
        AND s.currency_code=:currency_code
        AND s.business_date=:business_date
        AND s.status='COMPLETED'
    """), {"tenant_id": str(tenant_id), "business_date": today, "currency_code": currency_code}).mappings().one()
    channels = db.execute(text("""
      SELECT pc.id,pc.name,pc.channel_type,pc.currency_code,pc.active,
             COALESCE(SUM(p.amount) FILTER (WHERE p.status='RECORDED' AND p.business_date=:business_date),0)
             - COALESCE((SELECT SUM(r.amount) FROM refund_records r WHERE r.tenant_id=pc.tenant_id AND r.payment_channel_id=pc.id AND r.business_date=:business_date AND r.status='RECORDED'),0) expected
      FROM public.payment_channels AS pc LEFT JOIN public.payments AS p ON p.payment_channel_id=pc.id AND p.tenant_id=pc.tenant_id
      WHERE pc.tenant_id=:tenant_id GROUP BY pc.id ORDER BY pc.name
    """), {"tenant_id": str(tenant_id), "business_date": today}).mappings().all()
    recv = db.execute(text("""SELECT COALESCE(SUM(r.balance),0) outstanding FROM public.receivables AS r JOIN public.sales AS s ON s.tenant_id=r.tenant_id AND s.id=r.sale_id WHERE r.tenant_id=:tenant_id AND s.currency_code=:currency_code AND r.status IN ('OPEN','PARTIALLY_PAID')"""), {"tenant_id":str(tenant_id), "currency_code": currency_code}).mappings().one()
    return {"business_date": today, "currency_code": currency_code, "sales": out(sales), "payment_channels":[out(x) for x in channels], "outstanding_receivables":str(recv["outstanding"])}


@router.get("/customers")
def list_customers(search: str | None = Query(default=None, max_length=100), ctx=Depends(require_permission("customers.read"))):
    db, _, tenant_id, _ = ctx
    params={"tenant_id":str(tenant_id)}
    clause=""
    if search and search.strip():
        clause=" AND (p.display_name ILIKE :search OR COALESCE(p.phone,'') ILIKE :search OR COALESCE(p.email,'') ILIKE :search)"
        params["search"]='%'+search.strip()+'%'
    rows=db.execute(text(f"""
      SELECT cp.id,cp.party_id,p.display_name,p.party_type,p.email,p.phone,cp.credit_limit,cp.status,cp.notes,cp.created_at
      FROM customer_profiles cp JOIN parties p ON p.id=cp.party_id AND p.tenant_id=cp.tenant_id
      WHERE cp.tenant_id=:tenant_id {clause} ORDER BY p.display_name LIMIT 200
    """),params).mappings().all()
    return [out(x) for x in rows]


@router.get("/customers/{party_id}/history")
def customer_sales_history(
    party_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    ctx=Depends(require_permission("sales.read")),
):
    """Return a customer-ID keyed, branch-scoped sales/returns/credit timeline."""
    db, actor_id, tenant_id, _ = ctx
    customer = db.execute(text("""
      SELECT cp.party_id, p.display_name
      FROM customer_profiles cp
      JOIN parties p ON p.id=cp.party_id AND p.tenant_id=cp.tenant_id
      WHERE cp.tenant_id=:t AND cp.party_id=:party_id
    """), {"t": str(tenant_id), "party_id": str(party_id)}).mappings().first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    rows = db.execute(text("""
      SELECT s.id,s.transaction_id,s.customer_party_id,p.display_name customer_name,
             s.branch_id,s.location_id,s.currency_code,s.business_date,s.status,
             s.subtotal,s.discount_total,s.tax_total,s.total,s.amount_paid,s.amount_due,
             s.return_adjustment_amount,s.created_at,s.completed_at,
             COALESCE((SELECT count(*) FROM sale_returns sr
                       WHERE sr.tenant_id=s.tenant_id AND sr.sale_id=s.id),0) return_count,
             COALESCE((SELECT sum(sr.total) FROM sale_returns sr
                       WHERE sr.tenant_id=s.tenant_id AND sr.sale_id=s.id AND sr.status='COMPLETED'),0) returned_total,
             COALESCE((SELECT sum(rr.amount)
                       FROM refund_records rr JOIN sale_returns sr
                         ON sr.id=rr.return_id AND sr.tenant_id=rr.tenant_id
                       WHERE rr.tenant_id=s.tenant_id AND sr.sale_id=s.id
                         AND sr.status='COMPLETED' AND rr.status='RECORDED'),0) refund_total,
             COALESCE((SELECT sum(cc.original_amount) FROM customer_credits cc
                       JOIN sale_returns sr ON sr.id=cc.source_return_id AND sr.tenant_id=cc.tenant_id
                       WHERE cc.tenant_id=s.tenant_id AND sr.sale_id=s.id AND sr.status='COMPLETED'),0) customer_credit_total,
             COALESCE((SELECT sum(cc.balance) FROM customer_credits cc
                       JOIN sale_returns sr ON sr.id=cc.source_return_id AND sr.tenant_id=cc.tenant_id
                       WHERE cc.tenant_id=s.tenant_id AND sr.sale_id=s.id AND sr.status='COMPLETED'
                         AND cc.status IN ('OPEN','PARTIALLY_USED')),0) remaining_customer_credit,
             COALESCE((SELECT jsonb_agg(jsonb_build_object(
                         'id',sr.id::text,'status',sr.status,'reason',sr.reason,'total',sr.total,
                         'created_at',sr.created_at,'completed_at',sr.completed_at,
                         'refunded',COALESCE((SELECT sum(rr.amount) FROM refund_records rr
                           WHERE rr.tenant_id=sr.tenant_id AND rr.return_id=sr.id AND rr.status='RECORDED'),0),
                         'credit_balance',COALESCE((SELECT sum(cc.balance) FROM customer_credits cc
                           WHERE cc.tenant_id=sr.tenant_id AND cc.source_return_id=sr.id
                             AND cc.status IN ('OPEN','PARTIALLY_USED')),0)
                       ) ORDER BY sr.created_at DESC)
                       FROM sale_returns sr WHERE sr.tenant_id=s.tenant_id AND sr.sale_id=s.id), '[]'::jsonb) returns
      FROM sales s
      LEFT JOIN parties p ON p.id=s.customer_party_id AND p.tenant_id=s.tenant_id
      WHERE s.tenant_id=:t AND s.customer_party_id=:party_id AND s.branch_id IS NOT NULL
        AND EXISTS (
          SELECT 1 FROM tenant_memberships tm
          JOIN membership_branch_assignments mba ON mba.membership_id=tm.id AND mba.tenant_id=tm.tenant_id
          JOIN branches b ON b.id=mba.branch_id AND b.tenant_id=mba.tenant_id
          WHERE tm.tenant_id=s.tenant_id AND tm.user_id=:u AND tm.status='ACTIVE'
            AND mba.status='ACTIVE' AND b.status='ACTIVE' AND b.id=s.branch_id
        )
      ORDER BY s.created_at DESC,s.id DESC LIMIT :lim OFFSET :off
    """), {"t": str(tenant_id), "u": str(actor_id), "party_id": str(party_id), "lim": limit, "off": offset}).mappings().all()
    return [out(row) for row in rows]


@router.post("/customers", status_code=201)
def create_customer(body: CustomerCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("customers.manage"))):
    db, actor, tenant_id, _ = ctx
    idem, cached, status_code, cached_body = _idempotency(db,tenant_id,idempotency_key,"commerce.customer.create",body.model_dump(mode="json"))
    if cached: return cached_body
    party = Party(tenant_id=tenant_id, party_type=body.party_type, display_name=body.display_name.strip(), legal_name=body.legal_name, email=body.email, phone=body.phone, status="ACTIVE", metadata_json={})
    db.add(party); db.flush()
    db.add(PartyRole(tenant_id=tenant_id, party_id=party.id, role_type="CUSTOMER", status="ACTIVE", metadata_json={}))
    row=db.execute(text("""INSERT INTO customer_profiles(tenant_id,party_id,credit_limit,status,notes) VALUES(:t,:p,:l,'ACTIVE',:n) RETURNING id,party_id,credit_limit,status,notes,created_at"""),{"t":str(tenant_id),"p":str(party.id),"l":str(q(body.credit_limit)),"n":body.notes}).mappings().one()
    db.flush(); _emit(db,tenant_id,actor,"customer.created","CUSTOMER_CREATED","customer",party.id,{"display_name":party.display_name},request_id)
    result={**out(row),"display_name":party.display_name,"party_type":party.party_type,"email":party.email,"phone":party.phone}
    _finish(db,idem,201,result,"customer",party.id); db.commit(); return result


@router.get("/payment-channels")
def list_channels(ctx=Depends(require_permission("payments.read"))):
    db,_,tenant_id,_=ctx
    rows=db.execute(text("SELECT id,tenant_id,name,channel_type,provider,currency_code,active,created_at,updated_at FROM payment_channels WHERE tenant_id=:t ORDER BY active DESC,name"),{"t":str(tenant_id)}).mappings().all()
    return [out(x) for x in rows]


@router.post("/payment-channels", status_code=201)
def create_channel(body: ChannelCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("financial.configure"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.payment_channel.create",body.model_dump(mode="json"))
    if cached: return cached_body
    row=db.execute(text("""INSERT INTO payment_channels(tenant_id,name,channel_type,provider,currency_code,active) VALUES(:t,:n,:ct,:p,:c,true) RETURNING id,tenant_id,name,channel_type,provider,currency_code,active,created_at,updated_at"""),{"t":str(tenant_id),"n":body.name.strip(),"ct":body.channel_type,"p":body.provider,"c":body.currency_code}).mappings().one()
    _emit(db,tenant_id,actor,"payment_channel.created","PAYMENT_CHANNEL_CREATED","payment_channel",row["id"],{"name":row["name"],"channel_type":row["channel_type"],"currency_code":row["currency_code"]},request_id)
    result=out(row); _finish(db,idem,201,result,"payment_channel",row["id"]); db.commit(); return result


@router.post("/payment-channels/{channel_id}/deactivate")
def deactivate_channel(
    channel_id: UUID,
    body: ChannelDeactivate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
    ctx=Depends(require_permission("financial.configure")),
):
    """Stop a payment method being selected for new entries without deleting history."""
    db, actor, tenant_id, _ = ctx
    payload = {"channel_id": str(channel_id), "reason": body.reason.strip()}
    idem, cached, _, cached_body = _idempotency(db, tenant_id, idempotency_key, "commerce.payment_channel.deactivate", payload)
    if cached:
        return cached_body
    try:
        row = db.execute(text("""
          SELECT id,tenant_id,name,channel_type,provider,currency_code,active,created_at,updated_at
          FROM payment_channels WHERE tenant_id=:t AND id=:id FOR UPDATE
        """), {"t": str(tenant_id), "id": str(channel_id)}).mappings().first()
        if not row:
            raise HTTPException(404, "Payment method not found")
        if row["active"]:
            db.execute(text("UPDATE payment_channels SET active=false,updated_at=now() WHERE tenant_id=:t AND id=:id"), {"t": str(tenant_id), "id": str(channel_id)})
            _emit(db, tenant_id, actor, "payment_method.deactivated", "PAYMENT_METHOD_DEACTIVATED", "payment_channel", channel_id, {"name": row["name"], "reason": body.reason.strip()}, request_id)
        updated = db.execute(text("""
          SELECT id,tenant_id,name,channel_type,provider,currency_code,active,created_at,updated_at
          FROM payment_channels WHERE tenant_id=:t AND id=:id
        """), {"t": str(tenant_id), "id": str(channel_id)}).mappings().one()
        result = out(updated)
        _finish(db, idem, 200, result, "payment_channel", channel_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, "Could not update this payment method. Refresh and try again.") from exc


@router.get("/capabilities")
def commerce_capabilities(ctx=Depends(require_permission("sales.read"))):
    """Expose UI hints only; checkout repeats every authorization check server-side."""
    db, actor_id, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor_id)
    granted = {row[0] for row in db.execute(text("""
      SELECT DISTINCT p.code
      FROM membership_roles mr
      JOIN roles r ON r.id=mr.role_id AND r.tenant_id=:tenant_id
      JOIN role_permissions rp ON rp.role_id=r.id
      JOIN permissions p ON p.id=rp.permission_id
      JOIN tenant_memberships tm ON tm.id=mr.membership_id AND tm.tenant_id=:tenant_id
      WHERE tm.user_id=:user_id AND tm.status='ACTIVE'
        AND p.code IN ('catalog.pricing.manage','catalog.manage','sales.manage')
    """), {"tenant_id":str(tenant_id), "user_id":str(actor_id)}).all()}
    return {
        "can_manage_price": bool({"catalog.pricing.manage", "catalog.manage"} & granted),
        "can_manage_sales": "sales.manage" in granted,
    }


@router.get("/products")
def commerce_products(business_date: date | None = None, ctx=Depends(require_permission("sales.read"))):
    db,_,tenant_id,_=ctx
    pricing_date = business_date or db.execute(text("SELECT public.lexa_business_date(now(), :tenant_id)"), {"tenant_id":str(tenant_id)}).scalar_one()
    rows=db.execute(text("""
      SELECT pv.id variant_id,pv.sku,pv.name variant_name,p.name product_name,pv.track_inventory,
             COALESCE(pp.unit_price,0) selling_price,
             COALESCE(tx.rate_percent,0) effective_tax_rate,
             COALESCE(tx.inclusive,false) tax_inclusive,
             tx.code tax_code,
             CASE WHEN tx.tax_rate_id IS NULL THEN 'NO_MATCHING_TAX_RULE' ELSE 'EFFECTIVE_DATED_TENANT_RULE' END tax_rule_source
      FROM product_variants pv JOIN products p ON p.id=pv.product_id AND p.tenant_id=pv.tenant_id
      LEFT JOIN LATERAL (SELECT unit_price FROM product_prices x WHERE x.tenant_id=pv.tenant_id AND x.variant_id=pv.id AND x.effective_from<=:business_date AND (x.effective_to IS NULL OR x.effective_to>=:business_date) ORDER BY x.effective_from DESC LIMIT 1) pp ON true
      LEFT JOIN LATERAL (SELECT tax_rate_id,code,rate_percent,inclusive FROM public.resolve_tax_rate(pv.tenant_id,p.id,p.category_id,:business_date)) tx ON true
      WHERE pv.tenant_id=:t AND pv.deleted_at IS NULL AND pv.status='ACTIVE' AND p.deleted_at IS NULL AND p.status='ACTIVE'
      ORDER BY p.name,pv.name LIMIT 500
    """),{"t":str(tenant_id),"business_date":pricing_date}).mappings().all()
    return [out(x) for x in rows]


@router.get("/sales")
def list_sales(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100000),
    search: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=20),
    start_date: date | None = None,
    end_date: date | None = None,
    branch_id: UUID | None = None,
    payment_channel_id: UUID | None = None,
    ctx=Depends(require_permission("sales.read")),
):
    """List only sales in the caller's assigned branches, with safe bound filters."""
    db, actor_id, tenant_id, _ = ctx
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be on or before end_date")
    if branch_id is not None:
        ensure_branch_access(db, tenant_id=tenant_id, user_id=actor_id, branch_id=branch_id)
    params: dict[str, Any] = {"t": str(tenant_id), "u": str(actor_id), "lim": limit, "off": offset}
    filters = ["s.tenant_id=:t", "EXISTS (SELECT 1 FROM tenant_memberships tm JOIN membership_branch_assignments mba ON mba.membership_id=tm.id AND mba.tenant_id=tm.tenant_id JOIN branches b ON b.id=mba.branch_id AND b.tenant_id=mba.tenant_id WHERE tm.tenant_id=s.tenant_id AND tm.user_id=:u AND tm.status='ACTIVE' AND mba.status='ACTIVE' AND b.status='ACTIVE' AND b.id=s.branch_id)"]
    if status and status.strip():
        filters.append("s.status=:status")
        params["status"] = status.strip().upper()
    if search and search.strip():
        filters.append("(COALESCE(p.display_name,'') ILIKE :search OR s.id::text ILIKE :search OR s.transaction_id::text ILIKE :search)")
        params["search"] = f"%{search.strip()}%"
    if start_date:
        filters.append("s.business_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        filters.append("s.business_date <= :end_date")
        params["end_date"] = end_date
    if branch_id is not None:
        filters.append("s.branch_id=:branch_id")
        params["branch_id"] = str(branch_id)
    if payment_channel_id is not None:
        filters.append("EXISTS (SELECT 1 FROM payments payment_filter WHERE payment_filter.tenant_id=s.tenant_id AND payment_filter.transaction_id=s.transaction_id AND payment_filter.payment_channel_id=:payment_channel_id AND payment_filter.status='RECORDED')")
        params["payment_channel_id"] = str(payment_channel_id)
    rows = db.execute(text(f"""
      SELECT s.id,s.transaction_id,s.customer_party_id,p.display_name customer_name,s.branch_id,s.location_id,
             s.currency_code,s.business_date,s.status,s.subtotal,s.discount_total,s.tax_total,s.total,s.amount_paid,s.amount_due,
             s.return_adjustment_amount,s.created_at,s.completed_at
      FROM sales s LEFT JOIN parties p ON p.id=s.customer_party_id AND p.tenant_id=s.tenant_id
      WHERE {' AND '.join(filters)}
      ORDER BY s.created_at DESC, s.id DESC LIMIT :lim OFFSET :off
    """), params).mappings().all()
    return [out(x) for x in rows]


@router.get("/sales/{sale_id}")
def get_sale(sale_id: UUID, ctx=Depends(require_permission("sales.read"))):
    db,actor_id,tenant_id,_=ctx
    sale=db.execute(text("""
      SELECT s.id,s.transaction_id,s.customer_party_id,p.display_name customer_name,s.branch_id,s.location_id,s.currency_code,s.business_date,s.status,
             s.subtotal,s.discount_total,s.tax_total,s.total,s.amount_paid,s.amount_due,s.return_adjustment_amount,s.notes,s.created_at,s.completed_at
      FROM sales s LEFT JOIN parties p ON p.id=s.customer_party_id AND p.tenant_id=s.tenant_id
      WHERE s.tenant_id=:t AND s.id=:s
    """),{"t":str(tenant_id),"s":str(sale_id)}).mappings().first()
    if not sale:
        raise HTTPException(404,"Sale not found")
    if sale["branch_id"] is None:
        raise HTTPException(403, "Sale is not linked to an accessible branch")
    ensure_branch_access(db, tenant_id=tenant_id, user_id=actor_id, branch_id=sale["branch_id"])
    lines=db.execute(text("""
      SELECT tl.id sale_line_id,tl.product_variant_id,pv.sku,pv.name variant_name,tl.quantity,tl.unit_price,tl.discount_amount,tl.tax_amount,tl.line_total
      FROM transaction_lines tl LEFT JOIN product_variants pv ON pv.id=tl.product_variant_id AND pv.tenant_id=tl.tenant_id
      WHERE tl.tenant_id=:t AND tl.transaction_id=:tx ORDER BY tl.line_no
    """),{"t":str(tenant_id),"tx":str(sale["transaction_id"])}).mappings().all()
    payments=db.execute(text("""
      SELECT p.id,p.payment_channel_id,pc.name channel_name,p.amount AS payment_amount,pa.amount AS allocated_amount,
             p.currency_code,p.method,p.reference,p.business_date,p.paid_at,p.status,
             CASE WHEN pa.sale_id IS NOT NULL THEN 'SALE' ELSE 'RECEIVABLE' END allocation_type
      FROM payment_allocations pa
      JOIN payments p ON p.id=pa.payment_id AND p.tenant_id=pa.tenant_id
      LEFT JOIN payment_channels pc ON pc.id=p.payment_channel_id AND pc.tenant_id=p.tenant_id
      LEFT JOIN receivables r ON r.id=pa.receivable_id AND r.tenant_id=pa.tenant_id
      WHERE pa.tenant_id=:t AND pa.status='RECORDED' AND p.status='RECORDED'
        AND (pa.sale_id=:s OR r.sale_id=:s)
      ORDER BY p.paid_at,p.id
    """),{"t":str(tenant_id),"s":str(sale_id)}).mappings().all()
    returns=db.execute(text("""
      SELECT sr.id,sr.sale_id,sr.status,sr.reason,sr.total,sr.completed_at,sr.created_at,
             COALESCE((SELECT SUM(rr.amount) FROM refund_records rr WHERE rr.return_id=sr.id AND rr.tenant_id=sr.tenant_id AND rr.status='RECORDED'),0) refunded,
             COALESCE((SELECT MAX(cc.balance) FROM customer_credits cc WHERE cc.source_return_id=sr.id AND cc.tenant_id=sr.tenant_id),0) credit_balance,
             (SELECT je.id FROM journal_entries je WHERE je.tenant_id=sr.tenant_id AND je.source_type='SALE_RETURN' AND je.source_id=sr.id AND je.entry_role='RETURN_SETTLEMENT' LIMIT 1) journal_entry_id,
             (SELECT fd.id FROM fiscal_documents fd WHERE fd.tenant_id=sr.tenant_id AND fd.source_type='SALE_RETURN' AND fd.source_id=sr.id AND fd.document_type='CREDIT_NOTE' ORDER BY fd.created_at DESC LIMIT 1) fiscal_document_id,
             (SELECT fd.status FROM fiscal_documents fd WHERE fd.tenant_id=sr.tenant_id AND fd.source_type='SALE_RETURN' AND fd.source_id=sr.id AND fd.document_type='CREDIT_NOTE' ORDER BY fd.created_at DESC LIMIT 1) fiscal_document_status
      FROM sale_returns sr WHERE sr.tenant_id=:t AND sr.sale_id=:s
      ORDER BY sr.created_at,sr.id
    """),{"t":str(tenant_id),"s":str(sale_id)}).mappings().all()
    refunds=db.execute(text("""
      SELECT rr.id,rr.return_id,rr.payment_channel_id,pc.name channel_name,rr.amount,rr.currency_code,rr.reference,rr.business_date,rr.status,sr.reason
      FROM refund_records rr
      JOIN sale_returns sr ON sr.id=rr.return_id AND sr.tenant_id=rr.tenant_id
      LEFT JOIN payment_channels pc ON pc.id=rr.payment_channel_id AND pc.tenant_id=rr.tenant_id
      WHERE rr.tenant_id=:t AND sr.sale_id=:s
      ORDER BY rr.business_date,rr.id
    """),{"t":str(tenant_id),"s":str(sale_id)}).mappings().all()
    result=out(sale)
    accounting_entries=db.execute(text("""
      SELECT je.id,je.source_type,je.source_id,je.entry_role,je.entry_date,je.reference,
             je.description,je.currency_code,je.status,je.posted_at
      FROM journal_entries je
      WHERE je.tenant_id=:t AND (
        (je.source_type='SALE' AND je.source_id=:s)
        OR (je.source_type='PAYMENT' AND je.source_id IN (
          SELECT p.id FROM payment_allocations pa JOIN payments p ON p.tenant_id=pa.tenant_id AND p.id=pa.payment_id
          LEFT JOIN receivables r ON r.tenant_id=pa.tenant_id AND r.id=pa.receivable_id
          WHERE pa.tenant_id=:t AND (pa.sale_id=:s OR r.sale_id=:s)
        ))
        OR (je.source_type='SALE_RETURN' AND je.source_id IN (SELECT sr.id FROM sale_returns sr WHERE sr.tenant_id=:t AND sr.sale_id=:s))
      )
      ORDER BY je.entry_date,je.created_at,je.id
    """),{"t":str(tenant_id),"s":str(sale_id)}).mappings().all()
    result["lines"]=[out(x) for x in lines]
    result["payments"]=[out(x) for x in payments]
    result["returns"]=[out(x) for x in returns]
    result["refunds"]=[out(x) for x in refunds]
    result["accounting_entries"]=[out(x) for x in accounting_entries]
    return result


@router.post("/sales", status_code=201)
def create_sale(body: SaleCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("sales.complete"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.sale.create",body.model_dump(mode="json"))
    if cached: return cached_body
    try:
        currency = require_business_currency(db, tenant_id)
        if body.currency_code != currency:
            raise HTTPException(409, "Sale currency must match the saved business currency; foreign-currency checkout is not enabled.")
        _tenant_party(db,tenant_id,body.customer_party_id); _tenant_branch(db,tenant_id,body.branch_id)
        if body.location_id is None: raise HTTPException(400,"A sale location is required for inventory-safe checkout")
        tenant_location(db,tenant_id,body.location_id)
        location_branch_id = ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=body.location_id)
        if body.branch_id and body.branch_id != location_branch_id:
            raise HTTPException(400,"Sale branch must match the selected stock location branch")
        branch_id = body.branch_id or location_branch_id
        # Price changes and discounts are business controls, not trusted client data.
        # Cashiers can sell at the configured catalogue price; only members with
        # explicit pricing/sales-management capabilities may override it.
        granted = {row[0] for row in db.execute(text("""
          SELECT DISTINCT p.code
          FROM membership_roles mr
          JOIN roles r ON r.id=mr.role_id AND r.tenant_id=:tenant_id
          JOIN role_permissions rp ON rp.role_id=r.id
          JOIN permissions p ON p.id=rp.permission_id
          JOIN tenant_memberships tm ON tm.id=mr.membership_id AND tm.tenant_id=:tenant_id
          WHERE tm.user_id=:user_id AND tm.status='ACTIVE'
            AND p.code IN ('catalog.pricing.manage','catalog.manage','sales.manage')
        """), {"tenant_id":str(tenant_id),"user_id":str(actor)}).all()}
        can_manage_price = bool({"catalog.pricing.manage", "catalog.manage"} & granted)
        can_manage_sales = "sales.manage" in granted
        subtotal=Decimal("0"); discount=Decimal("0"); tax=Decimal("0"); total=Decimal("0")
        validated=[]
        for line in body.lines:
            variant=tenant_variant(db,tenant_id,line.variant_id)
            catalog_price = db.execute(text("""
              SELECT unit_price FROM product_prices
              WHERE tenant_id=:t AND variant_id=:v
                AND effective_from<=:business_date::timestamptz
                AND (effective_to IS NULL OR effective_to>=:business_date::timestamptz)
              ORDER BY effective_from DESC LIMIT 1
            """), {"t":str(tenant_id),"v":str(line.variant_id),"business_date":body.business_date}).scalar_one_or_none()
            if catalog_price is None and not can_manage_price:
                raise HTTPException(409, "No catalogue price is configured for this product; ask a pricing manager to set one")
            if catalog_price is not None and q(line.unit_price) != q(Decimal(str(catalog_price))) and not can_manage_price:
                raise HTTPException(403, "Price override permission required; use the catalogue price or ask a manager")
            if line.discount_amount > 0 and not can_manage_sales:
                raise HTTPException(403, "Discount permission required; ask a manager to apply this discount")

            # Tax is resolved on the server from the tenant's effective-dated
            # PRODUCT/CATEGORY/DEFAULT rule. The client rate is only a display hint.
            product_context = db.execute(text("""
              SELECT p.id AS product_id, p.category_id
              FROM products p
              WHERE p.tenant_id=:t AND p.id=:product_id AND p.status='ACTIVE' AND p.deleted_at IS NULL
            """), {"t":str(tenant_id), "product_id":str(variant.product_id)}).mappings().first()
            if not product_context:
                raise HTTPException(400, "This product is unavailable for sale")
            tax_rule = db.execute(text("""
              SELECT tax_rate_id,code,rate_percent,inclusive
              FROM public.resolve_tax_rate(:tenant_id,:product_id,:category_id,:business_date)
            """), {
                "tenant_id":str(tenant_id),
                "product_id":str(product_context["product_id"]),
                "category_id":str(product_context["category_id"]),
                "business_date":body.business_date,
            }).mappings().first()
            effective_tax_rate = Decimal(str(tax_rule["rate_percent"])) if tax_rule else Decimal("0")
            tax_inclusive = bool(tax_rule["inclusive"]) if tax_rule else False

            gross=q(line.quantity*line.unit_price)
            if line.discount_amount>gross: raise HTTPException(422,"Line discount cannot exceed line value")
            try:
                line_tax,line_total=calculate_line_tax(gross,line.discount_amount,effective_tax_rate,inclusive=tax_inclusive)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            subtotal+=gross; discount+=q(line.discount_amount); tax+=line_tax; total+=line_total
            validated.append((line,variant,line_total,line_tax,effective_tax_rate,tax_inclusive,tax_rule))
        subtotal=q(subtotal); discount=q(discount); tax=q(tax); total=q(total)
        if total<=0: raise HTTPException(422,"Sale total must be greater than zero")
        paid=q(sum((x.amount for x in body.payments),Decimal("0")))
        if paid>total: raise HTTPException(422,"Payment allocations cannot exceed sale total")
        if paid<total and body.customer_party_id is None: raise HTTPException(400,"A customer is required for credit/outstanding sales")
        ref=f"SAL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
        tx=BusinessTransaction(tenant_id=tenant_id,transaction_type="SALE",reference=ref,status="DRAFT",party_id=body.customer_party_id,branch_id=branch_id,total_amount=total,currency_code=currency,occurred_at=datetime.now(timezone.utc),metadata_json={"source":"commerce"})
        db.add(tx); db.flush()
        db.add(TransactionLine(tenant_id=tenant_id,transaction_id=tx.id,line_no=1,line_type="PRODUCT",product_variant_id=validated[0][1].id,description=validated[0][1].name,quantity=validated[0][0].quantity,unit_price=validated[0][0].unit_price,line_total=validated[0][2],currency_code=currency,discount_amount=validated[0][0].discount_amount,tax_rate=validated[0][4],tax_amount=validated[0][3],metadata_json={"tax_inclusive":validated[0][5],"tax_code":validated[0][6]["code"] if validated[0][6] else None,"tax_rate_source":"EFFECTIVE_DATED_TENANT_RULE" if validated[0][6] else "NO_MATCHING_TAX_RULE"}) )
        for idx,(line,variant,line_total,line_tax,effective_tax_rate,tax_inclusive,tax_rule) in enumerate(validated[1:],start=2):
            db.add(TransactionLine(tenant_id=tenant_id,transaction_id=tx.id,line_no=idx,line_type="PRODUCT",product_variant_id=variant.id,description=variant.name,quantity=line.quantity,unit_price=line.unit_price,line_total=line_total,currency_code=currency,discount_amount=line.discount_amount,tax_rate=effective_tax_rate,tax_amount=line_tax,metadata_json={"tax_inclusive":tax_inclusive,"tax_code":tax_rule["code"] if tax_rule else None,"tax_rate_source":"EFFECTIVE_DATED_TENANT_RULE" if tax_rule else "NO_MATCHING_TAX_RULE"}))
        db.execute(text("""INSERT INTO sales(tenant_id,transaction_id,customer_party_id,branch_id,location_id,business_date,currency_code,status,subtotal,discount_total,tax_total,total,amount_paid,amount_due,notes,created_by)
          VALUES(:t,:tx,:cp,:b,:l,:business_date,:c,'DRAFT',:s,:d,:tax,:total,0,:due,:notes,:actor)"""),{"t":str(tenant_id),"tx":str(tx.id),"cp":str(body.customer_party_id) if body.customer_party_id else None,"b":str(branch_id),"l":str(body.location_id),"business_date":body.business_date,"c":currency,"s":str(subtotal),"d":str(discount),"tax":str(tax),"total":str(total),"due":str(total),"notes":body.notes,"actor":str(actor)})
        sale_id=db.execute(text("SELECT id FROM sales WHERE tenant_id=:t AND transaction_id=:tx"),{"t":str(tenant_id),"tx":str(tx.id)}).scalar_one()
        for idx,(line,variant,_,_,_,_,_) in enumerate(validated, start=1):
            invtx=post_ledger(db,tenant_id=tenant_id,actor_user_id=actor,location_id=body.location_id,variant_id=variant.id,quantity_delta=-q(line.quantity),unit_cost=Decimal("0"),transaction_type="SALE",reference_type="sale",reference_id=sale_id,idempotency_key=f"{idempotency_key or tx.id}:inventory:{idx}",metadata={"sale_id":str(sale_id)}) if variant.track_inventory else None
            if invtx:
                _emit(db,tenant_id,actor,"stock.decreased","STOCK_DECREASED","inventory_transaction",invtx.id,{"sale_id":str(sale_id),"variant_id":str(variant.id),"quantity":str(q(line.quantity))},request_id)
        for payment in body.payments:
            ch=_channel(db,tenant_id,payment.payment_channel_id,currency)
            pid=db.execute(text("""INSERT INTO payments(tenant_id,transaction_id,party_id,amount,currency_code,method,status,reference,paid_at,metadata,payment_channel_id,business_date)
              VALUES(:t,:tx,:p,:a,:c,:m,'RECORDED',:ref,now(),:meta,:ch,:d) RETURNING id"""),{"t":str(tenant_id),"tx":str(tx.id),"p":str(body.customer_party_id) if body.customer_party_id else None,"a":str(q(payment.amount)),"c":currency,"m":ch["channel_type"],"ref":payment.reference,"meta":{},"ch":str(ch["id"]),"d":body.business_date}).scalar_one()
            db.execute(text("INSERT INTO payment_allocations(tenant_id,payment_id,sale_id,amount,status,created_by) VALUES(:t,:p,:s,:a,'RECORDED',:u)"),{"t":str(tenant_id),"p":str(pid),"s":str(sale_id),"a":str(q(payment.amount)),"u":str(actor)})
            accounting_entry_id = db.execute(text("SELECT post_payment_journal(:id,:u)"), {"id":str(pid),"u":str(actor)}).scalar_one()
            _emit(db,tenant_id,actor,"accounting.entry.posted","ACCOUNTING_ENTRY_POSTED","journal_entry",accounting_entry_id,{"payment_id":str(pid)},request_id)
            _emit(db,tenant_id,actor,"payment.recorded","PAYMENT_RECORDED","payment",pid,{"sale_id":str(sale_id),"channel_id":str(ch["id"]),"amount":str(q(payment.amount))},request_id)
            _emit(db,tenant_id,actor,"payment.allocated","PAYMENT_ALLOCATED","payment_allocation",pid,{"sale_id":str(sale_id),"amount":str(q(payment.amount))},request_id)
        paid_now=db.execute(text("SELECT amount_paid,amount_due FROM sales WHERE tenant_id=:t AND id=:s"),{"t":str(tenant_id),"s":str(sale_id)}).mappings().one()
        if Decimal(str(paid_now["amount_due"]))>0:
            rid=db.execute(text("INSERT INTO receivables(tenant_id,sale_id,customer_party_id,original_amount,paid_amount,adjustment_amount,balance,status) VALUES(:t,:s,:p,:o,0,0,:o,'OPEN') RETURNING id"),{"t":str(tenant_id),"s":str(sale_id),"p":str(body.customer_party_id),"o":str(q(paid_now["amount_due"]))}).scalar_one()
            _emit(db,tenant_id,actor,"receivable.created","RECEIVABLE_CREATED","receivable",rid,{"sale_id":str(sale_id),"balance":str(q(paid_now["amount_due"]))},request_id)
        tx.status="COMPLETED"; tx.closed_at=datetime.now(timezone.utc); db.add(tx)
        db.execute(text("INSERT INTO transaction_status_history(tenant_id,transaction_id,from_status,to_status,reason,changed_by) VALUES(:t,:tx,'DRAFT','COMPLETED','Sale completed',:u)"),{"t":str(tenant_id),"tx":str(tx.id),"u":str(actor)})
        db.execute(text("UPDATE sales SET status='COMPLETED',completed_by=:u,completed_at=now(),updated_at=now() WHERE tenant_id=:t AND id=:s"),{"u":str(actor),"t":str(tenant_id),"s":str(sale_id)})
        _emit(db,tenant_id,actor,"sale.created","SALE_CREATED","sale",sale_id,{"reference":ref,"total":str(total)},request_id)
        accounting_sale_entry = db.execute(text("SELECT post_sale_journal(:id,:u)"), {"id":str(sale_id),"u":str(actor)}).scalar_one()
        cogs_entry = db.execute(text("SELECT post_sale_cogs_journal(:id,:u)"), {"id":str(sale_id),"u":str(actor)}).scalar()
        _emit(db,tenant_id,actor,"accounting.entry.posted","ACCOUNTING_ENTRY_POSTED","journal_entry",accounting_sale_entry,{"sale_id":str(sale_id),"entry_role":"SALE_RECOGNITION"},request_id)
        if cogs_entry:
            _emit(db,tenant_id,actor,"accounting.entry.posted","ACCOUNTING_ENTRY_POSTED","journal_entry",cogs_entry,{"sale_id":str(sale_id),"entry_role":"COGS"},request_id)
        _emit(db,tenant_id,actor,"sale.completed","SALE_COMPLETED","sale",sale_id,{"reference":ref,"total":str(total),"paid":str(paid_now["amount_paid"]),"due":str(paid_now["amount_due"]),"accounting_journal_id":str(accounting_sale_entry)},request_id)
        # If system-to-system EFRIS is enabled and the taxpayer is active, create
        # an idempotent fiscalization work item in the same transaction as the sale.
        # Queueing is not treated as proof that URA accepted an e-document.
        fiscal_document_id = None
        efris = db.execute(text("SELECT enabled,integration_mode,registration_status FROM efris_configurations WHERE tenant_id=:t"), {"t":str(tenant_id)}).mappings().first()
        if efris and efris["enabled"] and efris["registration_status"] == "ACTIVE" and efris["integration_mode"] == "SYSTEM_TO_SYSTEM":
            fiscal_document_id = db.execute(text("SELECT public.create_fiscal_document_for_sale(:id,'INVOICE')"), {"id":str(sale_id)}).scalar_one()
            _emit(db,tenant_id,actor,"fiscalization.queued","FISCALIZATION_QUEUED","fiscal_document",fiscal_document_id,{"sale_id":str(sale_id),"status":"PENDING","reason":"Queued for the configured URA system-to-system adapter"},request_id)
        result=db.execute(text("SELECT s.id,s.transaction_id,s.currency_code,s.business_date,s.status,s.subtotal,s.discount_total,s.tax_total,s.total,s.amount_paid,s.amount_due,s.created_at,s.completed_at FROM sales s WHERE s.tenant_id=:t AND s.id=:s"),{"t":str(tenant_id),"s":str(sale_id)}).mappings().one()
        result=out(result)
        result["fiscal_document_id"] = str(fiscal_document_id) if fiscal_document_id else None
        result["fiscalization_status"] = "PENDING" if fiscal_document_id else ("MANUAL_REQUIRED" if efris and efris["enabled"] and efris["registration_status"] == "ACTIVE" and efris["integration_mode"] == "MANUAL" else "NOT_CONFIGURED")
        _finish(db,idem,201,result,"sale",sale_id); db.commit(); return result
    except HTTPException:
        db.rollback(); raise
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409,"Sale could not be committed because a business invariant was violated") from exc
    except Exception as exc:
        db.rollback(); raise HTTPException(500,"Sale creation failed") from exc


@router.get("/receivables")
def list_receivables(ctx=Depends(require_permission("receivables.read"))):
    db,_,tenant_id,_=ctx
    rows=db.execute(text("""
      SELECT r.id,r.sale_id,r.customer_party_id,p.display_name customer_name,r.original_amount,r.paid_amount,r.adjustment_amount,r.balance,r.status,r.due_at,r.created_at
      FROM receivables r JOIN parties p ON p.id=r.customer_party_id AND p.tenant_id=r.tenant_id
      JOIN sales s ON s.id=r.sale_id AND s.tenant_id=r.tenant_id
      WHERE r.tenant_id=:t AND r.status IN ('OPEN','PARTIALLY_PAID') AND EXISTS (
        SELECT 1 FROM membership_branch_assignments mba JOIN tenant_memberships tm ON tm.id=mba.membership_id AND tm.tenant_id=mba.tenant_id
        WHERE mba.tenant_id=r.tenant_id AND tm.user_id=:u AND tm.status='ACTIVE' AND mba.status='ACTIVE' AND mba.branch_id=s.branch_id
      ) ORDER BY r.created_at DESC LIMIT 500
    """),{"t":str(tenant_id),"u":str(ctx[1])}).mappings().all()
    return [out(x) for x in rows]


@router.post("/receivables/{receivable_id}/payments", status_code=201)
def pay_receivable(receivable_id: UUID, body: PaymentCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("payments.allocate"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.receivable.payment",body.model_dump(mode="json") | {"receivable_id":str(receivable_id)})
    if cached: return cached_body
    receivable=db.execute(text("SELECT r.*,s.currency_code,s.transaction_id,s.customer_party_id,s.branch_id FROM receivables r JOIN sales s ON s.id=r.sale_id AND s.tenant_id=r.tenant_id WHERE r.tenant_id=:t AND r.id=:r FOR UPDATE"),{"t":str(tenant_id),"r":str(receivable_id)}).mappings().first()
    if not receivable: raise HTTPException(404,"Receivable not found")
    ensure_branch_access(db, tenant_id=tenant_id, user_id=actor, branch_id=receivable["branch_id"])
    if Decimal(str(receivable["balance"])) <= 0: raise HTTPException(409,"Receivable is already paid")
    if q(body.amount)>q(Decimal(str(receivable["balance"]))): raise HTTPException(422,"Payment exceeds receivable balance")
    ch=_channel(db,tenant_id,body.payment_channel_id,receivable["currency_code"])
    pid=db.execute(text("""INSERT INTO payments(tenant_id,transaction_id,party_id,amount,currency_code,method,status,reference,paid_at,metadata,payment_channel_id,business_date)
      VALUES(:t,:tx,:p,:a,:c,:m,'RECORDED',:ref,now(),'{}'::jsonb,:ch,:d) RETURNING id"""),{"t":str(tenant_id),"tx":str(receivable["transaction_id"]),"p":str(receivable["customer_party_id"]),"a":str(q(body.amount)),"c":receivable["currency_code"],"m":ch["channel_type"],"ref":body.reference,"ch":str(ch["id"]),"d":body.business_date}).scalar_one()
    db.execute(text("INSERT INTO payment_allocations(tenant_id,payment_id,receivable_id,amount,status,created_by) VALUES(:t,:p,:r,:a,'RECORDED',:u)"),{"t":str(tenant_id),"p":str(pid),"r":str(receivable_id),"a":str(q(body.amount)),"u":str(actor)})
    accounting_entry_id = db.execute(text("SELECT post_payment_journal(:id,:u)"), {"id":str(pid),"u":str(actor)}).scalar_one()
    _emit(db,tenant_id,actor,"accounting.entry.posted","ACCOUNTING_ENTRY_POSTED","journal_entry",accounting_entry_id,{"payment_id":str(pid),"receivable_id":str(receivable_id)},request_id)
    _emit(db,tenant_id,actor,"payment.recorded","PAYMENT_RECORDED","payment",pid,{"receivable_id":str(receivable_id),"amount":str(q(body.amount))},request_id)
    _emit(db,tenant_id,actor,"payment.allocated","PAYMENT_ALLOCATED","receivable",receivable_id,{"payment_id":str(pid),"amount":str(q(body.amount))},request_id)
    refreshed=db.execute(text("SELECT id,paid_amount,balance,status FROM receivables WHERE tenant_id=:t AND id=:r"),{"t":str(tenant_id),"r":str(receivable_id)}).mappings().one()
    result=out(refreshed); _finish(db,idem,201,result,"receivable",receivable_id); db.commit(); return result


@router.get("/reconciliations")
def list_reconciliations(business_date: date | None = None, ctx=Depends(require_permission("reconciliation.read"))):
    db,_,tenant_id,_=ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    params={"t":str(tenant_id)}; clause=""
    if business_date: clause=" AND h.business_date=:d"; params["d"]=business_date
    rows=db.execute(text(f"""
      SELECT h.id,h.business_date,h.status,h.notes,h.closed_at,l.id line_id,l.payment_channel_id,pc.name channel_name,pc.channel_type,l.expected_amount,l.actual_amount,l.variance,l.status line_status,l.notes line_notes,l.reviewed_by
      FROM daily_reconciliations h LEFT JOIN daily_reconciliation_lines l ON l.reconciliation_id=h.id AND l.tenant_id=h.tenant_id
      LEFT JOIN payment_channels pc ON pc.id=l.payment_channel_id AND pc.tenant_id=l.tenant_id
      WHERE h.tenant_id=:t {clause} ORDER BY h.business_date DESC,pc.name
    """),params).mappings().all()
    grouped={}
    for row in rows:
        key=str(row["id"]); grouped.setdefault(key,{"id":row["id"],"business_date":row["business_date"],"status":row["status"],"notes":row["notes"],"closed_at":row["closed_at"],"lines":[]})
        if row["line_id"] is not None:
            grouped[key]["lines"].append({k:row[k] for k in ["line_id","payment_channel_id","channel_name","channel_type","expected_amount","actual_amount","variance","line_status","line_notes","reviewed_by"]})
    return [{**v,"lines":[out(x) for x in v["lines"]]} for v in grouped.values()]


@router.post("/reconciliations", status_code=201)
def create_reconciliation(body: ReconciliationCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("reconciliation.manage"))):
    db,actor,tenant_id,_=ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.reconciliation.create",body.model_dump(mode="json"))
    if cached: return cached_body
    try:
        existing=db.execute(text("SELECT id,business_date,status,notes,closed_at,created_at FROM daily_reconciliations WHERE tenant_id=:t AND business_date=:d"),{"t":str(tenant_id),"d":body.business_date}).mappings().first()
        if existing:
            result=out(existing)
            _finish(db,idem,200,result,"reconciliation",existing["id"]); db.commit(); return result
        rid=db.execute(text("INSERT INTO daily_reconciliations(tenant_id,business_date,status,notes,created_by) VALUES(:t,:d,'OPEN',:n,:u) RETURNING id"),{"t":str(tenant_id),"d":body.business_date,"n":body.notes,"u":str(actor)}).scalar_one()
        db.execute(text("""INSERT INTO daily_reconciliation_lines(tenant_id,reconciliation_id,payment_channel_id)
          SELECT :t,:r,pc.id FROM payment_channels pc
          WHERE pc.tenant_id=:t AND (
            pc.active=true
            OR EXISTS (SELECT 1 FROM payments p WHERE p.tenant_id=pc.tenant_id AND p.payment_channel_id=pc.id AND p.business_date=:d AND p.status='RECORDED')
            OR EXISTS (SELECT 1 FROM refund_records rr WHERE rr.tenant_id=pc.tenant_id AND rr.payment_channel_id=pc.id AND rr.business_date=:d AND rr.status='RECORDED')
          )"""),{"t":str(tenant_id),"r":str(rid),"d":body.business_date})
        _emit(db,tenant_id,actor,"reconciliation.started","RECONCILIATION_STARTED","reconciliation",rid,{"business_date":str(body.business_date)},request_id)
        result=db.execute(text("SELECT id,business_date,status,notes,closed_at,created_at FROM daily_reconciliations WHERE tenant_id=:t AND id=:r"),{"t":str(tenant_id),"r":str(rid)}).mappings().one(); result=out(result)
        _finish(db,idem,201,result,"reconciliation",rid); db.commit(); return result
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409,"A reconciliation already exists for this business date") from exc


@router.post("/reconciliation-lines/{line_id}/actual")
def set_actual(line_id: UUID, body: ActualIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("reconciliation.manage"))):
    db,actor,tenant_id,_=ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    payload = body.model_dump(mode="json") | {"line_id": str(line_id)}
    idem,cached,_,cached_body = _idempotency(db,tenant_id,idempotency_key,"commerce.reconciliation.actual",payload)
    if cached: return cached_body
    try:
        db.execute(text("SELECT set_reconciliation_line_actual(:id,:a,:n,:u)"),{"id":str(line_id),"a":str(q(body.actual_amount)),"n":body.notes,"u":str(actor)})
        row=db.execute(text("SELECT id,reconciliation_id,payment_channel_id,expected_amount,actual_amount,variance,status,notes,reviewed_by,updated_at FROM daily_reconciliation_lines WHERE tenant_id=:t AND id=:id"),{"t":str(tenant_id),"id":str(line_id)}).mappings().first()
        if not row: raise HTTPException(404,"Reconciliation line not found")
        result = out(row)
        _emit(db,tenant_id,actor,"reconciliation.actual_entered","ACTUAL_SETTLEMENT_ENTERED","reconciliation_line",line_id,{"actual_amount":str(q(body.actual_amount))},request_id)
        _finish(db,idem,200,result,"reconciliation_line",line_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except Exception as exc: db.rollback(); raise HTTPException(400,"The actual amount could not be saved. Try again.") from exc


@router.post("/reconciliation-lines/{line_id}/resolve")
def resolve_line(line_id: UUID, body: ResolveIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("reconciliation.resolve"))):
    db,actor,tenant_id,_=ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    payload = body.model_dump(mode="json") | {"line_id": str(line_id)}
    idem,cached,_,cached_body = _idempotency(db,tenant_id,idempotency_key,"commerce.reconciliation.resolve",payload)
    if cached: return cached_body
    try:
        db.execute(text("SELECT resolve_reconciliation_line(:id,:s,:u,:n)"),{"id":str(line_id),"s":body.status,"u":str(actor),"n":body.notes})
        row=db.execute(text("SELECT id,reconciliation_id,payment_channel_id,expected_amount,actual_amount,variance,status,notes,reviewed_by,updated_at FROM daily_reconciliation_lines WHERE tenant_id=:t AND id=:id"),{"t":str(tenant_id),"id":str(line_id)}).mappings().first()
        if not row: raise HTTPException(404,"Reconciliation line not found")
        result = out(row)
        _emit(db,tenant_id,actor,"reconciliation.variance_resolved","VARIANCE_RESOLVED","reconciliation_line",line_id,{"status":body.status},request_id)
        _finish(db,idem,200,result,"reconciliation_line",line_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except Exception as exc: db.rollback(); raise HTTPException(400,"The difference could not be marked as reviewed.") from exc


@router.post("/reconciliations/{reconciliation_id}/close")
def close_reconciliation(reconciliation_id: UUID, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("reconciliation.close"))):
    db,actor,tenant_id,_=ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    payload = {"reconciliation_id": str(reconciliation_id)}
    idem,cached,_,cached_body = _idempotency(db,tenant_id,idempotency_key,"commerce.reconciliation.close",payload)
    if cached: return cached_body
    try:
        existing = db.execute(text("SELECT id,business_date,status,closed_at FROM daily_reconciliations WHERE tenant_id=:t AND id=:id FOR UPDATE"),{"t":str(tenant_id),"id":str(reconciliation_id)}).mappings().first()
        if not existing: raise HTTPException(404,"End-of-day check not found")
        if existing["status"] != "CLOSED":
            db.execute(text("SELECT close_daily_reconciliation(:id)"),{"id":str(reconciliation_id)})
            db.execute(text("UPDATE daily_reconciliations SET closed_by=:u,updated_at=now() WHERE tenant_id=:t AND id=:id"),{"u":str(actor),"t":str(tenant_id),"id":str(reconciliation_id)})
            _emit(db,tenant_id,actor,"reconciliation.closed","DAY_CLOSED","reconciliation",reconciliation_id,{"business_date":str(existing["business_date"])},request_id)
        row=db.execute(text("SELECT id,business_date,status,closed_at FROM daily_reconciliations WHERE tenant_id=:t AND id=:id"),{"t":str(tenant_id),"id":str(reconciliation_id)}).mappings().one()
        result = out(row)
        _finish(db,idem,200,result,"reconciliation",reconciliation_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except Exception as exc: db.rollback(); raise HTTPException(400,"This end-of-day check cannot be finished yet. Enter all actual amounts and review any differences.") from exc

class ReturnLineIn(Strict):
    sale_line_id: UUID
    quantity: Decimal = Field(gt=0)

class ReturnCreate(Strict):
    reason: str = Field(min_length=2, max_length=240)
    inventory_location_id: UUID | None = None
    business_date: date = Field(default_factory=date.today)
    settlement_type: str = Field(default="NONE", pattern=r"^(NONE|REFUND|CUSTOMER_CREDIT)$")
    refund_channel_id: UUID | None = None
    lines: list[ReturnLineIn] = Field(min_length=1)

    @field_validator("lines")
    @classmethod
    def each_sale_line_is_returned_once(cls, lines: list[ReturnLineIn]) -> list[ReturnLineIn]:
        ensure_unique_return_line_ids(line.sale_line_id for line in lines)
        return lines

@router.get("/returns")
def list_returns(ctx=Depends(require_permission("returns.manage"))):
    db,actor_id,tenant_id,_=ctx
    rows=db.execute(text("""
      SELECT sr.id,sr.sale_id,sr.status,sr.reason,sr.total,sr.completed_at,sr.created_at,
             COALESCE((SELECT SUM(rr.amount) FROM refund_records rr WHERE rr.return_id=sr.id AND rr.tenant_id=sr.tenant_id AND rr.status='RECORDED'),0) refunded,
             COALESCE((SELECT MAX(cc.balance) FROM customer_credits cc WHERE cc.source_return_id=sr.id AND cc.tenant_id=sr.tenant_id),0) credit_balance,
             (SELECT je.id FROM journal_entries je WHERE je.tenant_id=sr.tenant_id AND je.source_type='SALE_RETURN' AND je.source_id=sr.id AND je.entry_role='RETURN_SETTLEMENT' LIMIT 1) journal_entry_id,
             (SELECT fd.id FROM fiscal_documents fd WHERE fd.tenant_id=sr.tenant_id AND fd.source_type='SALE_RETURN' AND fd.source_id=sr.id AND fd.document_type='CREDIT_NOTE' ORDER BY fd.created_at DESC LIMIT 1) fiscal_document_id,
             (SELECT fd.status FROM fiscal_documents fd WHERE fd.tenant_id=sr.tenant_id AND fd.source_type='SALE_RETURN' AND fd.source_id=sr.id AND fd.document_type='CREDIT_NOTE' ORDER BY fd.created_at DESC LIMIT 1) fiscal_document_status
      FROM sale_returns sr
      JOIN sales s ON s.id=sr.sale_id AND s.tenant_id=sr.tenant_id
      WHERE sr.tenant_id=:t AND EXISTS (
        SELECT 1 FROM tenant_memberships tm
        JOIN membership_branch_assignments mba ON mba.membership_id=tm.id AND mba.tenant_id=tm.tenant_id
        JOIN branches b ON b.id=mba.branch_id AND b.tenant_id=mba.tenant_id
        WHERE tm.tenant_id=sr.tenant_id AND tm.user_id=:u
          AND tm.status='ACTIVE' AND mba.status='ACTIVE' AND b.status='ACTIVE'
          AND b.id=s.branch_id
      )
      ORDER BY sr.created_at DESC LIMIT 200
    """),{"t":str(tenant_id),"u":str(actor_id)}).mappings().all()
    return [out(x) for x in rows]

@router.post("/sales/{sale_id}/returns", status_code=201)
def create_return(sale_id: UUID, body: ReturnCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("sales.return"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.sale.return",body.model_dump(mode="json") | {"sale_id":str(sale_id)})
    if cached: return cached_body
    try:
        sale=db.execute(text("SELECT * FROM sales WHERE tenant_id=:t AND id=:s FOR UPDATE"),{"t":str(tenant_id),"s":str(sale_id)}).mappings().first()
        if not sale: raise HTTPException(404,"Sale not found")
        ensure_branch_access(db, tenant_id=tenant_id, user_id=actor, branch_id=sale["branch_id"])
        if sale["status"]!='COMPLETED': raise HTTPException(409,"Only completed sales can be returned")
        if body.settlement_type=='REFUND':
            if body.refund_channel_id is None: raise HTTPException(400,"A refund channel is required for refunds")
            if Decimal(str(sale["amount_paid"]))<=0: raise HTTPException(409,"An unpaid credit sale cannot be refunded; use customer credit")
        if body.settlement_type=='CUSTOMER_CREDIT' and not sale["customer_party_id"]: raise HTTPException(400,"A customer is required for customer credit")
        return_location=body.inventory_location_id or sale["location_id"]
        if return_location is None: raise HTTPException(400,"An inventory location is required for an inventory return")
        tenant_location(db,tenant_id,return_location)
        return_branch_id = ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=return_location)
        if return_branch_id != sale["branch_id"]:
            ensure_branch_access(db, tenant_id=tenant_id, user_id=actor, branch_id=return_branch_id)
        validated=[]; total=Decimal("0")
        inventory_cost_by_variant: dict[UUID, tuple[bool, Decimal]] = {}
        for req_line in body.lines:
            line=db.execute(text("SELECT * FROM transaction_lines WHERE tenant_id=:t AND id=:id AND transaction_id=:tx"),{"t":str(tenant_id),"id":str(req_line.sale_line_id),"tx":str(sale["transaction_id"])}).mappings().first()
            if not line or not line["product_variant_id"]: raise HTTPException(400,"Return line must reference a product sale line")
            returned=db.execute(text("""SELECT COALESCE(SUM(srl.quantity),0) qty FROM sale_return_lines srl JOIN sale_returns sr ON sr.id=srl.return_id AND sr.tenant_id=srl.tenant_id WHERE srl.tenant_id=:t AND srl.sale_line_id=:sl AND sr.status='COMPLETED'"""),{"t":str(tenant_id),"sl":str(req_line.sale_line_id)}).scalar_one()
            available=Decimal(str(line["quantity"]))-Decimal(str(returned))
            if req_line.quantity>available: raise HTTPException(409,"Return quantity exceeds the remaining sale quantity")
            variant_id = UUID(str(line["product_variant_id"]))
            if variant_id not in inventory_cost_by_variant:
                variant = tenant_variant(db, tenant_id, variant_id)
                original_inventory = db.execute(text("""
                  SELECT COALESCE(SUM(ABS(quantity_delta)),0) AS sold_quantity,
                         COALESCE(SUM(total_cost),0) AS sold_total_cost
                  FROM inventory_transactions
                  WHERE tenant_id=:t AND reference_type='sale' AND reference_id=:s
                    AND variant_id=:v AND transaction_type='SALE' AND quantity_delta<0
                """), {"t":str(tenant_id), "s":str(sale_id), "v":str(variant_id)}).mappings().one()
                sold_quantity = Decimal(str(original_inventory["sold_quantity"]))
                if sold_quantity > 0:
                    try:
                        original_unit_cost = original_sale_inventory_unit_cost(
                            original_inventory["sold_total_cost"], sold_quantity
                        )
                    except ValueError as exc:
                        raise HTTPException(409, "Original sale inventory cost is invalid; reconcile the stock ledger before returning this item") from exc
                    inventory_cost_by_variant[variant_id] = (True, original_unit_cost)
                elif variant.track_inventory:
                    # A tracked sale without its matching immutable movement is not
                    # safe to restore at today's average cost: that would misstate COGS.
                    raise HTTPException(409, "Original sale stock movement is missing; reconcile inventory before returning this item")
                else:
                    # Services and non-stock products have no inventory/COGS entry.
                    inventory_cost_by_variant[variant_id] = (False, Decimal("0"))
            tracks_inventory, original_unit_cost = inventory_cost_by_variant[variant_id]
            line_total, line_discount, line_tax = prorate_return_line_amounts(
                req_line.quantity, line["quantity"], line["discount_amount"],
                line["tax_amount"], line["line_total"]
            )
            # A sale line stores the total tax and discount for its full quantity;
            # proportion partial returns instead of copying all original adjustments.
            total += line_total
            validated.append((req_line, line, line_total, line_discount, line_tax, tracks_inventory, original_unit_cost))
        total=q(total)
        remaining_sales_value=q(Decimal(str(sale["total"]))-Decimal(str(sale["return_adjustment_amount"])))
        if total<=0 or total>remaining_sales_value: raise HTTPException(422,"Return total is outside the remaining sale value")
        if body.settlement_type == 'NONE':
            # A no-cash/no-credit return may only offset an existing receivable.
            # Reject before any ledger writes when the customer has already paid
            # or the return exceeds the open receivable; otherwise accounting would
            # credit AR beyond the amount the customer still owes.
            open_receivable = db.execute(text("""
              SELECT COALESCE(SUM(GREATEST(balance,0)),0)
              FROM receivables
              WHERE tenant_id=:t AND sale_id=:s
                AND status IN ('OPEN','PARTIALLY_PAID')
            """), {"t":str(tenant_id), "s":str(sale_id)}).scalar_one()
            if total > Decimal(str(open_receivable)):
                raise HTTPException(
                    422,
                    "A no-refund return cannot exceed the open receivable; choose REFUND or CUSTOMER_CREDIT settlement",
                )
        if body.settlement_type=='REFUND':
            # Refundability must be based on the original recorded collection ledger,
            # not sales.amount_paid: after refund settlement that field is net of prior
            # refunds on migration 033 deployments. Using net amount_paid here would
            # subtract prior refunds twice and understate the remaining refundable cap.
            gross_collected=db.execute(text("""
              SELECT COALESCE(SUM(pa.amount),0)
              FROM payment_allocations pa
              JOIN payments p ON p.id=pa.payment_id AND p.tenant_id=pa.tenant_id
              LEFT JOIN receivables r ON r.id=pa.receivable_id AND r.tenant_id=pa.tenant_id
              WHERE pa.tenant_id=:t AND pa.status='RECORDED' AND p.status='RECORDED'
                AND (pa.sale_id=:s OR r.sale_id=:s)
            """),{"t":str(tenant_id),"s":str(sale_id)}).scalar_one()
            prior_refunds=db.execute(text("""
              SELECT COALESCE(SUM(rr.amount),0)
              FROM refund_records rr
              JOIN sale_returns prior_return ON prior_return.id=rr.return_id AND prior_return.tenant_id=rr.tenant_id
              WHERE rr.tenant_id=:t AND prior_return.sale_id=:s AND rr.status='RECORDED'
            """),{"t":str(tenant_id),"s":str(sale_id)}).scalar_one()
            refundable_balance=remaining_refund_balance(gross_collected,prior_refunds)
            if total>refundable_balance:
                raise HTTPException(422,"Refund exceeds the remaining collected amount after previous refunds")
        tx_ref=f"RET-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
        tx=BusinessTransaction(tenant_id=tenant_id,transaction_type="SALE_RETURN",reference=tx_ref,status="DRAFT",party_id=sale["customer_party_id"],branch_id=sale["branch_id"],total_amount=total,currency_code=sale["currency_code"],occurred_at=datetime.now(timezone.utc),metadata_json={"source":"commerce","sale_id":str(sale_id)})
        db.add(tx); db.flush()
        db.execute(text("""INSERT INTO sale_returns(tenant_id,sale_id,transaction_id,inventory_location_id,business_date,status,reason,total,created_by) VALUES(:t,:s,:tx,:l,:business_date,'DRAFT',:r,:total,:u) RETURNING id"""),{"t":str(tenant_id),"s":str(sale_id),"tx":str(tx.id),"l":str(return_location),"business_date":body.business_date,"r":body.reason.strip(),"total":str(total),"u":str(actor)})
        return_id=db.execute(text("SELECT id FROM sale_returns WHERE tenant_id=:t AND transaction_id=:tx"),{"t":str(tenant_id),"tx":str(tx.id)}).scalar_one()
        for req_line, line, line_total, line_discount, line_tax, tracks_inventory, original_unit_cost in validated:
            db.execute(text("""INSERT INTO sale_return_lines(tenant_id,return_id,sale_line_id,variant_id,quantity,unit_price,discount_amount,tax_amount,line_total) VALUES(:t,:r,:sl,:v,:q,:u,:d,:tax,:total)"""),{"t":str(tenant_id),"r":str(return_id),"sl":str(req_line.sale_line_id),"v":str(line["product_variant_id"]),"q":str(req_line.quantity),"u":str(line["unit_price"]),"d":str(line_discount),"tax":str(line_tax),"total":str(line_total)})
            if tracks_inventory:
                # Value returned stock at its originating sale cost. Current average
                # cost may have changed since checkout and must not rewrite COGS.
                post_ledger(db,tenant_id=tenant_id,actor_user_id=actor,location_id=return_location,variant_id=line["product_variant_id"],quantity_delta=q(req_line.quantity),unit_cost=original_unit_cost,transaction_type="RETURN",reference_type="sale_return",reference_id=return_id,idempotency_key=f"{idempotency_key or return_id}:inventory:{req_line.sale_line_id}",metadata={"sale_id":str(sale_id),"return_id":str(return_id),"cost_basis":"original_sale_inventory_ledger"},allow_zero_cost_receipt=True)
        db.execute(text("UPDATE sales SET return_adjustment_amount=return_adjustment_amount+:a,updated_at=now() WHERE tenant_id=:t AND id=:s"),{"t":str(tenant_id),"s":str(sale_id),"a":str(total)})
        # NONE reduces the sale value without issuing cash or store credit, so it
        # may offset the open receivable. A cash refund reduces both net collections
        # and sale value; a customer-credit return creates a separate liability.
        # Neither settlement should silently write off the sale receivable. Customer
        # credit reduces that receivable only if a later credit-allocation row does so.
        if body.settlement_type == 'NONE':
            db.execute(text("""
              UPDATE receivables
              SET adjustment_amount=LEAST(
                    GREATEST(original_amount-paid_amount,0),
                    adjustment_amount+:a
                  ),
                  balance=GREATEST(
                    original_amount-paid_amount-LEAST(
                      GREATEST(original_amount-paid_amount,0),
                      adjustment_amount+:a
                    ),0
                  ),
                  status=CASE
                    WHEN GREATEST(
                      original_amount-paid_amount-LEAST(
                        GREATEST(original_amount-paid_amount,0),
                        adjustment_amount+:a
                      ),0
                    )=0 THEN 'PAID'
                    WHEN paid_amount>0 THEN 'PARTIALLY_PAID'
                    ELSE 'OPEN'
                  END,
                  updated_at=now()
              WHERE tenant_id=:t AND sale_id=:s AND status IN ('OPEN','PARTIALLY_PAID')
            """),{"t":str(tenant_id),"s":str(sale_id),"a":str(total)})
        db.execute(text("UPDATE sale_returns SET status='COMPLETED',completed_by=:u,completed_at=now(),updated_at=now() WHERE tenant_id=:t AND id=:r"),{"t":str(tenant_id),"r":str(return_id),"u":str(actor)})
        db.execute(text("UPDATE business_transactions SET status='COMPLETED',closed_at=now(),updated_at=now() WHERE tenant_id=:t AND id=:tx"),{"t":str(tenant_id),"tx":str(tx.id)})
        db.execute(text("INSERT INTO transaction_status_history(tenant_id,transaction_id,from_status,to_status,reason,changed_by) VALUES(:t,:tx,'DRAFT','COMPLETED','Sale return completed',:u)"),{"t":str(tenant_id),"tx":str(tx.id),"u":str(actor)})
        if body.settlement_type=='REFUND':
            ch=_channel(db,tenant_id,body.refund_channel_id,sale["currency_code"])
            refund_id=db.execute(text("""INSERT INTO refund_records(tenant_id,return_id,payment_channel_id,amount,currency_code,reference,status,business_date,created_by) VALUES(:t,:r,:c,:a,:cur,:ref,'RECORDED',:d,:u) RETURNING id"""),{"t":str(tenant_id),"r":str(return_id),"c":str(ch["id"]),"a":str(total),"cur":sale["currency_code"],"ref":f"REF-{tx_ref}","d":body.business_date,"u":str(actor)}).scalar_one()
            _emit(db,tenant_id,actor,"refund.recorded","REFUND_RECORDED","refund",refund_id,{"return_id":str(return_id),"amount":str(total),"channel_id":str(ch["id"])},request_id)
        elif body.settlement_type=='CUSTOMER_CREDIT':
            credit_id=db.execute(text("""INSERT INTO customer_credits(tenant_id,customer_party_id,source_return_id,original_amount,allocated_amount,balance,status) VALUES(:t,:p,:r,:a,0,:a,'OPEN') RETURNING id"""),{"t":str(tenant_id),"p":str(sale["customer_party_id"]),"r":str(return_id),"a":str(total)}).scalar_one()
            _emit(db,tenant_id,actor,"customer_credit.created","CUSTOMER_CREDIT_CREATED","customer_credit",credit_id,{"return_id":str(return_id),"amount":str(total)},request_id)
        # Recalculate only after any cash refund row has been recorded. Migration
        # 033 also does this from an AFTER trigger so non-API refund changes reconcile.
        db.execute(text("SELECT refresh_sale_payment_totals(:t,:s)"),{"t":str(tenant_id),"s":str(sale_id)})
        return_journal = db.execute(text("SELECT post_sale_return_journal(:id,:u)"), {"id":str(return_id),"u":str(actor)}).scalar_one()
        return_cogs_journal = db.execute(text("SELECT post_sale_return_cogs_journal(:id,:u)"), {"id":str(return_id),"u":str(actor)}).scalar()
        _emit(db,tenant_id,actor,"accounting.entry.posted","ACCOUNTING_ENTRY_POSTED","journal_entry",return_journal,{"return_id":str(return_id),"entry_role":"RETURN_SETTLEMENT"},request_id)
        if return_cogs_journal:
            _emit(db,tenant_id,actor,"accounting.entry.posted","ACCOUNTING_ENTRY_POSTED","journal_entry",return_cogs_journal,{"return_id":str(return_id),"entry_role":"RETURN_COGS"},request_id)
        fiscal_document = db.execute(text("SELECT create_fiscal_document_for_return(:id)"), {"id":str(return_id)}).scalar()
        if fiscal_document:
            _emit(db,tenant_id,actor,"fiscal.credit_note.created","FISCAL_CREDIT_NOTE_CREATED","fiscal_document",fiscal_document,{"return_id":str(return_id),"status":"PENDING"},request_id)
        _emit(db,tenant_id,actor,"sale.return.created","RETURN_CREATED","sale_return",return_id,{"sale_id":str(sale_id),"total":str(total),"journal_entry_id":str(return_journal)},request_id)
        result=db.execute(text("SELECT id,sale_id,status,reason,total,completed_at,created_at FROM sale_returns WHERE tenant_id=:t AND id=:r"),{"t":str(tenant_id),"r":str(return_id)}).mappings().one(); result=out(result)
        result["journal_entry_id"] = str(return_journal)
        result["cogs_journal_entry_id"] = str(return_cogs_journal) if return_cogs_journal else None
        result["fiscal_document_id"] = str(fiscal_document) if fiscal_document else None
        _finish(db,idem,201,result,"sale_return",return_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except IntegrityError as exc: db.rollback(); raise HTTPException(409,"Return could not be committed because a business invariant was violated") from exc
    except Exception as exc: db.rollback(); raise HTTPException(500,"Return creation failed") from exc
