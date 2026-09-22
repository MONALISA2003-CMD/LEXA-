from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalog import begin_idempotency, emit_event, finish_idempotency, write_audit
from ..dependencies import require_permission
from ..inventory import post_ledger, tenant_location, tenant_variant
from ..models import Branch, BusinessProfile, BusinessTransaction, Party, PartyRole, TransactionLine

router = APIRouter(prefix="/commerce", tags=["commerce"])

MONEY = Decimal("0.0001")
CHANNEL_TYPES = {"CASH", "MOBILE_MONEY", "BANK", "CARD", "CHEQUE", "OTHER"}


def q(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def out(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in row._mapping.items()}


def default_currency(db: Session, tenant_id: UUID) -> str:
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id))
    return (profile.currency_code if profile else "UGX").upper()


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
    name: str = Field(min_length=1, max_length=160)
    channel_type: str = Field(min_length=2, max_length=30)
    provider: str | None = Field(default=None, max_length=100)
    currency_code: str = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_type(self):
        self.channel_type = self.channel_type.upper().strip()
        self.currency_code = self.currency_code.upper().strip()
        if self.channel_type not in CHANNEL_TYPES:
            raise ValueError("Credit is a receivable, not a payment channel")
        return self


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


class SaleCreate(Strict):
    customer_party_id: UUID | None = None
    branch_id: UUID | None = None
    location_id: UUID | None = None
    currency_code: str = Field(min_length=3, max_length=3)
    business_date: date = Field(default_factory=date.today)
    lines: list[SaleLineIn] = Field(min_length=1)
    payments: list[PaymentAllocationIn] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def normalize(self):
        self.currency_code = self.currency_code.upper().strip()
        return self


class PaymentCreate(Strict):
    payment_channel_id: UUID
    amount: Decimal = Field(gt=0)
    business_date: date = Field(default_factory=date.today)
    reference: str | None = Field(default=None, max_length=120)


class CustomerCreditAllocateIn(Strict):
    receivable_id: UUID
    amount: Decimal = Field(gt=0)


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
    db, _, tenant_id, _ = ctx
    today = business_date or date.today()
    sales = db.execute(text("""
      SELECT COALESCE(SUM(total),0) sales, COALESCE(SUM(amount_paid),0) collected,
             COALESCE(SUM(amount_due),0) credit
      FROM sales WHERE tenant_id=:tenant_id AND created_at::date=:business_date AND status='COMPLETED'
    """), {"tenant_id": str(tenant_id), "business_date": today}).mappings().one()
    channels = db.execute(text("""
      SELECT pc.id,pc.name,pc.channel_type,pc.currency_code,pc.active,
             COALESCE(SUM(p.amount) FILTER (WHERE p.status='RECORDED' AND p.business_date=:business_date),0)
             - COALESCE((SELECT SUM(r.amount) FROM refund_records r WHERE r.tenant_id=pc.tenant_id AND r.payment_channel_id=pc.id AND r.business_date=:business_date AND r.status='RECORDED'),0) expected
      FROM payment_channels pc LEFT JOIN payments p ON p.payment_channel_id=pc.id AND p.tenant_id=pc.tenant_id
      WHERE pc.tenant_id=:tenant_id GROUP BY pc.id ORDER BY pc.name
    """), {"tenant_id": str(tenant_id), "business_date": today}).mappings().all()
    recv = db.execute(text("SELECT COALESCE(SUM(balance),0) outstanding FROM receivables WHERE tenant_id=:tenant_id AND status IN ('OPEN','PARTIALLY_PAID')"), {"tenant_id":str(tenant_id)}).mappings().one()
    return {"business_date": today, "sales": out(sales), "payment_channels":[out(x) for x in channels], "outstanding_receivables":str(recv["outstanding"])}


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


@router.get("/products")
def commerce_products(ctx=Depends(require_permission("sales.read"))):
    db,_,tenant_id,_=ctx
    rows=db.execute(text("""
      SELECT pv.id variant_id,pv.sku,pv.name variant_name,p.name product_name,pv.track_inventory,
             COALESCE(pp.unit_price,0) selling_price
      FROM product_variants pv JOIN products p ON p.id=pv.product_id AND p.tenant_id=pv.tenant_id
      LEFT JOIN LATERAL (SELECT unit_price FROM product_prices x WHERE x.tenant_id=pv.tenant_id AND x.variant_id=pv.id ORDER BY effective_from DESC LIMIT 1) pp ON true
      WHERE pv.tenant_id=:t AND pv.deleted_at IS NULL AND pv.status='ACTIVE' AND p.deleted_at IS NULL AND p.status='ACTIVE'
      ORDER BY p.name,pv.name LIMIT 500
    """),{"t":str(tenant_id)}).mappings().all()
    return [out(x) for x in rows]


