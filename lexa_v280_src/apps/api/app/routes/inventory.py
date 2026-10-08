from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..catalog import emit_event, write_audit
from ..dependencies import require_permission
from ..inventory import (
    ZERO,
    change_inbound, get_or_create_balance, idempotent_finish, idempotent_start,
    now, post_ledger, q, serialize_balance, tenant_location, tenant_variant,
)
from ..models import (
    InventoryAdjustment, InventoryAdjustmentLine, InventoryBalance, InventoryTransaction,
    InventoryTransfer, InventoryTransferLine, Product, ProductVariant, StockCount, StockCountLine,
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
    db, _, tenant_id, _ = ctx
    stmt = select(InventoryBalance).where(InventoryBalance.tenant_id == tenant_id)
    if location_id: stmt = stmt.where(InventoryBalance.location_id == location_id)
    if variant_id: stmt = stmt.where(InventoryBalance.variant_id == variant_id)
    if q_search:
        like = f"%{q_search.strip()}%"
        stmt = stmt.join(ProductVariant, ProductVariant.id == InventoryBalance.variant_id).join(Product, Product.id == ProductVariant.product_id).where(
            Product.name.ilike(like) | ProductVariant.sku.ilike(like)
        )
    rows = list(db.scalars(stmt.order_by(InventoryBalance.updated_at.desc()).limit(limit)))
    return [serialize_balance(r) for r in rows]

@router.get("/ledger", response_model=list[LedgerOut])
def ledger(
    location_id: UUID | None = None, variant_id: UUID | None = None,
    transaction_type: str | None = None, limit: int = Query(100, ge=1, le=500),
    ctx=Depends(require_permission("inventory.read")),
):
    db, _, tenant_id, _ = ctx
    stmt = select(InventoryTransaction).where(InventoryTransaction.tenant_id == tenant_id)
    if location_id: stmt = stmt.where(InventoryTransaction.location_id == location_id)
    if variant_id: stmt = stmt.where(InventoryTransaction.variant_id == variant_id)
    if transaction_type: stmt = stmt.where(InventoryTransaction.transaction_type == transaction_type)
    return list(db.scalars(stmt.order_by(InventoryTransaction.occurred_at.desc(), InventoryTransaction.id.desc()).limit(limit)))

@router.get("/products/{variant_id}")
def product_inventory(variant_id: UUID, ctx=Depends(require_permission("inventory.read"))):
    db, _, tenant_id, _ = ctx
    tenant_variant(db, tenant_id, variant_id)
    balances = list(db.scalars(select(InventoryBalance).where(InventoryBalance.tenant_id == tenant_id, InventoryBalance.variant_id == variant_id).order_by(InventoryBalance.updated_at.desc())))
    recent = list(db.scalars(select(InventoryTransaction).where(InventoryTransaction.tenant_id == tenant_id, InventoryTransaction.variant_id == variant_id).order_by(InventoryTransaction.occurred_at.desc()).limit(25)))
    return {"balances": [serialize_balance(r) for r in balances], "ledger": recent}

@router.post("/adjustments")
def create_adjustment(body: AdjustmentIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("inventory.manage"))):
    db, actor, tenant_id, _ = ctx
    tenant_location(db, tenant_id, body.location_id)
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
    db, _, tenant_id, _ = ctx
    stmt = select(InventoryTransfer).where(InventoryTransfer.tenant_id == tenant_id)
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
    db, _, tenant_id, _ = ctx
    stmt = select(InventoryAdjustment).where(InventoryAdjustment.tenant_id == tenant_id)
    if status: stmt = stmt.where(InventoryAdjustment.status == status)
    rows = list(db.scalars(stmt.order_by(InventoryAdjustment.created_at.desc()).limit(limit)))
    result = []
    for row in rows:
        lines = list(db.scalars(select(InventoryAdjustmentLine).where(InventoryAdjustmentLine.adjustment_id == row.id, InventoryAdjustmentLine.tenant_id == tenant_id)))
        result.append({"id": row.id, "location_id": row.location_id, "reason_code": row.reason_code, "notes": row.notes, "status": row.status, "created_at": row.created_at, "lines": lines})
    return result

@router.get("/stock-counts")
def list_stock_counts(status: str | None = None, limit: int = Query(100, ge=1, le=500), ctx=Depends(require_permission("inventory.read"))):
    db, _, tenant_id, _ = ctx
    stmt = select(StockCount).where(StockCount.tenant_id == tenant_id)
    if status: stmt = stmt.where(StockCount.status == status)
    rows = list(db.scalars(stmt.order_by(StockCount.created_at.desc()).limit(limit)))
    result = []
    for row in rows:
        lines = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == row.id, StockCountLine.tenant_id == tenant_id)))
        result.append({"id": row.id, "location_id": row.location_id, "status": row.status, "scope_description": row.scope_description, "started_at": row.started_at, "created_at": row.created_at, "lines": lines})
    return result

@router.get("/stock-counts/{count_id}")
def get_stock_count(count_id: UUID, ctx=Depends(require_permission("inventory.read"))):
    db, _, tenant_id, _ = ctx
    row = db.scalar(select(StockCount).where(StockCount.id == count_id, StockCount.tenant_id == tenant_id))
    if not row: raise HTTPException(404, "Stock count not found")
    lines = list(db.scalars(select(StockCountLine).where(StockCountLine.stock_count_id == row.id, StockCountLine.tenant_id == tenant_id)))
    return {"id": row.id, "location_id": row.location_id, "status": row.status, "scope_description": row.scope_description, "started_at": row.started_at, "created_at": row.created_at, "lines": lines}



@router.post("/rebuild", response_model=dict)
def rebuild_inventory_balances(ctx=Depends(require_permission("inventory.rebuild"))):
    """Replay the immutable ledger and rebuild materialized on-hand/WAC projections."""
    db, actor, tenant_id, _ = ctx
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
    db, _, tenant_id, _ = ctx
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
        ).where(InventoryBalance.tenant_id == tenant_id)
        .group_by(InventoryBalance.location_id, InventoryBalance.variant_id, InventoryBalance.on_hand)
    ).all()
    mismatches = []
    for row in rows:
        if q(row.on_hand) != q(row.ledger_quantity):
            mismatches.append({"location_id": row.location_id, "variant_id": row.variant_id, "balance_on_hand": q(row.on_hand), "ledger_quantity": q(row.ledger_quantity)})
    return {"status": "ok" if not mismatches else "mismatch", "checked": len(rows), "mismatches": mismatches}
