from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .dependencies import require_permission
from .catalog import begin_idempotency, emit_event, finish_idempotency, write_audit
from .models import (
    Asset, BusinessCase, BusinessProject, BusinessTransaction, Contract, Document,
    Branch, Party, PartyRole, Payment, Resource, Service, Task, TenantMembership,
)

router = APIRouter(prefix="/kernel", tags=["business-kernel"])


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PartyCreate(BaseModel):
    party_type: str = Field(pattern=r"^(PERSON|ORGANIZATION)$")
    display_name: str = Field(min_length=1, max_length=250)
    legal_name: str | None = Field(default=None, max_length=250)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    metadata: dict = Field(default_factory=dict)


class PartyOut(ORM):
    id: UUID; tenant_id: UUID; party_type: str; display_name: str; legal_name: str | None
    email: str | None; phone: str | None; status: str; metadata: dict = Field(validation_alias="metadata_json")


class PartyRoleCreate(BaseModel):
    party_id: UUID
    role_type: str = Field(pattern=r"^(CUSTOMER|SUPPLIER|EMPLOYEE|CONTACT|OTHER)$")
    metadata: dict = Field(default_factory=dict)


class PartyRoleOut(ORM):
    id: UUID; tenant_id: UUID; party_id: UUID; role_type: str; status: str; metadata: dict = Field(validation_alias="metadata_json")


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    code: str = Field(min_length=1, max_length=80)
    description: str | None = None
    service_type: str | None = None
    metadata: dict = Field(default_factory=dict)


class ServiceOut(ORM):
    id: UUID; tenant_id: UUID; name: str; code: str; description: str | None
    service_type: str | None; status: str; metadata: dict = Field(validation_alias="metadata_json")


class ResourceCreate(BaseModel):
    resource_type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    code: str = Field(min_length=1, max_length=80)
    capacity: Decimal | None = None
    metadata: dict = Field(default_factory=dict)


class ResourceOut(ORM):
    id: UUID; tenant_id: UUID; resource_type: str; name: str; code: str
    capacity: Decimal | None; status: str; metadata: dict = Field(validation_alias="metadata_json")


class AssetCreate(BaseModel):
    asset_type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    code: str = Field(min_length=1, max_length=80)
    serial_number: str | None = None
    resource_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class AssetOut(ORM):
    id: UUID; tenant_id: UUID; asset_type: str; name: str; code: str
    serial_number: str | None; resource_id: UUID | None; status: str; metadata: dict = Field(validation_alias="metadata_json")


class DocumentCreate(BaseModel):
    document_type: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    name: str
    mime_type: str | None = None
    storage_key: str | None = None
    metadata: dict = Field(default_factory=dict)


class DocumentOut(ORM):
    id: UUID; tenant_id: UUID; document_type: str; entity_type: str | None
    entity_id: UUID | None; name: str; mime_type: str | None; storage_key: str | None
    status: str; metadata: dict = Field(validation_alias="metadata_json")


class BusinessTransactionCreate(BaseModel):
    transaction_type: str
    reference: str
    party_id: UUID | None = None
    branch_id: UUID | None = None
    total_amount: Decimal | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    occurred_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class BusinessTransactionOut(ORM):
    id: UUID; tenant_id: UUID; transaction_type: str; reference: str; status: str
    party_id: UUID | None; branch_id: UUID | None; total_amount: Decimal | None
    currency_code: str | None; occurred_at: datetime; metadata: dict = Field(validation_alias="metadata_json")


class PaymentCreate(BaseModel):
    transaction_id: UUID | None = None
    party_id: UUID | None = None
    amount: Decimal = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    method: str = Field(min_length=1, max_length=50)
    reference: str | None = None
    paid_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class PaymentOut(ORM):
    id: UUID; tenant_id: UUID; transaction_id: UUID | None; party_id: UUID | None
    amount: Decimal; currency_code: str; method: str; status: str; reference: str | None
    paid_at: datetime; metadata: dict = Field(validation_alias="metadata_json")


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = Field(default="NORMAL", pattern=r"^(LOW|NORMAL|HIGH|URGENT)$")
    assigned_to_user_id: UUID | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    due_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class TaskOut(ORM):
    id: UUID; tenant_id: UUID; title: str; description: str | None; status: str
    priority: str; assigned_to_user_id: UUID | None; entity_type: str | None
    entity_id: UUID | None; due_at: datetime | None; metadata: dict = Field(validation_alias="metadata_json")


