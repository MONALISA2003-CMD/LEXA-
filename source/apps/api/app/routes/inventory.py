from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import bindparam, case, func, select, text
from sqlalchemy.orm import Session

from ..catalog import emit_event, write_audit
from ..branch_access import accessible_location_ids, ensure_location_access, require_full_branch_scope
from ..dependencies import require_permission
from ..inventory import (
    ZERO,
    change_inbound, get_or_create_balance, idempotent_finish, idempotent_start,
    now, post_ledger, q, serialize_balance, tenant_location, tenant_variant,
)
from ..models import (
    InventoryAdjustment, InventoryAdjustmentLine, InventoryBalance, InventoryTransaction,
    InventoryTransfer, InventoryTransferLine, Location, Product, ProductVariant, StockCount, StockCountLine,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])

class BalanceOut(BaseModel):
    id: UUID; tenant_id: UUID; location_id: UUID; variant_id: UUID
    on_hand: Decimal; reserved: Decimal; available: Decimal; inbound: Decimal
    average_cost: Decimal; stock_value: Decimal
    updated_at: Any

class LedgerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; tenant_id: UUID; location_id: UUID; variant_id: UUID
    transaction_type: str; quantity_delta: Decimal; unit_cost: Decimal; total_cost: Decimal
    balance_after: Decimal; reference_type: str | None; reference_id: UUID | None
    source_transaction_id: UUID | None; occurred_at: Any
    metadata: dict = Field(validation_alias="inventory_metadata")

class AdjustmentLineIn(BaseModel):
    variant_id: UUID
    quantity_delta: Decimal
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
class AdjustmentIn(BaseModel):
    location_id: UUID; reason_code: str = Field(min_length=2, max_length=60)
    notes: str | None = None; lines: list[AdjustmentLineIn] = Field(min_length=1)

class CountLineIn(BaseModel):
    variant_id: UUID
    counted_quantity: Decimal | None = Field(default=None, ge=0)
class CountIn(BaseModel):
    location_id: UUID; scope_description: str | None = None
    variant_ids: list[UUID] = Field(min_length=1)
class CountUpdateIn(BaseModel):
    lines: list[CountLineIn] = Field(min_length=1)

class TransferLineIn(BaseModel):
    variant_id: UUID; quantity: Decimal = Field(gt=0)
class TransferIn(BaseModel):
    source_location_id: UUID; destination_location_id: UUID
    notes: str | None = None; lines: list[TransferLineIn] = Field(min_length=1)
class TransferReceiveIn(BaseModel):
    lines: list[CountLineIn] = Field(min_length=1)

class ReplenishmentPolicyIn(BaseModel):
    location_id: UUID
    variant_id: UUID
    lead_time_days: int = Field(default=7, ge=0, le=365)
    review_period_days: int = Field(default=7, ge=1, le=90)
    lookback_days: int = Field(default=30, ge=7, le=365)
    minimum_available: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=6)
    safety_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=6)
    enabled: bool = True


class ActionOut(BaseModel):
    id: UUID; status: str


def _action_response(row, status: str):
    return {"id": row.id, "status": status}


def _finish_idempotency(db, idem, response):
    if isinstance(idem, tuple):
        return idem[1]
    encoded = jsonable_encoder(response)
    idempotent_finish(db, idem, 200, encoded)
    return None


def _commit(db: Session, idem, response):
    replay = _finish_idempotency(db, idem, response)
    db.commit()
    if replay is not None:
        return replay
    return response

@router.get("/balances", response_model=list[BalanceOut])
def balances(
    location_id: UUID | None = None, variant_id: UUID | None = None,
    q_search: str | None = Query(None, alias="q"), limit: int = Query(100, ge=1, le=500),
    ctx=Depends(require_permission("inventory.read")),
):
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    stmt = select(InventoryBalance).where(InventoryBalance.tenant_id == tenant_id, InventoryBalance.location_id.in_(allowed_locations))
    if location_id:
        ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=location_id)
        stmt = stmt.where(InventoryBalance.location_id == location_id)
    if variant_id: stmt = stmt.where(InventoryBalance.variant_id == variant_id)
    if q_search:
        like = f"%{q_search.strip()}%"
        stmt = stmt.join(ProductVariant, (ProductVariant.id == InventoryBalance.variant_id) & (ProductVariant.tenant_id == InventoryBalance.tenant_id)).join(Product, Product.id == ProductVariant.product_id).where(
            Product.name.ilike(like) | ProductVariant.sku.ilike(like)
        )
    rows = list(db.scalars(stmt.order_by(InventoryBalance.updated_at.desc()).limit(limit)))
    return [serialize_balance(r) for r in rows]

@router.get("/summary")
def inventory_summary(ctx=Depends(require_permission("inventory.read"))):
    """Aggregate inventory health across every location the member can access.

    The dashboard must not infer workspace stock value or alert counts from the
    capped, detail-oriented /balances list. This endpoint calculates totals in
    PostgreSQL and returns a small, actionable set of low/out-of-stock rows.
    """
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    available = InventoryBalance.on_hand - InventoryBalance.reserved
    summary = db.execute(
        select(
            func.coalesce(func.sum(InventoryBalance.stock_value), 0).label("stock_value"),
            func.count(InventoryBalance.id).label("balance_rows"),
            func.coalesce(func.sum(case((available <= 0, 1), else_=0)), 0).label("out_of_stock_rows"),
            func.coalesce(func.sum(case(((available > 0) & (available <= 5), 1), else_=0)), 0).label("low_stock_rows"),
        ).where(
            InventoryBalance.tenant_id == tenant_id,
            InventoryBalance.location_id.in_(allowed_locations),
        )
    ).mappings().one()

    attention_rows = db.execute(
        select(
            InventoryBalance.variant_id,
            InventoryBalance.location_id,
            InventoryBalance.on_hand,
            InventoryBalance.reserved,
            available.label("available"),
            Product.name.label("product_name"),
            ProductVariant.sku.label("sku"),
            Location.name.label("location_name"),
        )
        .join(ProductVariant, (ProductVariant.id == InventoryBalance.variant_id) & (ProductVariant.tenant_id == InventoryBalance.tenant_id))
        .join(Product, (Product.id == ProductVariant.product_id) & (Product.tenant_id == ProductVariant.tenant_id))
        .join(Location, (Location.id == InventoryBalance.location_id) & (Location.tenant_id == InventoryBalance.tenant_id))
        .where(
            InventoryBalance.tenant_id == tenant_id,
            InventoryBalance.location_id.in_(allowed_locations),
            available <= 5,
        )
        .order_by(available.asc(), InventoryBalance.updated_at.desc())
        .limit(10)
    ).mappings().all()

    return {
        "stock_value": str(summary["stock_value"] or 0),
        "balance_rows": int(summary["balance_rows"] or 0),
        "out_of_stock_rows": int(summary["out_of_stock_rows"] or 0),
        "low_stock_rows": int(summary["low_stock_rows"] or 0),
        "attention": [
            {
                "variant_id": str(row["variant_id"]),
                "location_id": str(row["location_id"]),
                "on_hand": str(row["on_hand"]),
                "reserved": str(row["reserved"]),
                "available": str(row["available"]),
                "product_name": row["product_name"],
                "sku": row["sku"],
                "location_name": row["location_name"],
            }
            for row in attention_rows
        ],
    }