@router.get("/sales")
def list_sales(limit: int = Query(default=100, ge=1, le=500), ctx=Depends(require_permission("sales.read"))):
    db,_,tenant_id,_=ctx
    rows=db.execute(text("""
      SELECT s.id,s.transaction_id,s.customer_party_id,p.display_name customer_name,s.currency_code,s.status,
             s.subtotal,s.discount_total,s.tax_total,s.total,s.amount_paid,s.amount_due,s.return_adjustment_amount,s.created_at,s.completed_at
      FROM sales s LEFT JOIN parties p ON p.id=s.customer_party_id AND p.tenant_id=s.tenant_id
      WHERE s.tenant_id=:t ORDER BY s.created_at DESC LIMIT :lim
    """),{"t":str(tenant_id),"lim":limit}).mappings().all()
    return [out(x) for x in rows]


@router.get("/sales/{sale_id}")
def get_sale(sale_id: UUID, ctx=Depends(require_permission("sales.read"))):
    db,_,tenant_id,_=ctx
    sale=db.execute(text("""
      SELECT s.id,s.transaction_id,s.customer_party_id,p.display_name customer_name,s.branch_id,s.location_id,s.currency_code,s.status,
             s.subtotal,s.discount_total,s.tax_total,s.total,s.amount_paid,s.amount_due,s.return_adjustment_amount,s.notes,s.created_at,s.completed_at
      FROM sales s LEFT JOIN parties p ON p.id=s.customer_party_id AND p.tenant_id=s.tenant_id
      WHERE s.tenant_id=:t AND s.id=:s
    """),{"t":str(tenant_id),"s":str(sale_id)}).mappings().first()
    if not sale:
        raise HTTPException(404,"Sale not found")
    lines=db.execute(text("""
      SELECT tl.id sale_line_id,tl.product_variant_id,pv.sku,pv.name variant_name,tl.quantity,tl.unit_price,tl.discount_amount,tl.tax_amount,tl.line_total
      FROM transaction_lines tl LEFT JOIN product_variants pv ON pv.id=tl.product_variant_id AND pv.tenant_id=tl.tenant_id
      WHERE tl.tenant_id=:t AND tl.transaction_id=:tx ORDER BY tl.line_no
    """),{"t":str(tenant_id),"tx":str(sale["transaction_id"])}).mappings().all()
    result=out(sale); result["lines"]=[out(x) for x in lines]; return result