class CaseCreate(BaseModel):
    case_type: str
    title: str
    priority: str = Field(default="NORMAL", pattern=r"^(LOW|NORMAL|HIGH|URGENT)$")
    party_id: UUID | None = None
    assigned_to_user_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class CaseOut(ORM):
    id: UUID; tenant_id: UUID; case_type: str; title: str; status: str
    priority: str; party_id: UUID | None; assigned_to_user_id: UUID | None
    opened_at: datetime; closed_at: datetime | None; metadata: dict = Field(validation_alias="metadata_json")


class ProjectCreate(BaseModel):
    name: str
    code: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class ProjectOut(ORM):
    id: UUID; tenant_id: UUID; name: str; code: str; status: str
    starts_at: datetime | None; ends_at: datetime | None; metadata: dict = Field(validation_alias="metadata_json")


class ContractCreate(BaseModel):
    contract_number: str
    contract_type: str
    title: str
    party_id: UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    terms: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class ContractOut(ORM):
    id: UUID; tenant_id: UUID; contract_number: str; contract_type: str; title: str
    status: str; party_id: UUID | None; starts_at: datetime | None; ends_at: datetime | None
    terms: dict; metadata: dict = Field(validation_alias="metadata_json")


def _orm_data(body: BaseModel) -> dict:
    data = body.model_dump()
    if "metadata" in data:
        data["metadata_json"] = data.pop("metadata")
    return data


def _commit_created(db: Session, *, row, tenant_id: UUID, actor_id: UUID, action: str, event_type: str, request_id: str | None, idem, result_type: str):
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action=action, target_type=result_type, target_id=row.id, correlation_id=request_id)
    emit_event(db, tenant_id=tenant_id, event_type=event_type, aggregate_type=result_type, aggregate_id=row.id,
               payload={"id": str(row.id)}, actor_user_id=actor_id, correlation_id=request_id)
    body = {"id": str(row.id), "status": getattr(row, "status", None)}
    finish_idempotency(db, idem, status_code=201, response_body=body, resource_type=result_type, resource_id=row.id)
    db.commit()
    db.refresh(row)
    return row


def _find_party(db: Session, tenant_id: UUID, party_id: UUID | None):
    if party_id is None:
        return None
    return db.scalar(select(Party).where(Party.id == party_id, Party.tenant_id == tenant_id))


@router.get("/summary")
def kernel_summary(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    entities = {
        "parties": Party, "services": Service, "resources": Resource, "assets": Asset,
        "documents": Document, "transactions": BusinessTransaction, "payments": Payment,
        "tasks": Task, "cases": BusinessCase, "projects": BusinessProject, "contracts": Contract,
    }
    return {
        "tenant_id": str(tenant_id),
        "counts": {name: db.query(model).filter(model.tenant_id == tenant_id).count() for name, model in entities.items()},
    }


@router.get("/parties", response_model=list[PartyOut])
def list_parties(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Party).where(Party.tenant_id == tenant_id, Party.deleted_at.is_(None)).order_by(Party.display_name).limit(500)))