@router.get("/ledger", response_model=list[LedgerOut])
def ledger(
    location_id: UUID | None = None, variant_id: UUID | None = None,
    transaction_type: str | None = None, limit: int = Query(100, ge=1, le=500),
    ctx=Depends(require_permission("inventory.read")),
):
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    stmt = select(InventoryTransaction).where(InventoryTransaction.tenant_id == tenant_id, InventoryTransaction.location_id.in_(allowed_locations))
    if location_id:
        ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=location_id)
        stmt = stmt.where(InventoryTransaction.location_id == location_id)
    if variant_id: stmt = stmt.where(InventoryTransaction.variant_id == variant_id)
    if transaction_type: stmt = stmt.where(InventoryTransaction.transaction_type == transaction_type)
    return list(db.scalars(stmt.order_by(InventoryTransaction.occurred_at.desc(), InventoryTransaction.id.desc()).limit(limit)))

@router.get("/products/{variant_id}")
def product_inventory(variant_id: UUID, ctx=Depends(require_permission("inventory.read"))):
    db, actor_id, tenant_id, _ = ctx
    tenant_variant(db, tenant_id, variant_id)
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    balances = list(db.scalars(select(InventoryBalance).where(InventoryBalance.tenant_id == tenant_id, InventoryBalance.variant_id == variant_id, InventoryBalance.location_id.in_(allowed_locations)).order_by(InventoryBalance.updated_at.desc())))
    recent = list(db.scalars(select(InventoryTransaction).where(InventoryTransaction.tenant_id == tenant_id, InventoryTransaction.variant_id == variant_id, InventoryTransaction.location_id.in_(allowed_locations)).order_by(InventoryTransaction.occurred_at.desc()).limit(25)))
    return {"balances": [serialize_balance(r) for r in balances], "ledger": recent}

@router.post("/adjustments")
def create_adjustment(body: AdjustmentIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.manage"))):
    db, actor, tenant_id, _ = ctx
    tenant_location(db, tenant_id, body.location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=body.location_id)
    if len({line.variant_id for line in body.lines}) != len(body.lines):
        raise HTTPException(422, "Adjustment cannot contain the same variant twice")
    for line in body.lines:
        tenant_variant(db, tenant_id, line.variant_id)
        if line.quantity_delta == 0: raise HTTPException(422, "Adjustment quantity cannot be zero")
        if line.quantity_delta > 0 and line.unit_cost <= 0: raise HTTPException(422, "Positive adjustment requires a unit cost")
    payload = body.model_dump(mode="json")
    idem = idempotent_start(db, tenant_id, "inventory.adjustment.create", idempotency_key, payload)
    if isinstance(idem, tuple): return idem[1]
    row = InventoryAdjustment(tenant_id=tenant_id, location_id=body.location_id, reason_code=body.reason_code.strip().upper(), notes=body.notes, created_by=actor, idempotency_key=idempotency_key)
    db.add(row); db.flush()
    for line in body.lines:
        db.add(InventoryAdjustmentLine(tenant_id=tenant_id, adjustment_id=row.id, variant_id=line.variant_id, quantity_delta=q(line.quantity_delta), unit_cost=q(line.unit_cost), notes=line.notes))
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.adjustment.created", target_type="inventory_adjustment", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.adjustment.created.v1", aggregate_type="inventory_adjustment", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "status": row.status})
    return _commit(db, idem, {"id": row.id, "status": row.status})

@router.post("/adjustments/{adjustment_id}/approve")
def approve_adjustment(adjustment_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.adjust.approve"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(InventoryAdjustment).where(InventoryAdjustment.id == adjustment_id, InventoryAdjustment.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Adjustment not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.location_id)
    if row.status != "DRAFT": raise HTTPException(409, f"Adjustment cannot be approved from {row.status}")
    idem = idempotent_start(db, tenant_id, "inventory.adjustment.approve", idempotency_key, {"adjustment_id": str(adjustment_id)})
    if isinstance(idem, tuple): return idem[1]
    if not db.scalar(select(InventoryAdjustmentLine.id).where(InventoryAdjustmentLine.adjustment_id == row.id, InventoryAdjustmentLine.tenant_id == tenant_id)): raise HTTPException(409, "Adjustment has no lines")
    row.status = "APPROVED"; row.approved_by = actor; row.approved_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.adjustment.approved", target_type="inventory_adjustment", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.adjustment.approved.v1", aggregate_type="inventory_adjustment", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id)})
    return _commit(db, idem, _action_response(row, row.status))

@router.post("/adjustments/{adjustment_id}/post")
def post_adjustment(adjustment_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.adjust.post"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(InventoryAdjustment).where(InventoryAdjustment.id == adjustment_id, InventoryAdjustment.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Adjustment not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.location_id)
    if row.status != "APPROVED": raise HTTPException(409, f"Adjustment cannot be posted from {row.status}")
    idem = idempotent_start(db, tenant_id, "inventory.adjustment.post", idempotency_key, {"adjustment_id": str(adjustment_id)})
    if isinstance(idem, tuple): return idem[1]
    lines = list(db.scalars(select(InventoryAdjustmentLine).where(InventoryAdjustmentLine.adjustment_id == row.id, InventoryAdjustmentLine.tenant_id == tenant_id)))
    for line in lines:
        post_ledger(db, tenant_id=tenant_id, actor_user_id=actor, location_id=row.location_id, variant_id=line.variant_id, quantity_delta=line.quantity_delta, unit_cost=line.unit_cost, transaction_type="ADJUSTMENT", reference_type="inventory_adjustment", reference_id=row.id, metadata={"reason_code": row.reason_code, "notes": line.notes})
    row.status = "POSTED"; row.posted_by = actor; row.posted_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.adjustment.posted", target_type="inventory_adjustment", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.adjustment.posted.v1", aggregate_type="inventory_adjustment", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "line_count": len(lines)})
    return _commit(db, idem, _action_response(row, row.status))

@router.post("/stock-counts")
def create_stock_count(body: CountIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.count.manage"))):
    db, actor, tenant_id, _ = ctx
    tenant_location(db, tenant_id, body.location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=body.location_id)
    if len(set(body.variant_ids)) != len(body.variant_ids): raise HTTPException(422, "Stock count cannot contain duplicate variants")
    for variant_id in body.variant_ids: tenant_variant(db, tenant_id, variant_id)
    idem = idempotent_start(db, tenant_id, "inventory.stock_count.create", idempotency_key, body.model_dump(mode="json"))
    if isinstance(idem, tuple): return idem[1]
    row = StockCount(tenant_id=tenant_id, location_id=body.location_id, scope_description=body.scope_description, status="COUNTING", started_at=now(), created_by=actor)
    db.add(row); db.flush()
    for variant_id in body.variant_ids:
        bal = get_or_create_balance(db, tenant_id, body.location_id, variant_id)
        db.add(StockCountLine(tenant_id=tenant_id, stock_count_id=row.id, variant_id=variant_id, expected_quantity=q(bal.on_hand), unit_cost=q(bal.average_cost)))
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.stock_count.created", target_type="stock_count", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.stock_count.created.v1", aggregate_type="stock_count", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "line_count": len(body.variant_ids)})
    return _commit(db, idem, {"id": row.id, "status": row.status})

