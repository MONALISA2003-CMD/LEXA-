"""Inventory domain: immutable ledger, rebuildable balances and stateful commands."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .catalog import emit_event, write_audit
from .models import (
    IdempotencyKey, InventoryAdjustment, InventoryAdjustmentLine, InventoryBalance,
    InventoryTransaction, InventoryTransfer, InventoryTransferLine, Location,
    Product, ProductVariant, StockCount, StockCountLine,
)

ZERO = Decimal("0")
SCALE = Decimal("0.000001")


def now() -> datetime:
    return datetime.now(timezone.utc)


def q(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(SCALE, rounding=ROUND_HALF_UP)


def weighted_average_cost(old_quantity: Decimal, old_average: Decimal, inbound_quantity: Decimal, inbound_unit_cost: Decimal) -> Decimal:
    """Deterministically calculate the v1 location weighted-average cost."""
    old_quantity, old_average = q(old_quantity), q(old_average)
    inbound_quantity, inbound_unit_cost = q(inbound_quantity), q(inbound_unit_cost)
    if inbound_quantity <= 0:
        raise HTTPException(422, "Inbound quantity must be positive")
    if inbound_unit_cost < 0:
        raise HTTPException(422, "Inbound unit cost cannot be negative")
    total_quantity = old_quantity + inbound_quantity
    if old_quantity <= 0:
        return inbound_unit_cost
    return q(((old_quantity * old_average) + (inbound_quantity * inbound_unit_cost)) / total_quantity)


def request_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def idempotent_start(db: Session, tenant_id: UUID, operation: str, key: str | None, payload: Any):
    if not key:
        return None
    key = key.strip()
    if not key or len(key) > 200:
        raise HTTPException(400, "Invalid Idempotency-Key")
    digest = request_hash(payload)
    stmt = insert(IdempotencyKey).values(
        tenant_id=tenant_id, operation=operation, key=key, request_hash=digest,
        response_status=0, response_json={},
    ).on_conflict_do_nothing(index_elements=["tenant_id", "operation", "key"])
    db.execute(stmt)
    row = db.scalar(select(IdempotencyKey).where(
        IdempotencyKey.tenant_id == tenant_id,
        IdempotencyKey.operation == operation,
        IdempotencyKey.key == key,
    ))
    if not row:
        raise HTTPException(500, "Unable to establish idempotency record")
    if row.request_hash != digest:
        raise HTTPException(409, "Idempotency-Key was already used with a different request")
    if row.response_status:
        return row.response_status, row.response_json
    return row


def idempotent_finish(db: Session, row, status_code: int, response: dict[str, Any]):
    if isinstance(row, IdempotencyKey):
        row.response_status = status_code
        row.response_json = response


def tenant_location(db: Session, tenant_id: UUID, location_id: UUID) -> Location:
    row = db.scalar(select(Location).where(Location.id == location_id, Location.tenant_id == tenant_id, Location.status == "ACTIVE"))
    if not row:
        raise HTTPException(400, "Location does not belong to tenant or is inactive")
    return row


def tenant_variant(db: Session, tenant_id: UUID, variant_id: UUID) -> ProductVariant:
    row = db.scalar(select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None), ProductVariant.status == "ACTIVE"))
    if not row:
        raise HTTPException(400, "Variant does not belong to tenant or is inactive")
    product = db.scalar(select(Product).where(Product.id == row.product_id, Product.tenant_id == tenant_id, Product.deleted_at.is_(None), Product.status == "ACTIVE"))
    if not product:
        raise HTTPException(400, "Variant belongs to an inactive or archived product")
    return row


def get_or_create_balance(db: Session, tenant_id: UUID, location_id: UUID, variant_id: UUID) -> InventoryBalance:
    # The unique key is the concurrency boundary. PostgreSQL row locking happens after creation.
    stmt = insert(InventoryBalance).values(tenant_id=tenant_id, location_id=location_id, variant_id=variant_id).on_conflict_do_nothing(
        index_elements=["tenant_id", "location_id", "variant_id"]
    )
    db.execute(stmt)
    return db.scalar(select(InventoryBalance).where(
        InventoryBalance.tenant_id == tenant_id,
        InventoryBalance.location_id == location_id,
        InventoryBalance.variant_id == variant_id,
    ).with_for_update())


def post_ledger(
    db: Session, *, tenant_id: UUID, actor_user_id: UUID, location_id: UUID, variant_id: UUID,
    quantity_delta: Decimal, unit_cost: Decimal, transaction_type: str,
    reference_type: str, reference_id: UUID, metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None, source_transaction_id: UUID | None = None,
) -> InventoryTransaction:
    quantity_delta = q(quantity_delta); unit_cost = q(unit_cost)
    if quantity_delta == 0:
        raise HTTPException(422, "Inventory quantity cannot be zero")
    if unit_cost < 0:
        raise HTTPException(422, "Unit cost cannot be negative")
    if idempotency_key:
        existing = db.scalar(select(InventoryTransaction).where(
            InventoryTransaction.tenant_id == tenant_id,
            InventoryTransaction.idempotency_key == idempotency_key,
        ))
        if existing:
            return existing

    variant = tenant_variant(db, tenant_id, variant_id)
    if not variant.track_inventory:
        raise HTTPException(422, "This variant does not track inventory")
    balance = get_or_create_balance(db, tenant_id, location_id, variant_id)
    old_qty = q(balance.on_hand)
    old_avg = q(balance.average_cost)
    new_qty = old_qty + quantity_delta
    if new_qty < 0:
        raise HTTPException(409, "Insufficient available stock")

    if quantity_delta > 0:
        if unit_cost <= 0 and old_qty == 0:
            raise HTTPException(422, "A positive inventory receipt requires a unit cost when stock is zero")
        if old_qty > 0:
            new_avg = weighted_average_cost(old_qty, old_avg, quantity_delta, unit_cost)
        else:
            new_avg = unit_cost
    else:
        new_avg = old_avg

    balance.on_hand = new_qty
    balance.average_cost = new_avg
    balance.stock_value = q(new_qty * new_avg)
    balance.updated_at = now()
    tx = InventoryTransaction(
        tenant_id=tenant_id, location_id=location_id, variant_id=variant_id,
        transaction_type=transaction_type, quantity_delta=quantity_delta,
        unit_cost=unit_cost if quantity_delta > 0 else old_avg,
        total_cost=q(abs(quantity_delta) * (unit_cost if quantity_delta > 0 else old_avg)),
        balance_after=new_qty, reference_type=reference_type, reference_id=reference_id,
        source_transaction_id=source_transaction_id, idempotency_key=idempotency_key,
        actor_user_id=actor_user_id, occurred_at=now(), inventory_metadata=metadata or {},
    )
    db.add(tx)
    db.flush()
    return tx


def change_inbound(db: Session, tenant_id: UUID, location_id: UUID, variant_id: UUID, delta: Decimal):
    balance = get_or_create_balance(db, tenant_id, location_id, variant_id)
    new_value = q(balance.inbound) + q(delta)
    if new_value < 0:
        raise HTTPException(409, "Inbound quantity cannot become negative")
    balance.inbound = new_value
    balance.updated_at = now()


def serialize_balance(row: InventoryBalance) -> dict[str, Any]:
    available = q(row.on_hand) - q(row.reserved)
    return {
        "id": row.id, "tenant_id": row.tenant_id, "location_id": row.location_id,
        "variant_id": row.variant_id, "on_hand": q(row.on_hand), "reserved": q(row.reserved),
        "available": available, "inbound": q(row.inbound), "average_cost": q(row.average_cost),
        "stock_value": q(row.stock_value), "updated_at": row.updated_at,
    }