@router.post("/parties", response_model=PartyOut, status_code=201)
def create_party(body: PartyCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    idem, replay = begin_idempotency(db, tenant_id=tenant_id, operation_type="kernel.party.create", key=idempotency_key, payload=body.model_dump(mode="json"))
    if replay:
        existing = db.scalar(select(Party).where(Party.id == UUID(replay[1]["id"]), Party.tenant_id == tenant_id))
        if existing:
            return existing
        db.rollback()
        raise HTTPException(409, "Idempotency replay resource no longer exists")
    row = Party(tenant_id=tenant_id, **_orm_data(body))
    db.add(row); db.flush()
    return _commit_created(db, row=row, tenant_id=tenant_id, actor_id=actor_id, action="kernel.party.create", event_type="party.created", request_id=None, idem=idem, result_type="party")


@router.post("/parties/{party_id}/roles", response_model=PartyRoleOut, status_code=201)
def add_party_role(party_id: UUID, body: PartyRoleCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    party = db.scalar(select(Party).where(Party.id == party_id, Party.tenant_id == tenant_id))
    if not party:
        raise HTTPException(404, "Party not found")
    if party_id != body.party_id:
        raise HTTPException(400, "Path and body party IDs must match")
    row = PartyRole(tenant_id=tenant_id, party_id=party_id, role_type=body.role_type, metadata_json=body.metadata)
    db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.party.role.add", target_type="party_role", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="party.role_added", aggregate_type="party", aggregate_id=party_id,
               payload={"role_type": body.role_type}, actor_user_id=actor_id)
    db.commit(); db.refresh(row)
    return row


@router.get("/services", response_model=list[ServiceOut])
def list_services(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Service).where(Service.tenant_id == tenant_id).order_by(Service.name).limit(500)))


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(body: ServiceCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    idem, replay = begin_idempotency(db, tenant_id=tenant_id, operation_type="kernel.service.create", key=idempotency_key, payload=body.model_dump(mode="json"))
    if replay:
        db.rollback()
        existing = db.get(Service, UUID(replay[1]["id"]))
        if existing:
            return existing
        raise HTTPException(409, "Idempotency replay resource no longer exists")
    row = Service(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    return _commit_created(db, row=row, tenant_id=tenant_id, actor_id=actor_id, action="kernel.service.create", event_type="service.created", request_id=None, idem=idem, result_type="service")


@router.get("/resources", response_model=list[ResourceOut])
def list_resources(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Resource).where(Resource.tenant_id == tenant_id).order_by(Resource.name).limit(500)))


@router.post("/resources", response_model=ResourceOut, status_code=201)
def create_resource(body: ResourceCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    if idempotency_key:
        idem, replay = begin_idempotency(db, tenant_id=tenant_id, operation_type="kernel.resource.create", key=idempotency_key, payload=body.model_dump(mode="json"))
        if replay:
            db.rollback()
            existing = db.get(Resource, UUID(replay[1]["id"]))
            if existing: return existing
            raise HTTPException(409, "Idempotency replay resource no longer exists")
    else:
        idem = None
    row = Resource(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    return _commit_created(db, row=row, tenant_id=tenant_id, actor_id=actor_id, action="kernel.resource.create", event_type="resource.created", request_id=None, idem=idem, result_type="resource")


@router.post("/assets", response_model=AssetOut, status_code=201)
def create_asset(body: AssetCreate, ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    if body.resource_id and not db.scalar(select(Resource.id).where(Resource.id == body.resource_id, Resource.tenant_id == tenant_id)):
        raise HTTPException(400, "Resource does not belong to tenant")
    row = Asset(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.asset.create", target_type="asset", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="asset.created", aggregate_type="asset", aggregate_id=row.id, payload={"id": str(row.id)}, actor_user_id=actor_id)
    db.commit(); db.refresh(row); return row


@router.get("/assets", response_model=list[AssetOut])
def list_assets(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Asset).where(Asset.tenant_id == tenant_id).order_by(Asset.name).limit(500)))


@router.post("/documents", response_model=DocumentOut, status_code=201)
def create_document(body: DocumentCreate, ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    row = Document(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.document.create", target_type="document", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="document.created", aggregate_type="document", aggregate_id=row.id, payload={"id": str(row.id)}, actor_user_id=actor_id)
    db.commit(); db.refresh(row); return row


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Document).where(Document.tenant_id == tenant_id).order_by(Document.created_at.desc()).limit(500)))


@router.post("/transactions", response_model=BusinessTransactionOut, status_code=201)
def create_transaction(body: BusinessTransactionCreate, ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    if body.party_id and not _find_party(db, tenant_id, body.party_id):
        raise HTTPException(400, "Party does not belong to tenant")
    if body.branch_id and not db.scalar(select(Branch.id).where(Branch.id == body.branch_id, Branch.tenant_id == tenant_id)):
        raise HTTPException(400, "Branch does not belong to tenant")
    row = BusinessTransaction(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.transaction.create", target_type="business_transaction", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="business_transaction.created", aggregate_type="business_transaction", aggregate_id=row.id, payload={"reference": row.reference, "transaction_type": row.transaction_type}, actor_user_id=actor_id)
    db.commit(); db.refresh(row); return row


@router.get("/transactions", response_model=list[BusinessTransactionOut])
def list_transactions(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(BusinessTransaction).where(BusinessTransaction.tenant_id == tenant_id).order_by(BusinessTransaction.occurred_at.desc()).limit(500)))


@router.post("/payments", response_model=PaymentOut, status_code=201)
def create_payment(body: PaymentCreate, ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    if body.party_id and not _find_party(db, tenant_id, body.party_id):
        raise HTTPException(400, "Party does not belong to tenant")
    if body.transaction_id and not db.scalar(select(BusinessTransaction.id).where(BusinessTransaction.id == body.transaction_id, BusinessTransaction.tenant_id == tenant_id)):
        raise HTTPException(400, "Transaction does not belong to tenant")
    row = Payment(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.payment.create", target_type="payment", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="payment.recorded", aggregate_type="payment", aggregate_id=row.id, payload={"amount": str(row.amount), "currency_code": row.currency_code}, actor_user_id=actor_id)
    db.commit(); db.refresh(row); return row


@router.get("/payments", response_model=list[PaymentOut])
def list_payments(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Payment).where(Payment.tenant_id == tenant_id).order_by(Payment.paid_at.desc()).limit(500)))


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    if body.assigned_to_user_id and not db.scalar(select(TenantMembership.user_id).where(TenantMembership.user_id == body.assigned_to_user_id, TenantMembership.tenant_id == tenant_id, TenantMembership.status == "ACTIVE")):
        raise HTTPException(400, "Assigned user is not an active tenant member")
    row = Task(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.task.create", target_type="task", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="task.created", aggregate_type="task", aggregate_id=row.id, payload={"title": row.title}, actor_user_id=actor_id)
    db.commit(); db.refresh(row); return row


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Task).where(Task.tenant_id == tenant_id).order_by(Task.due_at.nulls_last(), Task.created_at.desc()).limit(500)))