@router.patch("/stock-counts/{count_id}/lines")
def update_count_lines(count_id: UUID, body: CountUpdateIn, ctx=Depends(require_permission("inventory.count.manage"))):
    db, actor, tenant_id, _ = ctx
    count = db.scalar(select(StockCount).where(StockCount.id == count_id, StockCount.tenant_id == tenant_id).with_for_update())
    if not count: raise HTTPException(404, "Stock count not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=count.location_id)
    if count.status != "COUNTING": raise HTTPException(409, f"Stock count cannot be edited from {count.status}")
    for item in body.lines:
        line = db.scalar(select(StockCountLine).where(StockCountLine.stock_count_id == count_id, StockCountLine.tenant_id == tenant_id, StockCountLine.variant_id == item.variant_id).with_for_update())
        if not line: raise HTTPException(404, "Stock count line not found")
        line.counted_quantity = item.counted_quantity
        line.variance_quantity = None if item.counted_quantity is None else q(item.counted_quantity - line.expected_quantity)
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.stock_count.lines_updated", target_type="stock_count", target_id=count.id)
    db.commit()
    return {"id": count.id, "status": count.status}

@router.post("/stock-counts/{count_id}/submit")
def submit_stock_count(count_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.count.manage"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(StockCount).where(StockCount.id == count_id, StockCount.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Stock count not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.location_id)
    if row.status != "COUNTING": raise HTTPException(409, f"Stock count cannot be submitted from {row.status}")
    lines = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == row.id, StockCountLine.tenant_id == tenant_id)))
    if not lines or any(line.counted_quantity is None for line in lines): raise HTTPException(422, "Every stock count line must have a counted quantity before submission")
    idem = idempotent_start(db, tenant_id, "inventory.stock_count.submit", idempotency_key, {"count_id": str(count_id)})
    if isinstance(idem, tuple): return idem[1]
    row.status = "SUBMITTED"; row.submitted_by = actor; row.submitted_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.stock_count.submitted", target_type="stock_count", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.stock_count.submitted.v1", aggregate_type="stock_count", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id)})
    return _commit(db, idem, _action_response(row, row.status))

@router.post("/stock-counts/{count_id}/approve")
def approve_stock_count(count_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.count.approve"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(StockCount).where(StockCount.id == count_id, StockCount.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Stock count not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.location_id)
    if row.status != "SUBMITTED": raise HTTPException(409, f"Stock count cannot be approved from {row.status}")
    idem = idempotent_start(db, tenant_id, "inventory.stock_count.approve", idempotency_key, {"count_id": str(count_id)})
    if isinstance(idem, tuple): return idem[1]
    row.status = "APPROVED"; row.approved_by = actor; row.approved_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.stock_count.approved", target_type="stock_count", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.stock_count.approved.v1", aggregate_type="stock_count", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id)})
    return _commit(db, idem, _action_response(row, row.status))

@router.post("/stock-counts/{count_id}/post")
def post_stock_count(count_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.count.post"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(StockCount).where(StockCount.id == count_id, StockCount.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Stock count not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.location_id)
    if row.status != "APPROVED": raise HTTPException(409, f"Stock count cannot be posted from {row.status}")
    idem = idempotent_start(db, tenant_id, "inventory.stock_count.post", idempotency_key, {"count_id": str(count_id)})
    if isinstance(idem, tuple): return idem[1]
    lines = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == row.id, StockCountLine.tenant_id == tenant_id)))
    for line in lines:
        variance = q(line.counted_quantity - line.expected_quantity) if line.counted_quantity is not None else ZERO
        if variance:
            post_ledger(db, tenant_id=tenant_id, actor_user_id=actor, location_id=row.location_id, variant_id=line.variant_id, quantity_delta=variance, unit_cost=q(line.unit_cost), transaction_type="COUNT_RECONCILIATION", reference_type="stock_count", reference_id=row.id, metadata={"expected_quantity": str(line.expected_quantity), "counted_quantity": str(line.counted_quantity)})
    row.status = "POSTED"; row.posted_by = actor; row.posted_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.stock_count.posted", target_type="stock_count", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.stock_count.posted.v1", aggregate_type="stock_count", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "variance_lines": sum(1 for l in lines if l.variance_quantity)})
    return _commit(db, idem, _action_response(row, row.status))

@router.get("/transfers")
def list_transfers(status: str | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("inventory.read"))):
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    stmt = select(InventoryTransfer).where(InventoryTransfer.tenant_id == tenant_id, InventoryTransfer.source_location_id.in_(allowed_locations), InventoryTransfer.destination_location_id.in_(allowed_locations))
    if status: stmt = stmt.where(InventoryTransfer.status == status)
    rows = list(db.scalars(stmt.order_by(InventoryTransfer.created_at.desc()).limit(limit)))
    result = []
    for row in rows:
        lines = list(db.scalars(select(InventoryTransferLine).where(InventoryTransferLine.transfer_id == row.id, InventoryTransferLine.tenant_id == tenant_id)))
        result.append({"id": row.id, "source_location_id": row.source_location_id, "destination_location_id": row.destination_location_id, "status": row.status, "notes": row.notes, "created_at": row.created_at, "lines": lines})
    return result

@router.post("/transfers")
def create_transfer(body: TransferIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.transfer.create"))):
    db, actor, tenant_id, _ = ctx
    if body.source_location_id == body.destination_location_id: raise HTTPException(422, "Source and destination locations must be different")
    tenant_location(db, tenant_id, body.source_location_id); tenant_location(db, tenant_id, body.destination_location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=body.source_location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=body.destination_location_id)
    if len({line.variant_id for line in body.lines}) != len(body.lines): raise HTTPException(422, "Transfer cannot contain duplicate variants")
    for line in body.lines: tenant_variant(db, tenant_id, line.variant_id)
    idem = idempotent_start(db, tenant_id, "inventory.transfer.create", idempotency_key, body.model_dump(mode="json"))
    if isinstance(idem, tuple): return idem[1]
    row = InventoryTransfer(tenant_id=tenant_id, source_location_id=body.source_location_id, destination_location_id=body.destination_location_id, notes=body.notes, created_by=actor)
    db.add(row); db.flush()
    for line in body.lines: db.add(InventoryTransferLine(tenant_id=tenant_id, transfer_id=row.id, variant_id=line.variant_id, requested_quantity=q(line.quantity)))
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.transfer.created", target_type="inventory_transfer", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.transfer.created.v1", aggregate_type="inventory_transfer", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "line_count": len(body.lines)})
    return _commit(db, idem, {"id": row.id, "status": row.status})

@router.post("/transfers/{transfer_id}/approve")
def approve_transfer(transfer_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.transfer.approve"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(InventoryTransfer).where(InventoryTransfer.id == transfer_id, InventoryTransfer.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Transfer not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.source_location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.destination_location_id)
    if row.status != "DRAFT": raise HTTPException(409, f"Transfer cannot be approved from {row.status}")
    lines = list(db.scalars(select(InventoryTransferLine).where(InventoryTransferLine.transfer_id == row.id, InventoryTransferLine.tenant_id == tenant_id)))
    if not lines: raise HTTPException(409, "Transfer has no lines")
    idem = idempotent_start(db, tenant_id, "inventory.transfer.approve", idempotency_key, {"transfer_id": str(transfer_id)})
    if isinstance(idem, tuple): return idem[1]
    row.status = "APPROVED"; row.approved_by = actor; row.approved_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.transfer.approved", target_type="inventory_transfer", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.transfer.approved.v1", aggregate_type="inventory_transfer", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id)})
    return _commit(db, idem, _action_response(row, row.status))