@router.post("/sales", status_code=201)
def create_sale(body: SaleCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("sales.complete"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.sale.create",body.model_dump(mode="json"))
    if cached: return cached_body
    try:
        currency=body.currency_code
        _tenant_party(db,tenant_id,body.customer_party_id); _tenant_branch(db,tenant_id,body.branch_id)
        if body.location_id is None: raise HTTPException(400,"A sale location is required for inventory-safe checkout")
        tenant_location(db,tenant_id,body.location_id)
        subtotal=Decimal("0"); discount=Decimal("0"); tax=Decimal("0")
        validated=[]
        for line in body.lines:
            variant=tenant_variant(db,tenant_id,line.variant_id)
            gross=q(line.quantity*line.unit_price)
            if line.discount_amount>gross: raise HTTPException(422,"Line discount cannot exceed line value")
            taxable=q(gross-line.discount_amount)
            line_tax=q(taxable*line.tax_rate/Decimal("100"))
            line_total=q(taxable+line_tax)
            subtotal+=gross; discount+=q(line.discount_amount); tax+=line_tax
            validated.append((line,variant,line_total,line_tax))
        subtotal=q(subtotal); discount=q(discount); tax=q(tax); total=q(subtotal-discount+tax)
        if total<=0: raise HTTPException(422,"Sale total must be greater than zero")
        paid=q(sum((x.amount for x in body.payments),Decimal("0")))
        if paid>total: raise HTTPException(422,"Payment allocations cannot exceed sale total")
        due=q(total-paid)
        if due>0:
            if body.customer_party_id is None: raise HTTPException(400,"A customer is required for credit/outstanding sales")
            customer_profile=db.execute(text("""
              SELECT cp.credit_limit,cp.status,
                     COALESCE((SELECT SUM(r.balance) FROM receivables r WHERE r.tenant_id=cp.tenant_id AND r.customer_party_id=cp.party_id AND r.status IN ('OPEN','PARTIALLY_PAID')),0) outstanding
              FROM customer_profiles cp
              WHERE cp.tenant_id=:t AND cp.party_id=:p
              FOR UPDATE
            """),{"t":str(tenant_id),"p":str(body.customer_party_id)}).mappings().first()
            if not customer_profile or customer_profile["status"] != "ACTIVE":
                raise HTTPException(409,"Customer credit is not enabled for this customer")
            available_credit=q(Decimal(str(customer_profile["credit_limit"]))-Decimal(str(customer_profile["outstanding"])))
            if due>available_credit:
                raise HTTPException(409,f"Sale would exceed the customer's available credit of {available_credit}")
        ref=f"SAL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
        tx=BusinessTransaction(tenant_id=tenant_id,transaction_type="SALE",reference=ref,status="DRAFT",party_id=body.customer_party_id,branch_id=body.branch_id,total_amount=total,currency_code=currency,occurred_at=datetime.now(timezone.utc),metadata_json={"source":"commerce"})
        db.add(tx); db.flush()
        db.add(TransactionLine(tenant_id=tenant_id,transaction_id=tx.id,line_no=1,line_type="PRODUCT",product_variant_id=validated[0][1].id,description=validated[0][1].name,quantity=validated[0][0].quantity,unit_price=validated[0][0].unit_price,line_total=validated[0][2],currency_code=currency,discount_amount=validated[0][0].discount_amount,tax_rate=validated[0][0].tax_rate,tax_amount=validated[0][3],metadata_json={}) )
        for idx,(line,variant,line_total,line_tax) in enumerate(validated[1:],start=2):
            db.add(TransactionLine(tenant_id=tenant_id,transaction_id=tx.id,line_no=idx,line_type="PRODUCT",product_variant_id=variant.id,description=variant.name,quantity=line.quantity,unit_price=line.unit_price,line_total=line_total,currency_code=currency,discount_amount=line.discount_amount,tax_rate=line.tax_rate,tax_amount=line_tax,metadata_json={}))
        db.execute(text("""INSERT INTO sales(tenant_id,transaction_id,customer_party_id,branch_id,location_id,currency_code,status,subtotal,discount_total,tax_total,total,amount_paid,amount_due,notes,created_by)
          VALUES(:t,:tx,:cp,:b,:l,:c,'DRAFT',:s,:d,:tax,:total,0,:due,:notes,:actor)"""),{"t":str(tenant_id),"tx":str(tx.id),"cp":str(body.customer_party_id) if body.customer_party_id else None,"b":str(body.branch_id) if body.branch_id else None,"l":str(body.location_id),"c":currency,"s":str(subtotal),"d":str(discount),"tax":str(tax),"total":str(total),"due":str(total),"notes":body.notes,"actor":str(actor)})
        sale_id=db.execute(text("SELECT id FROM sales WHERE tenant_id=:t AND transaction_id=:tx"),{"t":str(tenant_id),"tx":str(tx.id)}).scalar_one()
        for idx,(line,variant,_,_) in enumerate(validated, start=1):
            invtx=post_ledger(db,tenant_id=tenant_id,actor_user_id=actor,location_id=body.location_id,variant_id=variant.id,quantity_delta=-q(line.quantity),unit_cost=Decimal("0"),transaction_type="SALE",reference_type="sale",reference_id=sale_id,idempotency_key=f"{idempotency_key or tx.id}:inventory:{idx}",metadata={"sale_id":str(sale_id)}) if variant.track_inventory else None
            if invtx:
                _emit(db,tenant_id,actor,"stock.decreased","STOCK_DECREASED","inventory_transaction",invtx.id,{"sale_id":str(sale_id),"variant_id":str(variant.id),"quantity":str(q(line.quantity))},request_id)
        for payment in body.payments:
            ch=_channel(db,tenant_id,payment.payment_channel_id,currency)
            pid=db.execute(text("""INSERT INTO payments(tenant_id,transaction_id,party_id,amount,currency_code,method,status,reference,paid_at,metadata,payment_channel_id,business_date)
              VALUES(:t,:tx,:p,:a,:c,:m,'RECORDED',:ref,now(),:meta,:ch,:d) RETURNING id"""),{"t":str(tenant_id),"tx":str(tx.id),"p":str(body.customer_party_id) if body.customer_party_id else None,"a":str(q(payment.amount)),"c":currency,"m":ch["channel_type"],"ref":payment.reference,"meta":{},"ch":str(ch["id"]),"d":payment.business_date}).scalar_one()
            db.execute(text("INSERT INTO payment_allocations(tenant_id,payment_id,sale_id,amount,status,created_by) VALUES(:t,:p,:s,:a,'RECORDED',:u)"),{"t":str(tenant_id),"p":str(pid),"s":str(sale_id),"a":str(q(payment.amount)),"u":str(actor)})
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
        _emit(db,tenant_id,actor,"sale.completed","SALE_COMPLETED","sale",sale_id,{"reference":ref,"total":str(total),"paid":str(paid_now["amount_paid"]),"due":str(paid_now["amount_due"])},request_id)
        result=db.execute(text("SELECT s.id,s.transaction_id,s.currency_code,s.status,s.subtotal,s.discount_total,s.tax_total,s.total,s.amount_paid,s.amount_due,s.created_at,s.completed_at FROM sales s WHERE s.tenant_id=:t AND s.id=:s"),{"t":str(tenant_id),"s":str(sale_id)}).mappings().one()
        result=out(result); _finish(db,idem,201,result,"sale",sale_id); db.commit(); return result
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
      WHERE r.tenant_id=:t AND r.status IN ('OPEN','PARTIALLY_PAID') ORDER BY r.created_at DESC LIMIT 500
    """),{"t":str(tenant_id)}).mappings().all()
    return [out(x) for x in rows]


@router.post("/receivables/{receivable_id}/payments", status_code=201)
def pay_receivable(receivable_id: UUID, body: PaymentCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("payments.allocate"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.receivable.payment",body.model_dump(mode="json") | {"receivable_id":str(receivable_id)})
    if cached: return cached_body
    receivable=db.execute(text("SELECT r.*,s.currency_code,s.transaction_id,s.customer_party_id FROM receivables r JOIN sales s ON s.id=r.sale_id AND s.tenant_id=r.tenant_id WHERE r.tenant_id=:t AND r.id=:r FOR UPDATE"),{"t":str(tenant_id),"r":str(receivable_id)}).mappings().first()
    if not receivable: raise HTTPException(404,"Receivable not found")
    if Decimal(str(receivable["balance"])) <= 0: raise HTTPException(409,"Receivable is already paid")
    if q(body.amount)>q(Decimal(str(receivable["balance"]))): raise HTTPException(422,"Payment exceeds receivable balance")
    ch=_channel(db,tenant_id,body.payment_channel_id,receivable["currency_code"])
    pid=db.execute(text("""INSERT INTO payments(tenant_id,transaction_id,party_id,amount,currency_code,method,status,reference,paid_at,metadata,payment_channel_id,business_date)
      VALUES(:t,:tx,:p,:a,:c,:m,'RECORDED',:ref,now(),'{}'::jsonb,:ch,:d) RETURNING id"""),{"t":str(tenant_id),"tx":str(receivable["transaction_id"]),"p":str(receivable["customer_party_id"]),"a":str(q(body.amount)),"c":receivable["currency_code"],"m":ch["channel_type"],"ref":body.reference,"ch":str(ch["id"]),"d":body.business_date}).scalar_one()
    db.execute(text("INSERT INTO payment_allocations(tenant_id,payment_id,receivable_id,amount,status,created_by) VALUES(:t,:p,:r,:a,'RECORDED',:u)"),{"t":str(tenant_id),"p":str(pid),"r":str(receivable_id),"a":str(q(body.amount)),"u":str(actor)})
    _emit(db,tenant_id,actor,"payment.recorded","PAYMENT_RECORDED","payment",pid,{"receivable_id":str(receivable_id),"amount":str(q(body.amount))},request_id)
    _emit(db,tenant_id,actor,"payment.allocated","PAYMENT_ALLOCATED","receivable",receivable_id,{"payment_id":str(pid),"amount":str(q(body.amount))},request_id)
    refreshed=db.execute(text("SELECT id,paid_amount,balance,status FROM receivables WHERE tenant_id=:t AND id=:r"),{"t":str(tenant_id),"r":str(receivable_id)}).mappings().one()
    result=out(refreshed); _finish(db,idem,201,result,"receivable",receivable_id); db.commit(); return result


@router.get("/reconciliations")
def list_reconciliations(business_date: date | None = None, ctx=Depends(require_permission("reconciliation.read"))):
    db,_,tenant_id,_=ctx
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
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.reconciliation.create",body.model_dump(mode="json"))
    if cached: return cached_body
    try:
        existing=db.execute(text("SELECT id,business_date,status,notes,closed_at,created_at FROM daily_reconciliations WHERE tenant_id=:t AND business_date=:d"),{"t":str(tenant_id),"d":body.business_date}).mappings().first()
        if existing:
            result=out(existing)
            _finish(db,idem,200,result,"reconciliation",existing["id"]); db.commit(); return result
        rid=db.execute(text("INSERT INTO daily_reconciliations(tenant_id,business_date,status,notes,created_by) VALUES(:t,:d,'OPEN',:n,:u) RETURNING id"),{"t":str(tenant_id),"d":body.business_date,"n":body.notes,"u":str(actor)}).scalar_one()
        db.execute(text("""INSERT INTO daily_reconciliation_lines(tenant_id,reconciliation_id,payment_channel_id) SELECT :t,:r,id FROM payment_channels WHERE tenant_id=:t AND active=true"""),{"t":str(tenant_id),"r":str(rid)})
        _emit(db,tenant_id,actor,"reconciliation.started","RECONCILIATION_STARTED","reconciliation",rid,{"business_date":str(body.business_date)},request_id)
        result=db.execute(text("SELECT id,business_date,status,notes,closed_at,created_at FROM daily_reconciliations WHERE tenant_id=:t AND id=:r"),{"t":str(tenant_id),"r":str(rid)}).mappings().one(); result=out(result)
        _finish(db,idem,201,result,"reconciliation",rid); db.commit(); return result
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409,"A reconciliation already exists for this business date") from exc


@router.post("/reconciliation-lines/{line_id}/actual")
def set_actual(line_id: UUID, body: ActualIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("reconciliation.manage"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.reconciliation.actual",body.model_dump(mode="json") | {"line_id":str(line_id)})
    if cached: return cached_body
    try:
        db.execute(text("SELECT set_reconciliation_line_actual(:id,:a,:n,:u)"),{"id":str(line_id),"a":str(q(body.actual_amount)),"n":body.notes,"u":str(actor)})
        row=db.execute(text("SELECT id,reconciliation_id,payment_channel_id,expected_amount,actual_amount,variance,status,notes,reviewed_by,updated_at FROM daily_reconciliation_lines WHERE tenant_id=:t AND id=:id"),{"t":str(tenant_id),"id":str(line_id)}).mappings().first()
        if not row: raise HTTPException(404,"Reconciliation line not found")
        _emit(db,tenant_id,actor,"reconciliation.actual_entered","ACTUAL_SETTLEMENT_ENTERED","reconciliation_line",line_id,{"actual_amount":str(q(body.actual_amount))},request_id)
        result=out(row); _finish(db,idem,200,result,"reconciliation_line",line_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except Exception as exc: db.rollback(); raise HTTPException(400,str(exc)) from exc


@router.post("/reconciliation-lines/{line_id}/resolve")
def resolve_line(line_id: UUID, body: ResolveIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("reconciliation.resolve"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.reconciliation.resolve",body.model_dump(mode="json") | {"line_id":str(line_id)})
    if cached: return cached_body
    try:
        db.execute(text("SELECT resolve_reconciliation_line(:id,:s,:u,:n)"),{"id":str(line_id),"s":body.status,"u":str(actor),"n":body.notes})
        row=db.execute(text("SELECT id,reconciliation_id,payment_channel_id,expected_amount,actual_amount,variance,status,notes,reviewed_by,updated_at FROM daily_reconciliation_lines WHERE tenant_id=:t AND id=:id"),{"t":str(tenant_id),"id":str(line_id)}).mappings().first()
        if not row: raise HTTPException(404,"Reconciliation line not found")
        _emit(db,tenant_id,actor,"reconciliation.variance_resolved","VARIANCE_RESOLVED","reconciliation_line",line_id,{"status":body.status},request_id)
        result=out(row); _finish(db,idem,200,result,"reconciliation_line",line_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except Exception as exc: db.rollback(); raise HTTPException(400,str(exc)) from exc


@router.post("/reconciliations/{reconciliation_id}/close")
def close_reconciliation(reconciliation_id: UUID, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("reconciliation.close"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.reconciliation.close",{"reconciliation_id":str(reconciliation_id)})
    if cached: return cached_body
    try:
        db.execute(text("SELECT close_daily_reconciliation(:id)"),{"id":str(reconciliation_id)})
        db.execute(text("UPDATE daily_reconciliations SET closed_by=:u,updated_at=now() WHERE tenant_id=:t AND id=:id"),{"u":str(actor),"t":str(tenant_id),"id":str(reconciliation_id)})
        row=db.execute(text("SELECT id,business_date,status,closed_at FROM daily_reconciliations WHERE tenant_id=:t AND id=:id"),{"t":str(tenant_id),"id":str(reconciliation_id)}).mappings().first()
        if not row: raise HTTPException(404,"Reconciliation not found")
        _emit(db,tenant_id,actor,"reconciliation.closed","DAY_CLOSED","reconciliation",reconciliation_id,{"business_date":str(row["business_date"])},request_id)
        result=out(row); _finish(db,idem,200,result,"reconciliation",reconciliation_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except Exception as exc: db.rollback(); raise HTTPException(400,str(exc)) from exc

@router.get("/customer-credits")
def list_customer_credits(ctx=Depends(require_permission("credits.read"))):
    db,_,tenant_id,_=ctx
    rows=db.execute(text("""
      SELECT cc.id,cc.customer_party_id,p.display_name customer_name,cc.source_return_id,cc.original_amount,cc.allocated_amount,cc.balance,cc.status,cc.created_at,cc.updated_at
      FROM customer_credits cc
      JOIN parties p ON p.id=cc.customer_party_id AND p.tenant_id=cc.tenant_id
      WHERE cc.tenant_id=:t AND cc.status IN ('OPEN','PARTIALLY_USED')
      ORDER BY cc.created_at DESC LIMIT 500
    """),{"t":str(tenant_id)}).mappings().all()
    return [out(x) for x in rows]


@router.post("/customer-credits/{credit_id}/allocate", status_code=201)
def allocate_customer_credit(credit_id: UUID, body: CustomerCreditAllocateIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("credits.manage"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.customer_credit.allocate",body.model_dump(mode="json") | {"credit_id":str(credit_id)})
    if cached: return cached_body
    try:
        credit=db.execute(text("""
          SELECT * FROM customer_credits WHERE tenant_id=:t AND id=:id FOR UPDATE
        """),{"t":str(tenant_id),"id":str(credit_id)}).mappings().first()
        if not credit: raise HTTPException(404,"Customer credit not found")
        if credit["status"] not in ('OPEN','PARTIALLY_USED') or Decimal(str(credit["balance"]))<=0:
            raise HTTPException(409,"Customer credit has no available balance")
        receivable=db.execute(text("""
          SELECT * FROM receivables WHERE tenant_id=:t AND id=:id FOR UPDATE
        """),{"t":str(tenant_id),"id":str(body.receivable_id)}).mappings().first()
        if not receivable: raise HTTPException(404,"Receivable not found")
        if receivable["customer_party_id"] != credit["customer_party_id"]:
            raise HTTPException(409,"Customer credit and receivable belong to different customers")
        amount=q(body.amount)
        if amount>Decimal(str(credit["balance"])): raise HTTPException(422,"Allocation exceeds customer credit balance")
        if amount>Decimal(str(receivable["balance"])): raise HTTPException(422,"Allocation exceeds receivable balance")
        aid=db.execute(text("""
          INSERT INTO customer_credit_allocations(tenant_id,customer_credit_id,receivable_id,amount,status,created_by)
          VALUES(:t,:c,:r,:a,'RECORDED',:u) RETURNING id
        """),{"t":str(tenant_id),"c":str(credit_id),"r":str(body.receivable_id),"a":str(amount),"u":str(actor)}).scalar_one()
        result=db.execute(text("""
          SELECT cc.id,cc.customer_party_id,p.display_name customer_name,cc.source_return_id,cc.original_amount,cc.allocated_amount,cc.balance,cc.status,cc.created_at,cc.updated_at
          FROM customer_credits cc JOIN parties p ON p.id=cc.customer_party_id AND p.tenant_id=cc.tenant_id
          WHERE cc.tenant_id=:t AND cc.id=:id
        """),{"t":str(tenant_id),"id":str(credit_id)}).mappings().one()
        _emit(db,tenant_id,actor,"customer_credit.allocated","CUSTOMER_CREDIT_ALLOCATED","customer_credit_allocation",aid,{"credit_id":str(credit_id),"receivable_id":str(body.receivable_id),"amount":str(amount)},request_id)
        result=out(result); _finish(db,idem,201,result,"customer_credit",credit_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except IntegrityError as exc: db.rollback(); raise HTTPException(409,"Customer credit allocation violated a financial invariant") from exc
    except Exception as exc: db.rollback(); raise HTTPException(500,"Customer credit allocation failed") from exc


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

@router.get("/returns")
def list_returns(ctx=Depends(require_permission("returns.manage"))):
    db,_,tenant_id,_=ctx
    rows=db.execute(text("""
      SELECT sr.id,sr.sale_id,sr.status,sr.reason,sr.total,sr.completed_at,sr.created_at,
             COALESCE((SELECT SUM(rr.amount) FROM refund_records rr WHERE rr.return_id=sr.id AND rr.tenant_id=sr.tenant_id AND rr.status='RECORDED'),0) refunded,
             COALESCE((SELECT MAX(cc.balance) FROM customer_credits cc WHERE cc.source_return_id=sr.id AND cc.tenant_id=sr.tenant_id),0) credit_balance
      FROM sale_returns sr
      WHERE sr.tenant_id=:t ORDER BY sr.created_at DESC LIMIT 200
    """),{"t":str(tenant_id)}).mappings().all()
    return [out(x) for x in rows]

@router.post("/sales/{sale_id}/returns", status_code=201)
def create_return(sale_id: UUID, body: ReturnCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("sales.return"))):
    db,actor,tenant_id,_=ctx
    idem,cached,_,cached_body=_idempotency(db,tenant_id,idempotency_key,"commerce.sale.return",body.model_dump(mode="json") | {"sale_id":str(sale_id)})
    if cached: return cached_body
    try:
        sale=db.execute(text("SELECT * FROM sales WHERE tenant_id=:t AND id=:s FOR UPDATE"),{"t":str(tenant_id),"s":str(sale_id)}).mappings().first()
        if not sale: raise HTTPException(404,"Sale not found")
        if sale["status"]!='COMPLETED': raise HTTPException(409,"Only completed sales can be returned")
        if body.settlement_type=='REFUND':
            if body.refund_channel_id is None: raise HTTPException(400,"A refund channel is required for refunds")
            if Decimal(str(sale["amount_paid"]))<=0: raise HTTPException(409,"An unpaid credit sale cannot be refunded; use customer credit")
        if body.settlement_type=='CUSTOMER_CREDIT' and not sale["customer_party_id"]: raise HTTPException(400,"A customer is required for customer credit")
        return_location=body.inventory_location_id or sale["location_id"]
        if return_location is None: raise HTTPException(400,"An inventory location is required for an inventory return")
        tenant_location(db,tenant_id,return_location)
        validated=[]; total=Decimal("0")
        for req_line in body.lines:
            line=db.execute(text("SELECT * FROM transaction_lines WHERE tenant_id=:t AND id=:id AND transaction_id=:tx"),{"t":str(tenant_id),"id":str(req_line.sale_line_id),"tx":str(sale["transaction_id"])}).mappings().first()
            if not line or not line["product_variant_id"]: raise HTTPException(400,"Return line must reference a product sale line")
            returned=db.execute(text("""SELECT COALESCE(SUM(srl.quantity),0) qty FROM sale_return_lines srl JOIN sale_returns sr ON sr.id=srl.return_id AND sr.tenant_id=srl.tenant_id WHERE srl.tenant_id=:t AND srl.sale_line_id=:sl AND sr.status='COMPLETED'"""),{"t":str(tenant_id),"sl":str(req_line.sale_line_id)}).scalar_one()
            available=Decimal(str(line["quantity"]))-Decimal(str(returned))
            if req_line.quantity>available: raise HTTPException(409,"Return quantity exceeds the remaining sale quantity")
            line_total=q((Decimal(str(line["line_total"])) / Decimal(str(line["quantity"]))) * req_line.quantity)
            total+=line_total
            validated.append((req_line,line,line_total))
        total=q(total)
        remaining_sales_value=q(Decimal(str(sale["total"]))-Decimal(str(sale["return_adjustment_amount"])))
        if total<=0 or total>remaining_sales_value: raise HTTPException(422,"Return total is outside the remaining sale value")
        if body.settlement_type=='REFUND' and total>Decimal(str(sale["amount_paid"])): raise HTTPException(422,"Refund cannot exceed the amount collected for this sale")
        tx_ref=f"RET-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
        tx=BusinessTransaction(tenant_id=tenant_id,transaction_type="SALE_RETURN",reference=tx_ref,status="DRAFT",party_id=sale["customer_party_id"],branch_id=sale["branch_id"],total_amount=total,currency_code=sale["currency_code"],occurred_at=datetime.now(timezone.utc),metadata_json={"source":"commerce","sale_id":str(sale_id)})
        db.add(tx); db.flush()
        db.execute(text("""INSERT INTO sale_returns(tenant_id,sale_id,transaction_id,inventory_location_id,status,reason,total,created_by) VALUES(:t,:s,:tx,:l,'DRAFT',:r,:total,:u) RETURNING id"""),{"t":str(tenant_id),"s":str(sale_id),"tx":str(tx.id),"l":str(return_location),"r":body.reason.strip(),"total":str(total),"u":str(actor)})
        return_id=db.execute(text("SELECT id FROM sale_returns WHERE tenant_id=:t AND transaction_id=:tx"),{"t":str(tenant_id),"tx":str(tx.id)}).scalar_one()
        from ..models import InventoryBalance
        for req_line,line,line_total in validated:
            db.execute(text("""INSERT INTO sale_return_lines(tenant_id,return_id,sale_line_id,variant_id,quantity,unit_price,discount_amount,tax_amount,line_total) VALUES(:t,:r,:sl,:v,:q,:u,:d,:tax,:total)"""),{"t":str(tenant_id),"r":str(return_id),"sl":str(req_line.sale_line_id),"v":str(line["product_variant_id"]),"q":str(req_line.quantity),"u":str(line["unit_price"]),"d":str(line["discount_amount"]),"tax":str(line["tax_amount"]),"total":str(line_total)})
            cost_row=db.execute(text("""
              SELECT CASE WHEN SUM(ABS(quantity_delta))=0 THEN 0
                          ELSE SUM(total_cost)/SUM(ABS(quantity_delta)) END unit_cost
              FROM inventory_transactions
              WHERE tenant_id=:t AND reference_type='sale' AND reference_id=:sale AND variant_id=:v AND quantity_delta<0
            """),{"t":str(tenant_id),"sale":str(sale_id),"v":str(line["product_variant_id"])}).mappings().one()
            unit_cost=Decimal(str(cost_row["unit_cost"] or 0))
            post_ledger(db,tenant_id=tenant_id,actor_user_id=actor,location_id=return_location,variant_id=line["product_variant_id"],quantity_delta=q(req_line.quantity),unit_cost=unit_cost,transaction_type="RETURN",reference_type="sale_return",reference_id=return_id,idempotency_key=f"{idempotency_key or return_id}:inventory:{req_line.sale_line_id}",metadata={"sale_id":str(sale_id),"return_id":str(return_id),"cost_basis":"ORIGINAL_SALE_LEDGER"})
        db.execute(text("UPDATE sales SET return_adjustment_amount=return_adjustment_amount+:a,updated_at=now() WHERE tenant_id=:t AND id=:s"),{"t":str(tenant_id),"s":str(sale_id),"a":str(total)})
        db.execute(text("""
          UPDATE receivables
          SET adjustment_amount=LEAST(original_amount,adjustment_amount+:a),
              balance=GREATEST(original_amount-paid_amount-LEAST(original_amount,adjustment_amount+:a),0),
              status=CASE
                WHEN GREATEST(original_amount-paid_amount-LEAST(original_amount,adjustment_amount+:a),0)=0 THEN 'PAID'
                WHEN paid_amount>0 THEN 'PARTIALLY_PAID'
                ELSE 'OPEN'
              END,
              updated_at=now()
          WHERE tenant_id=:t AND sale_id=:s AND status IN ('OPEN','PARTIALLY_PAID')
        """),{"t":str(tenant_id),"s":str(sale_id),"a":str(total)})
        db.execute(text("UPDATE sale_returns SET status='COMPLETED',completed_by=:u,completed_at=now(),updated_at=now() WHERE tenant_id=:t AND id=:r"),{"t":str(tenant_id),"r":str(return_id),"u":str(actor)})
        db.execute(text("UPDATE business_transactions SET status='COMPLETED',closed_at=now(),updated_at=now() WHERE tenant_id=:t AND id=:tx"),{"t":str(tenant_id),"tx":str(tx.id)})
        db.execute(text("INSERT INTO transaction_status_history(tenant_id,transaction_id,from_status,to_status,reason,changed_by) VALUES(:t,:tx,'DRAFT','COMPLETED','Sale return completed',:u)"),{"t":str(tenant_id),"tx":str(tx.id),"u":str(actor)})
        db.execute(text("SELECT refresh_sale_payment_totals(:t,:s)"),{"t":str(tenant_id),"s":str(sale_id)})
        if body.settlement_type=='REFUND':
            ch=_channel(db,tenant_id,body.refund_channel_id,sale["currency_code"])
            refund_id=db.execute(text("""INSERT INTO refund_records(tenant_id,return_id,payment_channel_id,amount,currency_code,reference,status,business_date,created_by) VALUES(:t,:r,:c,:a,:cur,:ref,'RECORDED',:d,:u) RETURNING id"""),{"t":str(tenant_id),"r":str(return_id),"c":str(ch["id"]),"a":str(total),"cur":sale["currency_code"],"ref":f"REF-{tx_ref}","d":body.business_date,"u":str(actor)}).scalar_one()
            _emit(db,tenant_id,actor,"refund.recorded","REFUND_RECORDED","refund",refund_id,{"return_id":str(return_id),"amount":str(total),"channel_id":str(ch["id"])},request_id)
        elif body.settlement_type=='CUSTOMER_CREDIT':
            credit_id=db.execute(text("""INSERT INTO customer_credits(tenant_id,customer_party_id,source_return_id,original_amount,allocated_amount,balance,status) VALUES(:t,:p,:r,:a,0,:a,'OPEN') RETURNING id"""),{"t":str(tenant_id),"p":str(sale["customer_party_id"]),"r":str(return_id),"a":str(total)}).scalar_one()
            _emit(db,tenant_id,actor,"customer_credit.created","CUSTOMER_CREDIT_CREATED","customer_credit",credit_id,{"return_id":str(return_id),"amount":str(total)},request_id)
        _emit(db,tenant_id,actor,"sale.return.created","RETURN_CREATED","sale_return",return_id,{"sale_id":str(sale_id),"total":str(total)},request_id)
        result=db.execute(text("SELECT id,sale_id,status,reason,total,completed_at,created_at FROM sale_returns WHERE tenant_id=:t AND id=:r"),{"t":str(tenant_id),"r":str(return_id)}).mappings().one(); result=out(result)
        _finish(db,idem,201,result,"sale_return",return_id); db.commit(); return result
    except HTTPException: db.rollback(); raise
    except IntegrityError as exc: db.rollback(); raise HTTPException(409,"Return could not be committed because a business invariant was violated") from exc
    except Exception as exc: db.rollback(); raise HTTPException(500,"Return creation failed") from exc
