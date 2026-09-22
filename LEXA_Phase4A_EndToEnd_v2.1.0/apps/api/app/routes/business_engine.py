from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalog import begin_idempotency, emit_event, finish_idempotency, write_audit
from ..dependencies import require_permission
from ..models import (
    Branch, BusinessCapability, BusinessConfiguration, BusinessProfile, BusinessTransaction, BusinessCase,
    Party, PartyRelationship, PartyRole, Payment, Product, ProductVariant, Resource, Service,
    Task, TransactionLine, TransactionStatusHistory, TransactionType, WorkflowDefinition,
    WorkflowInstance, WorkflowStep, WorkflowStepRun,
)

router = APIRouter(prefix="/business-engine", tags=["business-engine"])


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CapabilityPatch(BaseModel):
    enabled: bool
    configuration: dict[str, Any] = Field(default_factory=dict)


class ConfigPut(BaseModel):
    value: Any
    value_type: str = Field(default="JSON", max_length=30)


class PartyRelationshipCreate(BaseModel):
    from_party_id: UUID
    to_party_id: UUID
    relationship_type: str = Field(min_length=1, max_length=80)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransactionTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default="GENERAL", max_length=60)
    initial_status: str = Field(default="DRAFT", max_length=40)
    statuses: list[str] = Field(default_factory=lambda: ["DRAFT", "CONFIRMED", "COMPLETED", "CANCELLED"])
    transitions: dict[str, list[str]] = Field(default_factory=lambda: {"DRAFT": ["CONFIRMED", "CANCELLED"], "CONFIRMED": ["COMPLETED", "CANCELLED"]})
    configuration: dict[str, Any] = Field(default_factory=dict)


class TransactionLineCreate(BaseModel):
    line_type: str = Field(default="MISC", pattern=r"^(PRODUCT|SERVICE|MISC)$")
    product_variant_id: UUID | None = None
    service_id: UUID | None = None
    resource_id: UUID | None = None
    description: str | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransactionCreate(BaseModel):
    transaction_type: str = Field(min_length=1, max_length=80)
    reference: str = Field(min_length=1, max_length=120)
    party_id: UUID | None = None
    branch_id: UUID | None = None
    source_transaction_id: UUID | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    lines: list[TransactionLineCreate] = Field(default_factory=list)


class TransactionTransition(BaseModel):
    to_status: str = Field(min_length=1, max_length=40)
    reason: str | None = Field(default=None, max_length=500)


class WorkflowStepCreate(BaseModel):
    step_key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)
    step_type: str = Field(default="TASK", pattern=r"^(TASK|APPROVAL|ACTION|CONDITION|NOTIFICATION)$")
    position: int = Field(default=1, ge=1)
    configuration: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinitionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    trigger_event: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    steps: list[WorkflowStepCreate] = Field(min_length=1)


class WorkflowInstanceCreate(BaseModel):
    workflow_definition_id: UUID
    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: UUID
    context: dict[str, Any] = Field(default_factory=dict)


class ContextOut(BaseModel):
    entity_type: str
    entity_id: UUID
    primary: dict[str, Any]
    related: dict[str, list[dict[str, Any]]]
    evidence: list[dict[str, Any]]


def _json_model(row) -> dict[str, Any]:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def _audit_event(db: Session, *, tenant_id: UUID, actor_id: UUID, action: str, event_type: str,
                 aggregate_type: str, aggregate_id: UUID, payload: dict[str, Any], request_id: str | None = None):
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action=action, target_type=aggregate_type, target_id=aggregate_id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type=event_type, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload=payload, actor_user_id=actor_id, correlation_id=request_id)


def _tenant_party(db: Session, tenant_id: UUID, party_id: UUID | None) -> Party | None:
    if party_id is None:
        return None
    row = db.scalar(select(Party).where(Party.id == party_id, Party.tenant_id == tenant_id, Party.deleted_at.is_(None)))
    if not row:
        raise HTTPException(400, "Party does not belong to tenant")
    return row