@router.post("/transfers/{transfer_id}/dispatch")
def dispatch_transfer(transfer_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.transfer.dispatch"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(InventoryTransfer).where(InventoryTransfer.id == transfer_id, InventoryTransfer.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Transfer not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.source_location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.destination_location_id)
    if row.status != "APPROVED": raise HTTPException(409, f"Transfer cannot be dispatched from {row.status}")
    idem = idempotent_start(db, tenant_id, "inventory.transfer.dispatch", idempotency_key, {"transfer_id": str(transfer_id)})
    if isinstance(idem, tuple): return idem[1]
    lines = list(db.scalars(select(InventoryTransferLine).where(InventoryTransferLine.transfer_id == row.id, InventoryTransferLine.tenant_id == tenant_id).with_for_update()))
    for line in lines:
        remaining = q(line.requested_quantity - line.dispatched_quantity)
        if remaining <= 0: continue
        bal = get_or_create_balance(db, tenant_id, row.source_location_id, line.variant_id)
        if q(bal.on_hand) - q(bal.reserved) < remaining: raise HTTPException(409, f"Insufficient stock for transfer line {line.variant_id}")
        tx = post_ledger(db, tenant_id=tenant_id, actor_user_id=actor, location_id=row.source_location_id, variant_id=line.variant_id, quantity_delta=-remaining, unit_cost=q(bal.average_cost), transaction_type="TRANSFER_OUT", reference_type="inventory_transfer", reference_id=row.id, metadata={"destination_location_id": str(row.destination_location_id)})
        line.dispatched_quantity = q(line.dispatched_quantity + remaining); line.unit_cost = q(tx.unit_cost)
        change_inbound(db, tenant_id, row.destination_location_id, line.variant_id, remaining)
    row.status = "DISPATCHED"; row.dispatched_by = actor; row.dispatched_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.transfer.dispatched", target_type="inventory_transfer", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.transfer.dispatched.v1", aggregate_type="inventory_transfer", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id)})
    return _commit(db, idem, _action_response(row, row.status))

@router.post("/transfers/{transfer_id}/receive")
def receive_transfer(transfer_id: UUID, body: TransferReceiveIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.transfer.receive"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(InventoryTransfer).where(InventoryTransfer.id == transfer_id, InventoryTransfer.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Transfer not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.source_location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.destination_location_id)
    if row.status not in {"DISPATCHED", "PARTIALLY_RECEIVED"}: raise HTTPException(409, f"Transfer cannot be received from {row.status}")
    if len({x.variant_id for x in body.lines}) != len(body.lines): raise HTTPException(422, "Receive cannot contain duplicate variants")
    idem = idempotent_start(db, tenant_id, "inventory.transfer.receive", idempotency_key, body.model_dump(mode="json") | {"transfer_id": str(transfer_id)})
    if isinstance(idem, tuple): return idem[1]
    for item in body.lines:
        line = db.scalar(select(InventoryTransferLine).where(InventoryTransferLine.transfer_id == row.id, InventoryTransferLine.variant_id == item.variant_id, InventoryTransferLine.tenant_id == tenant_id).with_for_update())
        if not line: raise HTTPException(404, "Transfer line not found")
        qty = q(item.counted_quantity or ZERO)
        remaining = q(line.dispatched_quantity - line.received_quantity)
        if qty <= 0: raise HTTPException(422, "Receive quantity must be positive")
        if qty > remaining: raise HTTPException(409, "TRANSFER_QUANTITY_EXCEEDED")
        post_ledger(db, tenant_id=tenant_id, actor_user_id=actor, location_id=row.destination_location_id, variant_id=line.variant_id, quantity_delta=qty, unit_cost=q(line.unit_cost), transaction_type="TRANSFER_IN", reference_type="inventory_transfer", reference_id=row.id, metadata={"source_location_id": str(row.source_location_id)})
        line.received_quantity = q(line.received_quantity + qty)
        change_inbound(db, tenant_id, row.destination_location_id, line.variant_id, -qty)
    lines = list(db.scalars(select(InventoryTransferLine).where(InventoryTransferLine.transfer_id == row.id, InventoryTransferLine.tenant_id == tenant_id)))
    row.status = "RECEIVED" if all(q(l.received_quantity) == q(l.dispatched_quantity) for l in lines) else "PARTIALLY_RECEIVED"
    row.received_by = actor; row.received_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.transfer.received", target_type="inventory_transfer", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.transfer.received.v1", aggregate_type="inventory_transfer", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "status": row.status})
    return _commit(db, idem, _action_response(row, row.status))

@router.post("/transfers/{transfer_id}/complete")
def complete_transfer(transfer_id: UUID, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.transfer.complete"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(InventoryTransfer).where(InventoryTransfer.id == transfer_id, InventoryTransfer.tenant_id == tenant_id).with_for_update())
    if not row: raise HTTPException(404, "Transfer not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.source_location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=row.destination_location_id)
    if row.status != "RECEIVED": raise HTTPException(409, f"Transfer cannot be completed from {row.status}")
    idem = idempotent_start(db, tenant_id, "inventory.transfer.complete", idempotency_key, {"transfer_id": str(transfer_id)})
    if isinstance(idem, tuple): return idem[1]
    row.status = "COMPLETED"; row.completed_by = actor; row.completed_at = now()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.transfer.completed", target_type="inventory_transfer", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.transfer.completed.v1", aggregate_type="inventory_transfer", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id)})
    return _commit(db, idem, _action_response(row, row.status))

@router.get("/variant-options")
def variant_options(ctx=Depends(require_permission("inventory.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.execute(select(ProductVariant.id, ProductVariant.sku, ProductVariant.name, Product.name.label("product_name"))
                     .join(Product, Product.id == ProductVariant.product_id)
                     .where(ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None), ProductVariant.status == "ACTIVE", Product.tenant_id == tenant_id, Product.deleted_at.is_(None), Product.status == "ACTIVE")
                     .order_by(Product.name, ProductVariant.name)).all()
    return [{"id": r.id, "sku": r.sku, "name": r.name, "product_name": r.product_name} for r in rows]

@router.get("/adjustments")
def list_adjustments(status: str | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("inventory.read"))):
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    stmt = select(InventoryAdjustment).where(InventoryAdjustment.tenant_id == tenant_id, InventoryAdjustment.location_id.in_(allowed_locations))
    if status: stmt = stmt.where(InventoryAdjustment.status == status)
    rows = list(db.scalars(stmt.order_by(InventoryAdjustment.created_at.desc()).limit(limit)))
    result = []
    for row in rows:
        lines = list(db.scalars(select(InventoryAdjustmentLine).where(InventoryAdjustmentLine.adjustment_id == row.id, InventoryAdjustmentLine.tenant_id == tenant_id)))
        result.append({"id": row.id, "location_id": row.location_id, "reason_code": row.reason_code, "notes": row.notes, "status": row.status, "created_at": row.created_at, "lines": lines})
    return result

@router.get("/stock-counts")
def list_stock_counts(status: str | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("inventory.read"))):
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    stmt = select(StockCount).where(StockCount.tenant_id == tenant_id, StockCount.location_id.in_(allowed_locations))
    if status: stmt = stmt.where(StockCount.status == status)
    rows = list(db.scalars(stmt.order_by(StockCount.created_at.desc()).limit(limit)))
    result = []
    for row in rows:
        lines = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == row.id, StockCountLine.tenant_id == tenant_id)))
        result.append({"id": row.id, "location_id": row.location_id, "status": row.status, "scope_description": row.scope_description, "started_at": row.started_at, "created_at": row.created_at, "lines": lines})
    return result

@router.get("/stock-counts/{count_id}")
def get_stock_count(count_id: UUID, ctx=Depends(require_permission("inventory.read"))):
    db, actor_id, tenant_id, _ = ctx
    row = db.scalar(select(StockCount).where(StockCount.id == count_id, StockCount.tenant_id == tenant_id))
    if not row: raise HTTPException(404, "Stock count not found")
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=row.location_id)
    lines = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == row.id, StockCountLine.tenant_id == tenant_id)))
    return {"id": row.id, "location_id": row.location_id, "status": row.status, "scope_description": row.scope_description, "started_at": row.started_at, "created_at": row.created_at, "lines": lines}



