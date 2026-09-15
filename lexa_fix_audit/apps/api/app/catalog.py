"""Catalog domain persistence helpers and transactional audit/event primitives."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from .catalog_rules import CatalogValidation, normalize_code, normalize_text, validate_minimum_quantity, validate_price
from .models import AuditLog, OutboxEvent


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
    event = OutboxEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_version=1,
        occurred_at=utc_now(),
        payload=payload,
        actor_user_id=actor_user_id,
        correlation_id=correlation_id,
    )
    db.add(event)
    return event
