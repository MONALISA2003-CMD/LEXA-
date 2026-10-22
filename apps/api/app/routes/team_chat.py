from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

from ..branch_access import ensure_branch_access
from ..catalog import begin_idempotency, emit_event, finish_idempotency, write_audit
from ..dependencies import require_permission

router = APIRouter(prefix="/team-chat", tags=["team-chat"])
_ALLOWED_CONTEXTS = {"SALE", "CUSTOMER", "PURCHASE_ORDER", "PRODUCT", "INVENTORY"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationCreate(Strict):
    title: str = Field(min_length=1, max_length=160)
    branch_id: UUID | None = None
    context_type: str | None = None
    context_id: UUID | None = None

    @model_validator(mode="after")
    def validate_context(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Conversation title cannot be blank")
        if self.context_type is not None:
            self.context_type = self.context_type.upper().strip()
            if self.context_type not in _ALLOWED_CONTEXTS:
                raise ValueError("Choose a supported business record type")
        if (self.context_type is None) != (self.context_id is None):
            raise ValueError("A linked business record needs both its type and ID")
        return self


class MessageCreate(Strict):
    body: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def normalize_body(self):
        self.body = self.body.strip()
        if not self.body:
            raise ValueError("Message cannot be blank")
        return self


def _out(row: Any) -> dict[str, Any]:
    result = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    for key, value in tuple(result.items()):
        if isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


def _accessible_conversation(db, tenant_id: UUID, user_id: UUID, conversation_id: UUID):
    # RLS and the explicit branch check work together: tenant isolation is always
    # enforced in PostgreSQL, while this check produces a consistent 403 for the UI.
    row = db.execute(text("""
        SELECT id, tenant_id, branch_id, title
        FROM team_conversations
        WHERE tenant_id=:tenant_id AND id=:conversation_id
          AND (branch_id IS NULL OR public.lexa_can_access_branch(branch_id))
    """), {"tenant_id": str(tenant_id), "conversation_id": str(conversation_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation was not found in this workspace")
    if row["branch_id"] is not None:
        ensure_branch_access(db, tenant_id=tenant_id, user_id=user_id, branch_id=row["branch_id"])
    return row


@router.get("/conversations")
def list_conversations(limit: int = Query(default=100, ge=1, le=200), ctx=Depends(require_permission("team_chat.read"))):
    db, user_id, tenant_id, _ = ctx
    rows = db.execute(text("""
        SELECT c.id, c.branch_id, b.name AS branch_name, c.title, c.context_type, c.context_id,
               c.created_by_user_id, COALESCE(creator.display_name, 'Team member') AS created_by_name,
               c.created_at, c.updated_at, c.last_message_at,
               latest.body AS latest_message, latest.sender_user_id AS latest_sender_user_id,
               latest.sender_name AS latest_sender_name,
               COALESCE((
                   SELECT count(*) FROM team_messages unread
                   LEFT JOIN team_conversation_reads reads
                     ON reads.tenant_id=unread.tenant_id
                    AND reads.conversation_id=unread.conversation_id
                    AND reads.reader_user_id=:user_id
                   WHERE unread.tenant_id=c.tenant_id AND unread.conversation_id=c.id
                     AND unread.sender_user_id<>:user_id
                     AND unread.created_at>COALESCE(reads.last_read_at, 'epoch'::timestamptz)
               ),0) AS unread_count
        FROM team_conversations c
        LEFT JOIN branches b ON b.tenant_id=c.tenant_id AND b.id=c.branch_id
        LEFT JOIN users creator ON creator.id=c.created_by_user_id
        LEFT JOIN LATERAL (
            SELECT m.body,m.sender_user_id,COALESCE(u.display_name,'Team member') AS sender_name
            FROM team_messages m LEFT JOIN users u ON u.id=m.sender_user_id
            WHERE m.tenant_id=c.tenant_id AND m.conversation_id=c.id
            ORDER BY m.created_at DESC,m.id DESC LIMIT 1
        ) latest ON true
        WHERE c.tenant_id=:tenant_id
          AND (c.branch_id IS NULL OR public.lexa_can_access_branch(c.branch_id))
        ORDER BY c.last_message_at DESC NULLS LAST,c.created_at DESC
        LIMIT :limit
    """), {"tenant_id": str(tenant_id), "user_id": str(user_id), "limit": limit}).mappings().all()
    return [_out(row) for row in rows]


@router.post("/conversations", status_code=201)
def create_conversation(
    body: ConversationCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
    ctx=Depends(require_permission("team_chat.send")),
):
    db, actor_id, tenant_id, _ = ctx
    payload = body.model_dump(mode="json")
    try:
        idem, cached = begin_idempotency(db, tenant_id=tenant_id, operation_type="team_chat.conversation.create", key=idempotency_key, payload=payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The conversation request could not be verified") from exc
    if cached:
        _, result = cached
        return result
    if body.branch_id:
        ensure_branch_access(db, tenant_id=tenant_id, user_id=actor_id, branch_id=body.branch_id)
    row = db.execute(text("""
        INSERT INTO team_conversations(tenant_id,branch_id,title,context_type,context_id,created_by_user_id)
        VALUES(:tenant_id,:branch_id,:title,:context_type,:context_id,:actor_id)
        RETURNING id,tenant_id,branch_id,title,context_type,context_id,created_by_user_id,created_at,updated_at,last_message_at
    """), {
        "tenant_id": str(tenant_id), "branch_id": str(body.branch_id) if body.branch_id else None,
        "title": body.title, "context_type": body.context_type,
        "context_id": str(body.context_id) if body.context_id else None, "actor_id": str(actor_id),
    }).mappings().one()
    result = _out(row)
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="team_chat.conversation.created", target_type="team_conversation", target_id=row["id"], correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, actor_user_id=actor_id, event_type="TEAM_CONVERSATION_CREATED", aggregate_type="team_conversation", aggregate_id=row["id"], payload={"branch_id": str(body.branch_id) if body.branch_id else None}, correlation_id=request_id)
    finish_idempotency(db, idem, status_code=201, response_body=result, resource_type="team_conversation", resource_id=row["id"])
    db.commit()
    return result


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: UUID, limit: int = Query(default=100, ge=1, le=200), ctx=Depends(require_permission("team_chat.read"))):
    db, user_id, tenant_id, _ = ctx
    _accessible_conversation(db, tenant_id, user_id, conversation_id)
    rows = db.execute(text("""
        SELECT * FROM (
          SELECT m.id,m.conversation_id,m.sender_user_id,COALESCE(u.display_name,'Team member') AS sender_name,
                 m.body,m.created_at,(m.sender_user_id=:user_id) AS is_mine
          FROM team_messages m LEFT JOIN users u ON u.id=m.sender_user_id
          WHERE m.tenant_id=:tenant_id AND m.conversation_id=:conversation_id
          ORDER BY m.created_at DESC,m.id DESC LIMIT :limit
        ) recent ORDER BY created_at ASC,id ASC
    """), {"tenant_id": str(tenant_id), "conversation_id": str(conversation_id), "user_id": str(user_id), "limit": limit}).mappings().all()
    return [_out(row) for row in rows]


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def send_message(
    conversation_id: UUID, body: MessageCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
    ctx=Depends(require_permission("team_chat.send")),
):
    db, actor_id, tenant_id, _ = ctx
    conversation = _accessible_conversation(db, tenant_id, actor_id, conversation_id)
    payload = {"conversation_id": str(conversation_id), **body.model_dump(mode="json")}
    try:
        idem, cached = begin_idempotency(db, tenant_id=tenant_id, operation_type="team_chat.message.send", key=idempotency_key, payload=payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The message request could not be verified") from exc
    if cached:
        _, result = cached
        return result
    row = db.execute(text("""
        INSERT INTO team_messages(tenant_id,conversation_id,sender_user_id,body)
        VALUES(:tenant_id,:conversation_id,:sender_user_id,:body)
        RETURNING id,tenant_id,conversation_id,sender_user_id,body,created_at
    """), {"tenant_id": str(tenant_id), "conversation_id": str(conversation_id), "sender_user_id": str(actor_id), "body": body.body}).mappings().one()
    db.execute(text("UPDATE team_conversations SET updated_at=now(),last_message_at=now() WHERE tenant_id=:tenant_id AND id=:conversation_id"), {"tenant_id": str(tenant_id), "conversation_id": str(conversation_id)})
    result = {**_out(row), "sender_name": db.execute(text("SELECT COALESCE(display_name,'Team member') FROM users WHERE id=:user_id"), {"user_id": str(actor_id)}).scalar_one(), "is_mine": True}
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="team_chat.message.sent", target_type="team_message", target_id=row["id"], correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, actor_user_id=actor_id, event_type="TEAM_MESSAGE_SENT", aggregate_type="team_conversation", aggregate_id=conversation_id, payload={"message_id": str(row["id"]), "branch_id": str(conversation["branch_id"]) if conversation["branch_id"] else None}, correlation_id=request_id)
    finish_idempotency(db, idem, status_code=201, response_body=result, resource_type="team_message", resource_id=row["id"])
    db.commit()
    return result


@router.post("/conversations/{conversation_id}/read")
def mark_read(conversation_id: UUID, ctx=Depends(require_permission("team_chat.read"))):
    db, user_id, tenant_id, _ = ctx
    _accessible_conversation(db, tenant_id, user_id, conversation_id)
    db.execute(text("""
      INSERT INTO team_conversation_reads(tenant_id,conversation_id,reader_user_id,last_read_at,updated_at)
      VALUES(:tenant_id,:conversation_id,:user_id,now(),now())
      ON CONFLICT(tenant_id,conversation_id,reader_user_id)
      DO UPDATE SET last_read_at=GREATEST(team_conversation_reads.last_read_at,EXCLUDED.last_read_at),updated_at=now()
    """), {"tenant_id": str(tenant_id), "conversation_id": str(conversation_id), "user_id": str(user_id)})
    db.commit()
    return {"conversation_id": str(conversation_id), "read_at": datetime.now(timezone.utc).isoformat()}