@router.get("/replenishment/policies")
def list_replenishment_policies(
    location_id: UUID | None = None,
    variant_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    ctx=Depends(require_permission("inventory.read")),
):
    """List location-and-variant-specific replenishment assumptions."""
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    if location_id:
        ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=location_id)
    stmt = text("""
        SELECT p.id, p.location_id, p.variant_id, p.lead_time_days, p.review_period_days,
               p.lookback_days, p.minimum_available, p.safety_stock, p.enabled,
               p.created_at, p.updated_at, l.name AS location_name, pr.name AS product_name,
               pv.name AS variant_name, pv.sku
          FROM public.inventory_replenishment_policies p
          JOIN public.locations l ON l.tenant_id=p.tenant_id AND l.id=p.location_id
          JOIN public.product_variants pv ON pv.tenant_id=p.tenant_id AND pv.id=p.variant_id
          JOIN public.products pr ON pr.tenant_id=p.tenant_id AND pr.id=pv.product_id
         WHERE p.tenant_id=:tenant_id AND p.location_id IN :allowed_location_ids
           AND (:location_id IS NULL OR p.location_id=:location_id)
           AND (:variant_id IS NULL OR p.variant_id=:variant_id)
         ORDER BY l.name, pr.name, pv.sku
         LIMIT :limit
    """).bindparams(bindparam("allowed_location_ids", expanding=True))
    rows = db.execute(stmt, {
        "tenant_id": str(tenant_id),
        "allowed_location_ids": list(allowed_locations),
        "location_id": str(location_id) if location_id else None,
        "variant_id": str(variant_id) if variant_id else None,
        "limit": limit,
    }).mappings().all()
    return [{
        "id": str(r["id"]), "location_id": str(r["location_id"]), "variant_id": str(r["variant_id"]),
        "location_name": r["location_name"], "product_name": r["product_name"],
        "variant_name": r["variant_name"], "sku": r["sku"],
        "lead_time_days": r["lead_time_days"], "review_period_days": r["review_period_days"],
        "lookback_days": r["lookback_days"], "minimum_available": str(r["minimum_available"]),
        "safety_stock": str(r["safety_stock"]), "enabled": r["enabled"],
        "created_at": r["created_at"], "updated_at": r["updated_at"],
    } for r in rows]


@router.put("/replenishment/policies")
def upsert_replenishment_policy(
    body: ReplenishmentPolicyIn,
    ctx=Depends(require_permission("inventory.manage")),
):
    """Idempotently configure a replenishment policy for one tracked variant at one location."""
    db, actor_id, tenant_id, _ = ctx
    tenant_location(db, tenant_id, body.location_id)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=body.location_id)
    variant = tenant_variant(db, tenant_id, body.variant_id)
    if not variant.track_inventory:
        raise HTTPException(422, "Replenishment policies are available only for inventory-tracked variants")

    row = db.execute(text("""
        INSERT INTO public.inventory_replenishment_policies
          (tenant_id, location_id, variant_id, lead_time_days, review_period_days,
           lookback_days, minimum_available, safety_stock, enabled, created_by, updated_by)
        VALUES
          (:tenant_id, :location_id, :variant_id, :lead_time_days, :review_period_days,
           :lookback_days, :minimum_available, :safety_stock, :enabled, :actor_id, :actor_id)
        ON CONFLICT (tenant_id, location_id, variant_id) DO UPDATE SET
          lead_time_days=EXCLUDED.lead_time_days,
          review_period_days=EXCLUDED.review_period_days,
          lookback_days=EXCLUDED.lookback_days,
          minimum_available=EXCLUDED.minimum_available,
          safety_stock=EXCLUDED.safety_stock,
          enabled=EXCLUDED.enabled,
          updated_by=EXCLUDED.updated_by,
          updated_at=now()
        RETURNING id, location_id, variant_id, lead_time_days, review_period_days,
                  lookback_days, minimum_available, safety_stock, enabled, updated_at
    """), {
        "tenant_id": str(tenant_id), "location_id": str(body.location_id), "variant_id": str(body.variant_id),
        "lead_time_days": body.lead_time_days, "review_period_days": body.review_period_days,
        "lookback_days": body.lookback_days, "minimum_available": body.minimum_available,
        "safety_stock": body.safety_stock, "enabled": body.enabled, "actor_id": str(actor_id),
    }).mappings().one()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="inventory.replenishment_policy.upserted", target_type="inventory_replenishment_policy", target_id=row["id"])
    emit_event(db, tenant_id=tenant_id, event_type="inventory.replenishment_policy.updated.v1", aggregate_type="inventory_replenishment_policy", aggregate_id=row["id"], actor_user_id=actor_id, payload={
        "location_id": str(body.location_id), "variant_id": str(body.variant_id),
        "lead_time_days": body.lead_time_days, "review_period_days": body.review_period_days,
        "lookback_days": body.lookback_days, "enabled": body.enabled,
    })
    db.commit()
    return {
        "id": str(row["id"]), "location_id": str(row["location_id"]), "variant_id": str(row["variant_id"]),
        "lead_time_days": row["lead_time_days"], "review_period_days": row["review_period_days"],
        "lookback_days": row["lookback_days"], "minimum_available": str(row["minimum_available"]),
        "safety_stock": str(row["safety_stock"]), "enabled": row["enabled"], "updated_at": row["updated_at"],
    }