@router.post("/cases", response_model=CaseOut, status_code=201)
def create_case(body: CaseCreate, ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    if body.party_id and not _find_party(db, tenant_id, body.party_id):
        raise HTTPException(400, "Party does not belong to tenant")
    row = BusinessCase(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.case.create", target_type="business_case", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="case.created", aggregate_type="business_case", aggregate_id=row.id, payload={"title": row.title, "case_type": row.case_type}, actor_user_id=actor_id)
    db.commit(); db.refresh(row); return row


@router.get("/cases", response_model=list[CaseOut])
def list_cases(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(BusinessCase).where(BusinessCase.tenant_id == tenant_id).order_by(BusinessCase.opened_at.desc()).limit(500)))


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    row = BusinessProject(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.project.create", target_type="business_project", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="project.created", aggregate_type="business_project", aggregate_id=row.id, payload={"code": row.code, "name": row.name}, actor_user_id=actor_id)
    db.commit(); db.refresh(row); return row


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(BusinessProject).where(BusinessProject.tenant_id == tenant_id).order_by(BusinessProject.name).limit(500)))


@router.post("/contracts", response_model=ContractOut, status_code=201)
def create_contract(body: ContractCreate, ctx=Depends(require_permission("kernel.manage"))):
    db, actor_id, tenant_id, _ = ctx
    if body.party_id and not _find_party(db, tenant_id, body.party_id):
        raise HTTPException(400, "Party does not belong to tenant")
    row = Contract(tenant_id=tenant_id, **_orm_data(body)); db.add(row); db.flush()
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor_id, action="kernel.contract.create", target_type="contract", target_id=row.id)
    emit_event(db, tenant_id=tenant_id, event_type="contract.created", aggregate_type="contract", aggregate_id=row.id, payload={"contract_number": row.contract_number}, actor_user_id=actor_id)
    db.commit(); db.refresh(row); return row


@router.get("/contracts", response_model=list[ContractOut])
def list_contracts(ctx=Depends(require_permission("kernel.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Contract).where(Contract.tenant_id == tenant_id).order_by(Contract.created_at.desc()).limit(500)))
