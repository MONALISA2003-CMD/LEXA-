"""Catalog domain persistence helpers and transactional audit/event primitives."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .catalog_rules import CatalogValidation, normalize_code, normalize_text, request_hash, validate_minimum_quantity, validate_price
from .models import AuditLog, IdempotencyRecord, OutboxEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def write_audit(db: Session, *, tenant_id: UUID, actor_user_id: UUID | None, action: str,
                target_type: str, target_id: UUID, outcome: str = "SUCCESS",
                correlation_id: str | None = None) -> AuditLog:
    row = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        correlation_id=correlation_id,
    )
    db.add(row)
    return row


def emit_event(db: Session, *, tenant_id: UUID, event_type: str, aggregate_type: str,
               aggregate_id: UUID, payload: dict[str, Any], actor_user_id: UUID | None = None,
               correlation_id: str | None = None) -> OutboxEvent:
    parsed_correlation_id = None
    if correlation_id:
        try:
            parsed_correlation_id = UUID(correlation_id)
        except (ValueError, TypeError):
            parsed_correlation_id = None
    event = OutboxEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_version=1,
        occurred_at=utc_now(),
        payload=payload,
        actor_id=actor_user_id,
        correlation_id=parsed_correlation_id,
    )
    db.add(event)
    return event



def begin_idempotency(db: Session, *, tenant_id: UUID, operation_type: str, key: str | None, payload: Any):
    if not key:
        return None, None
    key = key.strip()
    if not key or len(key) > 200:
        raise CatalogValidation("Invalid Idempotency-Key")
    digest = request_hash(payload)
    stmt = insert(IdempotencyRecord).values(
        tenant_id=tenant_id, idempotency_key=key, operation_type=operation_type, request_hash=digest,
    ).on_conflict_do_nothing(index_elements=["tenant_id", "idempotency_key", "operation_type"])
    db.execute(stmt)
    row = db.scalar(select(IdempotencyRecord).where(
        IdempotencyRecord.tenant_id == tenant_id,
        IdempotencyRecord.idempotency_key == key,
        IdempotencyRecord.operation_type == operation_type,
    ))
    if not row:
        raise CatalogValidation("Unable to establish idempotency record")
    if row.request_hash != digest:
        raise CatalogValidation("Idempotency-Key was already used with a different request")
    if row.response_status is not None:
        return row, (row.response_status, row.response_body or {})
    return row, None


def finish_idempotency(db: Session, row: IdempotencyRecord | None, *, status_code: int, response_body: dict[str, Any], resource_type: str, resource_id: UUID):
    if row is None:
        return
    row.response_status = status_code
    row.response_body = response_body
    row.resource_type = resource_type
    row.resource_id = resource_id