@router.get("/replenishment/recommendations")
def replenishment_recommendations(
    location_id: UUID | None = None,
    include_covered: bool = False,
    limit: int = Query(100, ge=1, le=500),
    ctx=Depends(require_permission("inventory.read")),
):
    """Explain reorder suggestions from completed net unit demand and scoped inventory facts.

    Suggestions are advisory only. This endpoint never creates a purchase order or stock movement.
    Units returned are assigned to the location where the return was received.
    """
    from ..inventory_intelligence import build_replenishment_metrics

    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    if location_id:
        ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=location_id)
    stmt = text("""
        SELECT p.id AS policy_id, p.location_id, p.variant_id, p.lead_time_days, p.review_period_days,
               p.lookback_days, p.minimum_available, p.safety_stock,
               l.name AS location_name, pr.name AS product_name, pv.name AS variant_name, pv.sku,
               COALESCE(b.on_hand, 0) AS on_hand, COALESCE(b.reserved, 0) AS reserved,
               COALESCE(b.inbound, 0) AS inbound, COALESCE(b.average_cost, 0) AS average_cost,
               COALESCE(sold.units_sold, 0) AS units_sold,
               COALESCE(ret.units_returned, 0) AS units_returned
          FROM public.inventory_replenishment_policies p
          JOIN public.locations l ON l.tenant_id=p.tenant_id AND l.id=p.location_id
          JOIN public.product_variants pv ON pv.tenant_id=p.tenant_id AND pv.id=p.variant_id
          JOIN public.products pr ON pr.tenant_id=p.tenant_id AND pr.id=pv.product_id
          LEFT JOIN public.inventory_balances b
            ON b.tenant_id=p.tenant_id AND b.location_id=p.location_id AND b.variant_id=p.variant_id
          LEFT JOIN LATERAL (
            SELECT SUM(tl.quantity) AS units_sold
              FROM public.sales s
              JOIN public.business_transactions bt ON bt.tenant_id=s.tenant_id AND bt.id=s.transaction_id
              JOIN public.transaction_lines tl ON tl.tenant_id=bt.tenant_id AND tl.transaction_id=bt.id
             WHERE s.tenant_id=p.tenant_id AND s.location_id=p.location_id
               AND s.status='COMPLETED' AND bt.status='COMPLETED' AND bt.transaction_type='SALE'
               AND tl.line_type='PRODUCT' AND tl.product_variant_id=p.variant_id
               AND COALESCE(s.completed_at, s.created_at) >= now() - make_interval(days => p.lookback_days)
          ) sold ON true
          LEFT JOIN LATERAL (
            SELECT SUM(srl.quantity) AS units_returned
              FROM public.sale_return_lines srl
              JOIN public.sale_returns sr ON sr.tenant_id=srl.tenant_id AND sr.id=srl.return_id
              JOIN public.sales source_sale ON source_sale.tenant_id=sr.tenant_id AND source_sale.id=sr.sale_id
             WHERE sr.tenant_id=p.tenant_id AND sr.status='COMPLETED'
               AND COALESCE(sr.inventory_location_id, source_sale.location_id)=p.location_id
               AND srl.variant_id=p.variant_id
               AND COALESCE(sr.completed_at, sr.created_at) >= now() - make_interval(days => p.lookback_days)
          ) ret ON true
         WHERE p.tenant_id=:tenant_id AND p.enabled=true AND p.location_id IN :allowed_location_ids
           AND (:location_id IS NULL OR p.location_id=:location_id)
         ORDER BY l.name, pr.name, pv.sku
         LIMIT :limit
    """).bindparams(bindparam("allowed_location_ids", expanding=True))
    rows = db.execute(stmt, {
        "tenant_id": str(tenant_id), "allowed_location_ids": list(allowed_locations),
        "location_id": str(location_id) if location_id else None, "limit": limit,
    }).mappings().all()
    results = []
    for row in rows:
        metrics = build_replenishment_metrics(
            on_hand=row["on_hand"], reserved=row["reserved"], inbound=row["inbound"],
            units_sold=row["units_sold"], units_returned=row["units_returned"],
            lookback_days=int(row["lookback_days"]), lead_time_days=int(row["lead_time_days"]),
            review_period_days=int(row["review_period_days"]), safety_stock=row["safety_stock"],
            minimum_available=row["minimum_available"],
        )
        if not include_covered and metrics["reorder_quantity"] <= 0:
            continue
        results.append({
            "policy_id": str(row["policy_id"]), "location_id": str(row["location_id"]),
            "variant_id": str(row["variant_id"]), "location_name": row["location_name"],
            "product_name": row["product_name"], "variant_name": row["variant_name"], "sku": row["sku"],
            **{key: (str(value) if value is not None else None) if key not in {"lookback_days", "recommended_action", "reason_code"} else value
               for key, value in metrics.items()},
            "average_cost": str(row["average_cost"]),
            "estimated_reorder_value": str((metrics["reorder_quantity"] * Decimal(str(row["average_cost"]))).quantize(Decimal("0.000001"))),
            "currency_note": "Valuation uses current average cost as an estimate, not a supplier quote.",
            "methodology": "Completed SALE product units minus completed return units received at this location (or the original sale location when no return location was recorded), divided by the policy lookback days. Target = max(minimum available, safety stock + daily demand × (lead time + review period)); reserved stock and inbound are accounted for separately.",
        })
    return {"source": "posted_transactions_and_inventory_balances", "advisory_only": True, "count": len(results), "items": results}


@router.get("/movement-health")
def inventory_movement_health(
    location_id: UUID | None = None,
    limit: int = Query(200, ge=1, le=500),
    ctx=Depends(require_permission("inventory.read")),
):
    """Show stockout and low-movement risks using completed sales and returns.

    This is an operational exception view, not a demand forecast. “No sale” means no
    completed sale is present in LEXA's available history for that tenant/location/SKU.
    """
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    if location_id:
        ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=location_id)

    stmt = text(r"""
      WITH scoped_locations AS (
        SELECT id FROM public.locations
         WHERE tenant_id=:tenant_id AND id IN :allowed_location_ids
           AND (:location_id IS NULL OR id=:location_id)
      ), stock_keys AS (
        SELECT b.tenant_id,b.location_id,b.variant_id FROM public.inventory_balances b
         WHERE b.tenant_id=:tenant_id AND b.location_id IN (SELECT id FROM scoped_locations)
        UNION
        SELECT p.tenant_id,p.location_id,p.variant_id FROM public.inventory_replenishment_policies p
         WHERE p.tenant_id=:tenant_id AND p.enabled=true AND p.location_id IN (SELECT id FROM scoped_locations)
      ), sales_activity AS (
        SELECT s.tenant_id,s.location_id,tl.product_variant_id AS variant_id,
               MAX(COALESCE(s.completed_at,s.created_at)) AS last_sale_at,
               COALESCE(SUM(tl.quantity) FILTER (
                 WHERE COALESCE(s.completed_at,s.created_at) >= now()-interval '30 days'),0) AS units_sold_30d,
               COALESCE(SUM(tl.quantity) FILTER (
                 WHERE COALESCE(s.completed_at,s.created_at) >= now()-interval '90 days'),0) AS units_sold_90d
          FROM public.sales s
          JOIN public.business_transactions bt ON bt.tenant_id=s.tenant_id AND bt.id=s.transaction_id
          JOIN public.transaction_lines tl ON tl.tenant_id=bt.tenant_id AND tl.transaction_id=bt.id
         WHERE s.tenant_id=:tenant_id AND s.status='COMPLETED'
           AND bt.status='COMPLETED' AND bt.transaction_type='SALE'
           AND tl.line_type='PRODUCT' AND tl.product_variant_id IS NOT NULL
         GROUP BY s.tenant_id,s.location_id,tl.product_variant_id
      ), returns_activity AS (
        SELECT sr.tenant_id,COALESCE(sr.inventory_location_id,source_sale.location_id) AS location_id,
               srl.variant_id,
               COALESCE(SUM(srl.quantity) FILTER (
                 WHERE COALESCE(sr.completed_at,sr.created_at) >= now()-interval '30 days'),0) AS units_returned_30d,
               COALESCE(SUM(srl.quantity) FILTER (
                 WHERE COALESCE(sr.completed_at,sr.created_at) >= now()-interval '90 days'),0) AS units_returned_90d
          FROM public.sale_returns sr
          JOIN public.sales source_sale ON source_sale.tenant_id=sr.tenant_id AND source_sale.id=sr.sale_id
          JOIN public.sale_return_lines srl ON srl.tenant_id=sr.tenant_id AND srl.return_id=sr.id
         WHERE sr.tenant_id=:tenant_id AND sr.status='COMPLETED'
         GROUP BY sr.tenant_id,COALESCE(sr.inventory_location_id,source_sale.location_id),srl.variant_id
      )
      SELECT k.location_id,l.name AS location_name,k.variant_id,pr.name AS product_name,
             pv.name AS variant_name,pv.sku,COALESCE(b.on_hand,0) AS on_hand,
             COALESCE(b.reserved,0) AS reserved,
             COALESCE(b.on_hand,0)-COALESCE(b.reserved,0) AS available,
             COALESCE(b.inbound,0) AS inbound,COALESCE(b.stock_value,0) AS stock_value,
             sa.last_sale_at,
             CASE WHEN sa.last_sale_at IS NULL THEN NULL
                  ELSE CURRENT_DATE-sa.last_sale_at::date END AS days_since_last_sale,
             COALESCE(sa.units_sold_30d,0) AS units_sold_30d,
             COALESCE(ra.units_returned_30d,0) AS units_returned_30d,
             GREATEST(COALESCE(sa.units_sold_30d,0)-COALESCE(ra.units_returned_30d,0),0) AS net_units_sold_30d,
             COALESCE(sa.units_sold_90d,0) AS units_sold_90d,
             COALESCE(ra.units_returned_90d,0) AS units_returned_90d,
             GREATEST(COALESCE(sa.units_sold_90d,0)-COALESCE(ra.units_returned_90d,0),0) AS net_units_sold_90d,
             p.minimum_available,
             CASE
               WHEN COALESCE(b.on_hand,0)-COALESCE(b.reserved,0) <= 0
                    AND GREATEST(COALESCE(sa.units_sold_90d,0)-COALESCE(ra.units_returned_90d,0),0)>0
                 THEN 'OUT_OF_STOCK_WITH_RECENT_DEMAND'
               WHEN COALESCE(b.on_hand,0)-COALESCE(b.reserved,0) <= 0 THEN 'OUT_OF_STOCK'
               WHEN p.id IS NOT NULL AND COALESCE(b.on_hand,0)-COALESCE(b.reserved,0) <= p.minimum_available
                 THEN 'AT_OR_BELOW_CONFIGURED_MINIMUM'
               WHEN sa.last_sale_at IS NULL THEN 'NO_COMPLETED_SALE_HISTORY'
               WHEN sa.last_sale_at < now()-interval '90 days' THEN 'NO_SALE_90D'
               WHEN sa.last_sale_at < now()-interval '60 days' THEN 'NO_SALE_60D'
               WHEN sa.last_sale_at < now()-interval '30 days' THEN 'NO_SALE_30D'
               ELSE 'ACTIVE'
             END AS health_status
        FROM stock_keys k
        JOIN scoped_locations sl ON sl.id=k.location_id
        JOIN public.locations l ON l.tenant_id=k.tenant_id AND l.id=k.location_id
        JOIN public.product_variants pv ON pv.tenant_id=k.tenant_id AND pv.id=k.variant_id
        JOIN public.products pr ON pr.tenant_id=pv.tenant_id AND pr.id=pv.product_id
        LEFT JOIN public.inventory_balances b ON b.tenant_id=k.tenant_id AND b.location_id=k.location_id AND b.variant_id=k.variant_id
        LEFT JOIN sales_activity sa ON sa.tenant_id=k.tenant_id AND sa.location_id=k.location_id AND sa.variant_id=k.variant_id
        LEFT JOIN returns_activity ra ON ra.tenant_id=k.tenant_id AND ra.location_id=k.location_id AND ra.variant_id=k.variant_id
        LEFT JOIN public.inventory_replenishment_policies p
          ON p.tenant_id=k.tenant_id AND p.location_id=k.location_id AND p.variant_id=k.variant_id AND p.enabled=true
       WHERE k.tenant_id=:tenant_id
       ORDER BY CASE
         WHEN COALESCE(b.on_hand,0)-COALESCE(b.reserved,0)<=0 AND COALESCE(sa.units_sold_90d,0)>0 THEN 0
         WHEN COALESCE(b.on_hand,0)-COALESCE(b.reserved,0)<=0 THEN 1
         WHEN p.id IS NOT NULL AND COALESCE(b.on_hand,0)-COALESCE(b.reserved,0)<=p.minimum_available THEN 2
         WHEN sa.last_sale_at IS NULL THEN 3
         WHEN sa.last_sale_at < now()-interval '90 days' THEN 4
         WHEN sa.last_sale_at < now()-interval '60 days' THEN 5
         WHEN sa.last_sale_at < now()-interval '30 days' THEN 6 ELSE 7 END,
         COALESCE(CURRENT_DATE-sa.last_sale_at::date,-1) DESC,
         COALESCE(b.stock_value,0) DESC,l.name,pr.name,pv.sku
       LIMIT :limit
    """).bindparams(bindparam("allowed_location_ids", expanding=True))
    rows = db.execute(stmt, {
        "tenant_id": str(tenant_id), "allowed_location_ids": list(allowed_locations),
        "location_id": str(location_id) if location_id else None, "limit": limit,
    }).mappings().all()
    return {
        "source": "completed_sales_returns_and_inventory_balances",
        "counts_as_completed_sale_only": True,
        "count": len(rows),
        "items": [{
            **{key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()},
            "currency_note": "Stock value is current cost valuation; units and movement recency are operational indicators, not a profitability measure.",
        } for row in rows],
    }