def _tenant_branch(db: Session, tenant_id: UUID, branch_id: UUID | None) -> Branch | None:
    if branch_id is None:
        return None
    row = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.tenant_id == tenant_id, Branch.status == "ACTIVE"))
    if not row:
        raise HTTPException(400, "Branch does not belong to tenant")
    return row


def _default_currency(db: Session, tenant_id: UUID) -> str:
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id))
    return (profile.currency_code if profile else "UGX").upper()


@router.get("/capabilities")
def list_capabilities(ctx=Depends(require_permission("business.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.scalars(select(BusinessCapability).where(BusinessCapability.tenant_id == tenant_id).order_by(BusinessCapability.code)).all()
    return [_json_model(x) for x in rows]


@router.put("/capabilities/{code}")
def set_capability(code: str, body: CapabilityPatch, ctx=Depends(require_permission("business.manage"))):
    db, actor, tenant_id, _ = ctx
    code = code.strip().upper()
    row = db.scalar(select(BusinessCapability).where(BusinessCapability.tenant_id == tenant_id, BusinessCapability.code == code))
    if not row:
        row = BusinessCapability(tenant_id=tenant_id, code=code, name=code.replace("_", " ").title(), enabled=body.enabled, configuration=body.configuration)
        db.add(row)
    else:
        row.enabled = body.enabled
        row.configuration = body.configuration
        row.version += 1
    db.flush()
    _audit_event(db, tenant_id=tenant_id, actor_id=actor, action="business.capability.updated", event_type="BusinessCapabilityUpdated", aggregate_type="business_capability", aggregate_id=row.id, payload={"code": code, "enabled": row.enabled})
    db.commit(); db.refresh(row)
    return _json_model(row)


@router.get("/configuration")
def list_configuration(ctx=Depends(require_permission("business.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.scalars(select(BusinessConfiguration).where(BusinessConfiguration.tenant_id == tenant_id).order_by(BusinessConfiguration.config_key)).all()
    return [_json_model(x) for x in rows]


@router.put("/configuration/{key}")
def put_configuration(key: str, body: ConfigPut, ctx=Depends(require_permission("business.manage"))):
    db, actor, tenant_id, _ = ctx
    key = key.strip()
    if not key:
        raise HTTPException(422, "Configuration key is required")
    row = db.scalar(select(BusinessConfiguration).where(BusinessConfiguration.tenant_id == tenant_id, BusinessConfiguration.config_key == key))
    if not row:
        row = BusinessConfiguration(tenant_id=tenant_id, config_key=key, value_json=body.value, value_type=body.value_type.upper(), updated_by=actor)
        db.add(row)
    else:
        row.value_json = body.value; row.value_type = body.value_type.upper(); row.version += 1; row.updated_by = actor
    db.flush()
    _audit_event(db, tenant_id=tenant_id, actor_id=actor, action="business.configuration.updated", event_type="BusinessConfigurationUpdated", aggregate_type="business_configuration", aggregate_id=row.id, payload={"key": key, "version": row.version})
    db.commit(); db.refresh(row)
    return _json_model(row)


@router.get("/relationships", response_model=list[dict])
def list_relationships(party_id: UUID | None = None, ctx=Depends(require_permission("business.read"))):
    db, _, tenant_id, _ = ctx
    stmt = select(PartyRelationship).where(PartyRelationship.tenant_id == tenant_id, PartyRelationship.status == "ACTIVE")
    if party_id:
        stmt = stmt.where(or_(PartyRelationship.from_party_id == party_id, PartyRelationship.to_party_id == party_id))
    rows = db.scalars(stmt.order_by(desc(PartyRelationship.created_at)).limit(500)).all()
    out=[]
    for row in rows:
        a=db.get(Party,row.from_party_id); b=db.get(Party,row.to_party_id)
        out.append({**_json_model(row), "from_party_name": a.display_name if a else None, "to_party_name": b.display_name if b else None})
    return out


@router.post("/relationships", status_code=201)
def create_relationship(body: PartyRelationshipCreate, ctx=Depends(require_permission("business.manage"))):
    db, actor, tenant_id, session_id = ctx
    if body.from_party_id == body.to_party_id:
        raise HTTPException(422, "A party relationship cannot point to itself")
    _tenant_party(db, tenant_id, body.from_party_id); _tenant_party(db, tenant_id, body.to_party_id)
    if body.valid_from and body.valid_to and body.valid_to < body.valid_from:
        raise HTTPException(422, "valid_to must be after valid_from")
    row = PartyRelationship(tenant_id=tenant_id, from_party_id=body.from_party_id, to_party_id=body.to_party_id, relationship_type=body.relationship_type.strip().upper(), valid_from=body.valid_from, valid_to=body.valid_to, metadata_json=body.metadata)
    db.add(row); db.flush()
    _audit_event(db, tenant_id=tenant_id, actor_id=actor, action="business.relationship.created", event_type="PartyRelationshipCreated", aggregate_type="party_relationship", aggregate_id=row.id, payload={"relationship_type": row.relationship_type, "from_party_id": str(row.from_party_id), "to_party_id": str(row.to_party_id)})
    db.commit(); db.refresh(row)
    return {**_json_model(row), "session_id": str(session_id)}


@router.get("/transaction-types")
def list_transaction_types(ctx=Depends(require_permission("transactions.read"))):
    db, _, tenant_id, _ = ctx
    rows=db.scalars(select(TransactionType).where(TransactionType.tenant_id==tenant_id, TransactionType.active.is_(True)).order_by(TransactionType.category, TransactionType.code)).all()
    return [_json_model(x) for x in rows]


@router.post("/transaction-types", status_code=201)
def create_transaction_type(body: TransactionTypeCreate, ctx=Depends(require_permission("transactions.manage"))):
    db, actor, tenant_id, _ = ctx
    row=TransactionType(tenant_id=tenant_id, code=body.code.strip().upper(), name=body.name.strip(), category=body.category.strip().upper(), initial_status=body.initial_status.strip().upper(), statuses=[x.strip().upper() for x in body.statuses], transitions={k.strip().upper(): [v.strip().upper() for v in vals] for k, vals in body.transitions.items()}, configuration=body.configuration)
    db.add(row)
    try: db.flush()
    except IntegrityError as exc: db.rollback(); raise HTTPException(409, "Transaction type code already exists") from exc
    _audit_event(db, tenant_id=tenant_id, actor_id=actor, action="transactions.type.created", event_type="TransactionTypeCreated", aggregate_type="transaction_type", aggregate_id=row.id, payload={"code": row.code})
    db.commit(); db.refresh(row); return _json_model(row)


@router.post("/transactions", status_code=201)
def create_transaction(body: TransactionCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), ctx=Depends(require_permission("transactions.manage"))):
    db, actor, tenant_id, _ = ctx
    idem, replay = begin_idempotency(db, tenant_id=tenant_id, operation_type="business-engine.transaction.create", key=idempotency_key, payload=body.model_dump(mode="json"))
    if replay:
        return replay[1]
    _tenant_party(db, tenant_id, body.party_id); _tenant_branch(db, tenant_id, body.branch_id)
    source = None
    if body.source_transaction_id:
        source = db.scalar(select(BusinessTransaction).where(BusinessTransaction.id == body.source_transaction_id, BusinessTransaction.tenant_id == tenant_id))
        if not source: raise HTTPException(400, "Source transaction does not belong to tenant")
    tx_type = db.scalar(select(TransactionType).where(TransactionType.tenant_id == tenant_id, TransactionType.code == body.transaction_type.strip().upper(), TransactionType.active.is_(True)))
    initial_status = tx_type.initial_status if tx_type else "DRAFT"
    currency = (body.currency_code or _default_currency(db, tenant_id)).upper()
    line_total = Decimal("0")
    row = BusinessTransaction(tenant_id=tenant_id, transaction_type=body.transaction_type.strip().upper(), reference=body.reference.strip(), status=initial_status, party_id=body.party_id, branch_id=body.branch_id, source_transaction_id=body.source_transaction_id, currency_code=currency, occurred_at=body.occurred_at or datetime.now(timezone.utc), metadata_json=body.metadata)
    db.add(row); db.flush()
    for no, line in enumerate(body.lines, start=1):
        if line.line_type == "PRODUCT":
            if not line.product_variant_id or not db.scalar(select(ProductVariant.id).where(ProductVariant.id == line.product_variant_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None))): raise HTTPException(400, "Product variant does not belong to tenant")
            if line.service_id: raise HTTPException(422, "PRODUCT lines cannot include a service")
        elif line.line_type == "SERVICE":
            if not line.service_id or not db.scalar(select(Service.id).where(Service.id == line.service_id, Service.tenant_id == tenant_id, Service.status == "ACTIVE")): raise HTTPException(400, "Service does not belong to tenant")
            if line.product_variant_id: raise HTTPException(422, "SERVICE lines cannot include a product")
        elif line.product_variant_id or line.service_id:
            raise HTTPException(422, "MISC lines cannot include a product or service")
        if line.resource_id and not db.scalar(select(Resource.id).where(Resource.id == line.resource_id, Resource.tenant_id == tenant_id)):
            raise HTTPException(400, "Resource does not belong to tenant")
        if line.currency_code and line.currency_code.upper() != currency:
            raise HTTPException(422, "All transaction lines must use the transaction currency")
        total = line.quantity * line.unit_price
        line_total += total
        db.add(TransactionLine(tenant_id=tenant_id, transaction_id=row.id, line_no=no, line_type=line.line_type, product_variant_id=line.product_variant_id, service_id=line.service_id, resource_id=line.resource_id, description=line.description, quantity=line.quantity, unit_price=line.unit_price, line_total=total, currency_code=currency, metadata_json=line.metadata))
    row.total_amount = line_total
    db.add(TransactionStatusHistory(tenant_id=tenant_id, transaction_id=row.id, from_status=None, to_status=row.status, changed_by=actor, metadata_json={"reason":"created"}))
    _audit_event(db, tenant_id=tenant_id, actor_id=actor, action="transactions.created", event_type="BusinessTransactionCreated", aggregate_type="business_transaction", aggregate_id=row.id, payload={"reference":row.reference,"transaction_type":row.transaction_type,"status":row.status})
    finish_idempotency(db, idem, status_code=201, response_body={"id":str(row.id),"status":row.status,"reference":row.reference}, resource_type="business_transaction", resource_id=row.id)
    db.commit(); db.refresh(row)
    return _json_model(row) | {"lines": [_json_model(x) for x in db.scalars(select(TransactionLine).where(TransactionLine.transaction_id==row.id).order_by(TransactionLine.line_no)).all()]}


@router.get("/transactions")
def list_transactions(status: str | None = None, transaction_type: str | None = None, ctx=Depends(require_permission("transactions.read"))):
    db, _, tenant_id, _ = ctx
    stmt=select(BusinessTransaction).where(BusinessTransaction.tenant_id==tenant_id).order_by(desc(BusinessTransaction.occurred_at)).limit(500)
    if status: stmt=stmt.where(BusinessTransaction.status==status.strip().upper())
    if transaction_type: stmt=stmt.where(BusinessTransaction.transaction_type==transaction_type.strip().upper())
    rows=db.scalars(stmt).all()
    return [{**_json_model(x), "line_count": db.query(TransactionLine).filter(TransactionLine.transaction_id==x.id).count()} for x in rows]


@router.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: UUID, ctx=Depends(require_permission("transactions.read"))):
    db, _, tenant_id, _ = ctx
    row=db.scalar(select(BusinessTransaction).where(BusinessTransaction.id==transaction_id,BusinessTransaction.tenant_id==tenant_id))
    if not row: raise HTTPException(404,"Transaction not found")
    lines=db.scalars(select(TransactionLine).where(TransactionLine.transaction_id==transaction_id).order_by(TransactionLine.line_no)).all()
    history=db.scalars(select(TransactionStatusHistory).where(TransactionStatusHistory.transaction_id==transaction_id).order_by(desc(TransactionStatusHistory.changed_at))).all()
    payments=db.scalars(select(Payment).where(Payment.tenant_id==tenant_id, Payment.transaction_id==transaction_id).order_by(desc(Payment.paid_at))).all()
    return {**_json_model(row), "lines":[_json_model(x) for x in lines], "history":[_json_model(x) for x in history], "payments":[_json_model(x) for x in payments]}


@router.post("/transactions/{transaction_id}/transition")
def transition_transaction(transaction_id: UUID, body: TransactionTransition, ctx=Depends(require_permission("transactions.manage"))):
    db, actor, tenant_id, _ = ctx
    row=db.scalar(select(BusinessTransaction).where(BusinessTransaction.id==transaction_id,BusinessTransaction.tenant_id==tenant_id).with_for_update())
    if not row: raise HTTPException(404,"Transaction not found")
    target=body.to_status.strip().upper()
    if target == row.status: return _json_model(row)
    tx_type=db.scalar(select(TransactionType).where(TransactionType.tenant_id==tenant_id,TransactionType.code==row.transaction_type,TransactionType.active.is_(True)))
    transitions = tx_type.transitions if tx_type else {"DRAFT":["CONFIRMED","CANCELLED"],"CONFIRMED":["COMPLETED","CANCELLED"]}
    allowed=[str(x).upper() for x in transitions.get(row.status, [])]
    if target not in allowed: raise HTTPException(409, f"Transition {row.status} -> {target} is not allowed")
    old=row.status; row.status=target
    if target in {"COMPLETED","CANCELLED","REJECTED","SETTLED","RECONCILED"}: row.closed_at=datetime.now(timezone.utc)
    db.add(TransactionStatusHistory(tenant_id=tenant_id,transaction_id=row.id,from_status=old,to_status=target,reason=body.reason,changed_by=actor))
    _audit_event(db,tenant_id=tenant_id,actor_id=actor,action="transactions.status_changed",event_type="BusinessTransactionStatusChanged",aggregate_type="business_transaction",aggregate_id=row.id,payload={"from":old,"to":target,"reason":body.reason})
    db.commit(); db.refresh(row); return _json_model(row)


@router.get("/transactions/{transaction_id}/history")
def transaction_history(transaction_id: UUID, ctx=Depends(require_permission("transactions.read"))):
    db, _, tenant_id, _ = ctx
    if not db.scalar(select(BusinessTransaction.id).where(BusinessTransaction.id==transaction_id,BusinessTransaction.tenant_id==tenant_id)): raise HTTPException(404,"Transaction not found")
    return [_json_model(x) for x in db.scalars(select(TransactionStatusHistory).where(TransactionStatusHistory.transaction_id==transaction_id,TransactionStatusHistory.tenant_id==tenant_id).order_by(desc(TransactionStatusHistory.changed_at))).all()]


@router.post("/workflows/definitions", status_code=201)
def create_workflow_definition(body: WorkflowDefinitionCreate, ctx=Depends(require_permission("workflows.manage"))):
    db, actor, tenant_id, _ = ctx
    keys=[s.step_key.strip() for s in body.steps]
    if len(keys)!=len(set(keys)): raise HTTPException(422,"Workflow step keys must be unique")
    row=WorkflowDefinition(tenant_id=tenant_id,code=body.code.strip().upper(),name=body.name.strip(),description=body.description,trigger_event=body.trigger_event,configuration=body.configuration,status="ACTIVE")
    db.add(row); db.flush()
    for step in body.steps:
        db.add(WorkflowStep(tenant_id=tenant_id,workflow_definition_id=row.id,step_key=step.step_key.strip(),name=step.name.strip(),step_type=step.step_type,position=step.position,configuration=step.configuration))
    try: db.flush()
    except IntegrityError as exc: db.rollback(); raise HTTPException(409,"Workflow definition code already exists") from exc
    _audit_event(db,tenant_id=tenant_id,actor_id=actor,action="workflows.definition.created",event_type="WorkflowDefinitionCreated",aggregate_type="workflow_definition",aggregate_id=row.id,payload={"code":row.code})
    db.commit(); db.refresh(row)
    steps=db.scalars(select(WorkflowStep).where(WorkflowStep.workflow_definition_id==row.id).order_by(WorkflowStep.position)).all()
    return {**_json_model(row),"steps":[_json_model(x) for x in steps]}


@router.get("/workflows/definitions")
def list_workflow_definitions(ctx=Depends(require_permission("workflows.read"))):
    db, _, tenant_id, _ = ctx
    rows=db.scalars(select(WorkflowDefinition).where(WorkflowDefinition.tenant_id==tenant_id,WorkflowDefinition.status!="ARCHIVED").order_by(WorkflowDefinition.name)).all()
    out=[]
    for row in rows:
        steps=db.scalars(select(WorkflowStep).where(WorkflowStep.workflow_definition_id==row.id).order_by(WorkflowStep.position)).all()
        out.append({**_json_model(row),"steps":[_json_model(x) for x in steps]})
    return out


@router.post("/workflows/instances", status_code=201)
def create_workflow_instance(body: WorkflowInstanceCreate, ctx=Depends(require_permission("workflows.manage"))):
    db, actor, tenant_id, _ = ctx
    definition=db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.id==body.workflow_definition_id,WorkflowDefinition.tenant_id==tenant_id,WorkflowDefinition.status=="ACTIVE"))
    if not definition: raise HTTPException(404,"Workflow definition not found")
    entity_exists=False
    entity_type=body.entity_type.strip().lower()
    model_map={"transaction":BusinessTransaction,"party":Party,"task":Task,"product":Product,"service":Service,"resource":Resource}
    model=model_map.get(entity_type)
    if model:
        entity_exists=db.scalar(select(model.id).where(model.id==body.entity_id,model.tenant_id==tenant_id)) is not None
    else:
        entity_exists=True
    if not entity_exists: raise HTTPException(400,"Workflow entity does not belong to tenant")
    first=db.scalar(select(WorkflowStep).where(WorkflowStep.workflow_definition_id==definition.id).order_by(WorkflowStep.position).limit(1))
    if not first: raise HTTPException(409,"Workflow definition has no steps")
    instance=WorkflowInstance(tenant_id=tenant_id,workflow_definition_id=definition.id,entity_type=entity_type,entity_id=body.entity_id,current_step_id=first.id,status="RUNNING",context=body.context)
    db.add(instance); db.flush()
    task_id=None
    if first.step_type in {"TASK","APPROVAL"}:
        task=Task(tenant_id=tenant_id,title=f"Workflow: {first.name}",description=f"Complete workflow step {first.step_key}",status="OPEN",priority="NORMAL",entity_type="workflow_instance",entity_id=instance.id,metadata_json={"workflow_step_id":str(first.id),"step_type":first.step_type})
        db.add(task); db.flush(); task_id=task.id
    db.add(WorkflowStepRun(tenant_id=tenant_id,workflow_instance_id=instance.id,workflow_step_id=first.id,status="RUNNING",task_id=task_id))
    _audit_event(db,tenant_id=tenant_id,actor_id=actor,action="workflows.instance.created",event_type="WorkflowInstanceCreated",aggregate_type="workflow_instance",aggregate_id=instance.id,payload={"definition_id":str(definition.id),"entity_type":entity_type,"entity_id":str(body.entity_id)})
    db.commit(); db.refresh(instance)
    return _json_model(instance) | {"current_step":_json_model(first)}


@router.get("/workflows/instances")
def list_workflow_instances(status: str | None = None, ctx=Depends(require_permission("workflows.read"))):
    db, _, tenant_id, _ = ctx
    stmt=select(WorkflowInstance).where(WorkflowInstance.tenant_id==tenant_id).order_by(desc(WorkflowInstance.started_at)).limit(500)
    if status: stmt=stmt.where(WorkflowInstance.status==status.strip().upper())
    return [_json_model(x) for x in db.scalars(stmt).all()]


@router.post("/workflows/instances/{instance_id}/advance")
def advance_workflow(instance_id: UUID, output: dict[str, Any] | None = None, ctx=Depends(require_permission("workflows.manage"))):
    db, actor, tenant_id, _ = ctx
    instance=db.scalar(select(WorkflowInstance).where(WorkflowInstance.id==instance_id,WorkflowInstance.tenant_id==tenant_id).with_for_update())
    if not instance: raise HTTPException(404,"Workflow instance not found")
    if instance.status != "RUNNING": raise HTTPException(409,"Workflow instance is not running")
    current=db.scalar(select(WorkflowStep).where(WorkflowStep.id==instance.current_step_id,WorkflowStep.tenant_id==tenant_id))
    if not current: raise HTTPException(409,"Workflow current step is missing")
    run=db.scalar(select(WorkflowStepRun).where(WorkflowStepRun.workflow_instance_id==instance.id,WorkflowStepRun.workflow_step_id==current.id,WorkflowStepRun.status=="RUNNING").order_by(desc(WorkflowStepRun.started_at)).limit(1).with_for_update())
    now=datetime.now(timezone.utc)
    if run:
        run.status="COMPLETED"; run.output=output or {}; run.completed_at=now
        if run.task_id:
            task=db.get(Task,run.task_id)
            if task: task.status="COMPLETED"
    next_step=db.scalar(select(WorkflowStep).where(WorkflowStep.workflow_definition_id==instance.workflow_definition_id,WorkflowStep.position>current.position).order_by(WorkflowStep.position).limit(1))
    if not next_step:
        instance.status="COMPLETED"; instance.completed_at=now
    else:
        instance.current_step_id=next_step.id
        task_id=None
        if next_step.step_type in {"TASK","APPROVAL"}:
            task=Task(tenant_id=tenant_id,title=f"Workflow: {next_step.name}",description=f"Complete workflow step {next_step.step_key}",status="OPEN",priority="NORMAL",entity_type="workflow_instance",entity_id=instance.id,metadata_json={"workflow_step_id":str(next_step.id),"step_type":next_step.step_type})
            db.add(task); db.flush(); task_id=task.id
        db.add(WorkflowStepRun(tenant_id=tenant_id,workflow_instance_id=instance.id,workflow_step_id=next_step.id,status="RUNNING",task_id=task_id))
    _audit_event(db,tenant_id=tenant_id,actor_id=actor,action="workflows.instance.advanced",event_type="WorkflowInstanceAdvanced",aggregate_type="workflow_instance",aggregate_id=instance.id,payload={"from_step":current.step_key,"to_step":next_step.step_key if next_step else None,"status":instance.status})
    db.commit(); db.refresh(instance)
    return _json_model(instance)


@router.get("/workflows/instances/{instance_id}")
def get_workflow_instance(instance_id: UUID, ctx=Depends(require_permission("workflows.read"))):
    db, _, tenant_id, _ = ctx
    instance=db.scalar(select(WorkflowInstance).where(WorkflowInstance.id==instance_id,WorkflowInstance.tenant_id==tenant_id))
    if not instance: raise HTTPException(404,"Workflow instance not found")
    runs=db.scalars(select(WorkflowStepRun).where(WorkflowStepRun.workflow_instance_id==instance.id).order_by(WorkflowStepRun.started_at)).all()
    current=db.get(WorkflowStep,instance.current_step_id) if instance.current_step_id else None
    return {**_json_model(instance),"current_step":_json_model(current) if current else None,"runs":[_json_model(x) for x in runs]}


@router.get("/context/{entity_type}/{entity_id}", response_model=ContextOut)
def get_business_context(entity_type: str, entity_id: UUID, ctx=Depends(require_permission("context.read"))):
    db, _, tenant_id, _ = ctx
    entity_type=entity_type.strip().lower()
    if entity_type == "party":
        primary=db.scalar(select(Party).where(Party.id==entity_id,Party.tenant_id==tenant_id,Party.deleted_at.is_(None)))
        if not primary: raise HTTPException(404,"Party not found")
        roles=db.scalars(select(PartyRole).where(PartyRole.party_id==entity_id,PartyRole.tenant_id==tenant_id)).all()
        relationships=db.scalars(select(PartyRelationship).where(PartyRelationship.tenant_id==tenant_id,or_(PartyRelationship.from_party_id==entity_id,PartyRelationship.to_party_id==entity_id),PartyRelationship.status=="ACTIVE")).all()
        transactions=db.scalars(select(BusinessTransaction).where(BusinessTransaction.tenant_id==tenant_id,BusinessTransaction.party_id==entity_id).order_by(desc(BusinessTransaction.occurred_at)).limit(50)).all()
        tasks=db.scalars(select(Task).where(Task.tenant_id==tenant_id,Task.entity_type=="party",Task.entity_id==entity_id).order_by(desc(Task.created_at)).limit(50)).all()
        cases=db.scalars(select(BusinessCase).where(BusinessCase.tenant_id==tenant_id,BusinessCase.party_id==entity_id).order_by(desc(BusinessCase.opened_at)).limit(50)).all()
        rel=[_json_model(x) for x in relationships]
        return ContextOut(entity_type="party",entity_id=entity_id,primary=_json_model(primary),related={"roles":[_json_model(x) for x in roles],"relationships":rel,"transactions":[_json_model(x) for x in transactions],"tasks":[_json_model(x) for x in tasks],"cases":[_json_model(x) for x in cases]},evidence=[{"source":"parties","id":str(entity_id),"observed_at":primary.updated_at.isoformat() if primary.updated_at else None}])
    if entity_type == "transaction":
        primary=db.scalar(select(BusinessTransaction).where(BusinessTransaction.id==entity_id,BusinessTransaction.tenant_id==tenant_id))
        if not primary: raise HTTPException(404,"Transaction not found")
        lines=db.scalars(select(TransactionLine).where(TransactionLine.transaction_id==entity_id).order_by(TransactionLine.line_no)).all()
        history=db.scalars(select(TransactionStatusHistory).where(TransactionStatusHistory.transaction_id==entity_id).order_by(desc(TransactionStatusHistory.changed_at))).all()
        payments=db.scalars(select(Payment).where(Payment.transaction_id==entity_id,Payment.tenant_id==tenant_id).order_by(desc(Payment.paid_at))).all()
        workflow_instances=db.scalars(select(WorkflowInstance).where(WorkflowInstance.tenant_id==tenant_id,WorkflowInstance.entity_type=="transaction",WorkflowInstance.entity_id==entity_id).order_by(desc(WorkflowInstance.started_at))).all()
        return ContextOut(entity_type="transaction",entity_id=entity_id,primary=_json_model(primary),related={"lines":[_json_model(x) for x in lines],"history":[_json_model(x) for x in history],"payments":[_json_model(x) for x in payments],"workflow_instances":[_json_model(x) for x in workflow_instances]},evidence=[{"source":"business_transactions","id":str(entity_id),"observed_at":primary.updated_at.isoformat() if primary.updated_at else None}])
    if entity_type == "product":
        primary=db.scalar(select(Product).where(Product.id==entity_id,Product.tenant_id==tenant_id,Product.deleted_at.is_(None)))
        if not primary: raise HTTPException(404,"Product not found")
        variants=db.scalars(select(ProductVariant).where(ProductVariant.product_id==entity_id,ProductVariant.tenant_id==tenant_id,ProductVariant.deleted_at.is_(None))).all()
        lines=db.scalars(select(TransactionLine).where(TransactionLine.tenant_id==tenant_id,TransactionLine.product_variant_id.in_([v.id for v in variants]) if variants else False).order_by(desc(TransactionLine.created_at)).limit(50)).all()
        return ContextOut(entity_type="product",entity_id=entity_id,primary=_json_model(primary),related={"variants":[_json_model(x) for x in variants],"recent_transaction_lines":[_json_model(x) for x in lines]},evidence=[{"source":"products","id":str(entity_id),"observed_at":primary.updated_at.isoformat() if primary.updated_at else None}])
    raise HTTPException(400,"Context supports party, transaction and product entities")