@router.get("/ageing")
def inventory_ageing(
    location_id: UUID | None = None,
    limit: int = Query(200, ge=1, le=500),
    ctx=Depends(require_permission("inventory.read")),
):
    """Return ledger-derived remaining-stock age signals for accessible locations.

    Positive opening/count-correction/transfer-in quantities have unknown provenance and
    are reported separately. The bucket allocator consumes those unknown-age quantities
    first as an explicitly analytical convention; it is not an accounting FIFO valuation.
    """
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    if location_id:
        ensure_location_access(db, tenant_id=tenant_id, user_id=actor_id, location_id=location_id)

    stmt = text(r"""
      WITH ledger AS (
        SELECT t.tenant_id, t.location_id, t.variant_id, t.id, t.occurred_at,
               t.transaction_type, t.quantity_delta,
               CASE WHEN t.quantity_delta > 0 AND upper(t.transaction_type) IN
                    ('OPENING_BALANCE','OPENING_STOCK','ADJUSTMENT','COUNT_CORRECTION',
                     'COUNT_RECONCILIATION','STOCK_COUNT_ADJUSTMENT','STOCK_COUNT_VARIANCE',
                     'TRANSFER_IN','LEGACY_RECONCILIATION')
                    THEN t.quantity_delta ELSE 0::numeric END AS unknown_in,
               CASE WHEN t.quantity_delta > 0 AND upper(t.transaction_type) NOT IN
                    ('OPENING_BALANCE','OPENING_STOCK','ADJUSTMENT','COUNT_CORRECTION',
                     'COUNT_RECONCILIATION','STOCK_COUNT_ADJUSTMENT','STOCK_COUNT_VARIANCE',
                     'TRANSFER_IN','LEGACY_RECONCILIATION')
                    THEN t.quantity_delta ELSE 0::numeric END AS traceable_in,
               CASE WHEN t.quantity_delta < 0 THEN -t.quantity_delta ELSE 0::numeric END AS outflow
          FROM public.inventory_transactions t
         WHERE t.tenant_id=:tenant_id AND t.location_id IN :allowed_location_ids
           AND (:location_id IS NULL OR t.location_id=:location_id)
      ), totals AS (
        SELECT tenant_id, location_id, variant_id,
               SUM(quantity_delta) AS ledger_quantity,
               SUM(unknown_in) AS unknown_in,
               SUM(traceable_in) AS traceable_in,
               SUM(outflow) AS total_outflow,
               MAX(occurred_at) AS last_movement_at
          FROM ledger GROUP BY tenant_id,location_id,variant_id
      ), inventory_keys AS (
        SELECT tenant_id,location_id,variant_id FROM totals
        UNION
        SELECT b.tenant_id,b.location_id,b.variant_id
          FROM public.inventory_balances b
         WHERE b.tenant_id=:tenant_id AND b.location_id IN :allowed_location_ids
           AND (:location_id IS NULL OR b.location_id=:location_id)
      ), layer_running AS (
        SELECT l.tenant_id,l.location_id,l.variant_id,l.id,l.occurred_at,l.traceable_in,
               SUM(l.traceable_in) OVER (
                 PARTITION BY l.tenant_id,l.location_id,l.variant_id
                 ORDER BY l.occurred_at,l.id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
               ) AS cumulative_in
          FROM ledger l WHERE l.traceable_in > 0
      ), remaining_layers AS (
        SELECT r.tenant_id,r.location_id,r.variant_id,r.occurred_at,
               GREATEST(r.cumulative_in-GREATEST(t.total_outflow-t.unknown_in,0),0)
               - GREATEST(r.cumulative_in-r.traceable_in-GREATEST(t.total_outflow-t.unknown_in,0),0)
                 AS remaining_quantity
          FROM layer_running r JOIN totals t USING (tenant_id,location_id,variant_id)
      ), age_aggregate AS (
        SELECT tenant_id,location_id,variant_id,
               SUM(remaining_quantity) AS traceable_remaining,
               SUM(remaining_quantity) FILTER (WHERE CURRENT_DATE-occurred_at::date >= 30) AS aged_over_30,
               SUM(remaining_quantity) FILTER (WHERE CURRENT_DATE-occurred_at::date >= 60) AS aged_over_60,
               SUM(remaining_quantity) FILTER (WHERE CURRENT_DATE-occurred_at::date >= 90) AS aged_over_90,
               MAX(CURRENT_DATE-occurred_at::date) FILTER (WHERE remaining_quantity > 0) AS oldest_remaining_age_days
          FROM remaining_layers GROUP BY tenant_id,location_id,variant_id
      )
      SELECT k.location_id,l.name AS location_name,k.variant_id,pv.sku,p.name AS product_name,pv.name AS variant_name,
             COALESCE(b.on_hand,0) AS on_hand,COALESCE(b.reserved,0) AS reserved,
             COALESCE(b.on_hand,0)-COALESCE(b.reserved,0) AS available,
             COALESCE(b.stock_value,0) AS stock_value,COALESCE(b.average_cost,0) AS average_cost,
             COALESCE(a.aged_over_30,0) AS aged_over_30,
             COALESCE(a.aged_over_60,0) AS aged_over_60,
             COALESCE(a.aged_over_90,0) AS aged_over_90,
             COALESCE(a.traceable_remaining,0) AS traceable_remaining,
             GREATEST(COALESCE(t.unknown_in,0)-COALESCE(t.total_outflow,0),0) AS unknown_age_quantity,
             a.oldest_remaining_age_days,t.last_movement_at,
             (ABS(COALESCE(t.ledger_quantity,0)-COALESCE(b.on_hand,0)) > 0.000001
               OR ABS(COALESCE(a.traceable_remaining,0)
                    + GREATEST(COALESCE(t.unknown_in,0)-COALESCE(t.total_outflow,0),0)
                    - COALESCE(b.on_hand,0)) > 0.000001) AS reconciliation_gap
        FROM inventory_keys k
        JOIN public.locations l ON l.tenant_id=k.tenant_id AND l.id=k.location_id
        JOIN public.product_variants pv ON pv.tenant_id=k.tenant_id AND pv.id=k.variant_id
        JOIN public.products p ON p.tenant_id=pv.tenant_id AND p.id=pv.product_id
        LEFT JOIN public.inventory_balances b ON b.tenant_id=k.tenant_id AND b.location_id=k.location_id AND b.variant_id=k.variant_id
        LEFT JOIN totals t USING (tenant_id,location_id,variant_id)
        LEFT JOIN age_aggregate a USING (tenant_id,location_id,variant_id)
       WHERE k.tenant_id=:tenant_id
       ORDER BY reconciliation_gap DESC, aged_over_90 DESC, aged_over_60 DESC, aged_over_30 DESC,
                l.name,p.name,pv.sku
       LIMIT :limit
    """).bindparams(bindparam("allowed_location_ids", expanding=True))
    rows = db.execute(stmt, {
        "tenant_id": str(tenant_id), "allowed_location_ids": list(allowed_locations),
        "location_id": str(location_id) if location_id else None, "limit": limit,
    }).mappings().all()
    return {
        "source": "inventory_ledger_and_balance_projection",
        "age_method": "Unknown-provenance receipts are kept outside dated age bands and consumed first for this advisory age estimate. Traceable remaining positive ledger layers use oldest-first depletion. This is not batch/serial tracking or FIFO accounting valuation.",
        "count": len(rows),
        "items": [
            {**{key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()},
             "age_status": "RECONCILIATION_GAP" if row["reconciliation_gap"] else ("UNKNOWN_AGE_PRESENT" if Decimal(str(row["unknown_age_quantity"])) > 0 else "TRACEABLE"),
             "currency_note": "Stock value is the current ledger balance valuation; age bands are quantities, not a separate valuation method."}
            for row in rows
        ],
    }


@router.post("/rebuild", response_model=dict)
def rebuild_inventory_balances(ctx=Depends(require_permission("inventory.rebuild"))):
    """Replay the immutable ledger and rebuild materialized on-hand/WAC projections."""
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor)
    rows = list(db.scalars(select(InventoryTransaction).where(InventoryTransaction.tenant_id == tenant_id).order_by(InventoryTransaction.location_id, InventoryTransaction.variant_id, InventoryTransaction.occurred_at, InventoryTransaction.id)))
    state: dict[tuple[UUID, UUID], tuple[Decimal, Decimal]] = {}
    for tx in rows:
        key = (tx.location_id, tx.variant_id)
        old_qty, old_avg = state.get(key, (ZERO, ZERO))
        delta = q(tx.quantity_delta)
        if delta > 0:
            avg = weighted_average_cost(old_qty, old_avg, delta, q(tx.unit_cost)) if old_qty > 0 else q(tx.unit_cost)
        else:
            avg = old_avg
        new_qty = q(old_qty + delta)
        if new_qty < 0:
            raise HTTPException(409, f"Ledger replay would create negative stock for {tx.variant_id}")
        state[key] = (new_qty, avg)

    rebuilt = 0
    for (location_id, variant_id), (on_hand, average_cost) in state.items():
        balance = get_or_create_balance(db, tenant_id, location_id, variant_id)
        balance.on_hand = on_hand
        balance.average_cost = average_cost
        balance.stock_value = q(on_hand * average_cost)
        balance.updated_at = now()
        rebuilt += 1
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="inventory.balances.rebuilt", target_type="inventory", target_id=None)
    emit_event(db, tenant_id=tenant_id, event_type="inventory.balances.rebuilt.v1", aggregate_type="inventory", aggregate_id=tenant_id, actor_user_id=actor, payload={"rebuilt": rebuilt})
    db.commit()
    return {"status": "ok", "rebuilt": rebuilt}

@router.get("/integrity")
def inventory_integrity(ctx=Depends(require_permission("inventory.read"))):
    """Read-only consistency check: every materialized balance must equal ledger quantity sum."""
    db, actor_id, tenant_id, _ = ctx
    allowed_locations = accessible_location_ids(db, tenant_id=tenant_id, user_id=actor_id)
    rows = db.execute(
        select(
            InventoryBalance.location_id,
            InventoryBalance.variant_id,
            InventoryBalance.on_hand,
            func.coalesce(func.sum(InventoryTransaction.quantity_delta), 0).label("ledger_quantity"),
        ).outerjoin(
            InventoryTransaction,
            (InventoryTransaction.tenant_id == InventoryBalance.tenant_id)
            & (InventoryTransaction.location_id == InventoryBalance.location_id)
            & (InventoryTransaction.variant_id == InventoryBalance.variant_id),
        ).where(InventoryBalance.tenant_id == tenant_id, InventoryBalance.location_id.in_(allowed_locations))
        .group_by(InventoryBalance.location_id, InventoryBalance.variant_id, InventoryBalance.on_hand)
    ).all()
    mismatches = []
    for row in rows:
        if q(row.on_hand) != q(row.ledger_quantity):
            mismatches.append({"location_id": row.location_id, "variant_id": row.variant_id, "balance_on_hand": q(row.on_hand), "ledger_quantity": q(row.ledger_quantity)})
    return {"status": "ok" if not mismatches else "mismatch", "checked": len(rows), "mismatches": mismatches}
