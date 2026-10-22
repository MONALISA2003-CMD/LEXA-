from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..dependencies import require_permission
from ..models import Branch, BusinessProfile, Warehouse, Location, PosTerminal
from ..catalog import begin_idempotency, emit_event, finish_idempotency, write_audit
from ..catalog_rules import CatalogValidation

router = APIRouter(prefix="/organization", tags=["organization"])


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BusinessProfileIn(BaseModel):
    legal_name: str = Field(min_length=2, max_length=250)
    display_name: str = Field(min_length=2, max_length=250)
    country_code: str = Field(default="UG", pattern=r"^[A-Z]{2}$")
    currency_code: str = Field(default="UGX", pattern=r"^[A-Z]{3}$")

    @field_validator("legal_name", "display_name")
    @classmethod
    def trim_profile_names(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least two characters.")
        return value

    @field_validator("country_code", "currency_code", mode="before")
    @classmethod
    def normalize_profile_codes(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class BusinessProfilePatch(BaseModel):
    legal_name: str | None = Field(default=None, min_length=2, max_length=250)
    display_name: str | None = Field(default=None, min_length=2, max_length=250)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @field_validator("legal_name", "display_name")
    @classmethod
    def trim_profile_names(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least two characters.")
        return value

    @field_validator("country_code", "currency_code", mode="before")
    @classmethod
    def normalize_profile_codes(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class BusinessProfileOut(ORM):
    id: UUID
    tenant_id: UUID
    legal_name: str
    display_name: str
    country_code: str
    currency_code: str


class BranchIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=50)

    @field_validator("name")
    @classmethod
    def trim_branch_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least two characters.")
        return value

    @field_validator("code")
    @classmethod
    def normalize_branch_code(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("Branch code must have at least two characters.")
        return value


class BranchPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    code: str | None = Field(default=None, min_length=2, max_length=50)

    @field_validator("name")
    @classmethod
    def trim_branch_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least two characters.")
        return value

    @field_validator("code")
    @classmethod
    def normalize_branch_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("Branch code must have at least two characters.")
        return value


class BranchOut(ORM):
    id: UUID
    tenant_id: UUID
    name: str
    code: str
    status: str


class WarehouseIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=50)
    branch_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def trim_warehouse_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least two characters.")
        return value

    @field_validator("code")
    @classmethod
    def normalize_warehouse_code(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("Warehouse code must have at least two characters.")
        return value


class WarehouseOut(ORM):
    id: UUID
    tenant_id: UUID
    name: str
    code: str
    branch_id: UUID | None
    status: str


class LocationIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=50)
    warehouse_id: UUID

    @field_validator("name")
    @classmethod
    def trim_location_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least two characters.")
        return value

    @field_validator("code")
    @classmethod
    def normalize_location_code(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("Location code must have at least two characters.")
        return value


class LocationOut(ORM):
    id: UUID
    tenant_id: UUID
    warehouse_id: UUID
    name: str
    code: str
    status: str


class PosIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=50)
    branch_id: UUID

    @field_validator("name")
    @classmethod
    def trim_pos_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least two characters.")
        return value

    @field_validator("code")
    @classmethod
    def normalize_pos_code(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise ValueError("POS terminal code must have at least two characters.")
        return value


class PosOut(ORM):
    id: UUID
    tenant_id: UUID
    branch_id: UUID
    name: str
    code: str
    status: str


def _begin_idempotency(db: Session, *, tenant_id: UUID, operation_type: str, key: str, payload: dict):
    try:
        return begin_idempotency(
            db,
            tenant_id=tenant_id,
            operation_type=operation_type,
            key=key,
            payload=payload,
        )
    except CatalogValidation as exc:
        message = str(exc)
        status_code = 409 if "already used with a different request" in message else 400
        raise HTTPException(status_code, message) from exc


def _commit_created(
    db: Session,
    *,
    row,
    tenant_id: UUID,
    actor_id: UUID,
    action: str,
    event_type: str,
    idem,
    resource_type: str,
    response_body: dict,
):
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action=action,
        target_type=resource_type,
        target_id=row.id,
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        event_type=event_type,
        aggregate_type=resource_type,
        aggregate_id=row.id,
        actor_user_id=actor_id,
        payload={"id": str(row.id), "name": row.name, "code": row.code},
    )
    finish_idempotency(
        db,
        idem,
        status_code=201,
        response_body=response_body,
        resource_type=resource_type,
        resource_id=row.id,
    )
    # response_body was materialized before commit; avoid a second RLS-scoped SELECT.
    db.commit()
    return response_body


def _require_replay(replay, response_model, *, resource_label: str):
    if not replay:
        return None
    body = replay[1]
    if not body:
        raise HTTPException(409, f"Idempotency replay for {resource_label} has no saved response")
    try:
        return response_model.model_validate(body)
    except Exception as exc:
        raise HTTPException(409, f"Idempotency replay for {resource_label} has an invalid saved response") from exc


@router.get("/profile", response_model=BusinessProfileOut | None)
def get_profile(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx
    return db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id))


@router.post("/profile", response_model=BusinessProfileOut, status_code=201)
def create_profile(
    body: BusinessProfileIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    ctx=Depends(require_permission("organization.manage")),
):
    db, actor_id, tenant_id, _ = ctx
    idem, replay = _begin_idempotency(
        db,
        tenant_id=tenant_id,
        operation_type="organization.profile.create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    replayed = _require_replay(replay, BusinessProfileOut, resource_label="business profile")
    if replayed is not None:
        db.rollback()
        return replayed
    if db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id)):
        db.rollback()
        raise HTTPException(409, "Business profile already exists")
    profile = BusinessProfile(tenant_id=tenant_id, **body.model_dump())
    db.add(profile)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Business profile conflicts with an existing record") from exc
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="organization.profile.create",
        target_type="business_profile",
        target_id=profile.id,
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        event_type="BusinessProfileCreated",
        aggregate_type="business_profile",
        aggregate_id=profile.id,
        actor_user_id=actor_id,
        payload={
            "id": str(profile.id),
            "legal_name": profile.legal_name,
            "display_name": profile.display_name,
            "country_code": profile.country_code,
            "currency_code": profile.currency_code,
        },
    )
    response_body = BusinessProfileOut.model_validate(profile).model_dump(mode="json")
    finish_idempotency(
        db,
        idem,
        status_code=201,
        response_body=response_body,
        resource_type="business_profile",
        resource_id=profile.id,
    )
    db.commit()
    return profile


@router.patch("/profile", response_model=BusinessProfileOut)
def update_profile(
    body: BusinessProfilePatch,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    ctx=Depends(require_permission("organization.manage")),
):
    db, actor_id, tenant_id, _ = ctx
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(422, "Provide at least one business profile field to update")
    if any(value is None for value in updates.values()):
        raise HTTPException(422, "Business profile fields cannot be null")
    idem, replay = _begin_idempotency(
        db,
        tenant_id=tenant_id,
        operation_type="organization.profile.update",
        key=idempotency_key,
        payload=body.model_dump(exclude_unset=True, mode="json"),
    )
    replayed = _require_replay(replay, BusinessProfileOut, resource_label="business profile update")
    if replayed is not None:
        db.rollback()
        return replayed
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id))
    if not profile:
        db.rollback()
        raise HTTPException(404, "Create the business profile before updating it")
    for field, value in updates.items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(timezone.utc)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Business profile update conflicts with an existing record") from exc
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="organization.profile.update",
        target_type="business_profile",
        target_id=profile.id,
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        event_type="BusinessProfileUpdated",
        aggregate_type="business_profile",
        aggregate_id=profile.id,
        actor_user_id=actor_id,
        payload={
            "id": str(profile.id),
            "changed_fields": sorted(updates),
            "legal_name": profile.legal_name,
            "display_name": profile.display_name,
            "country_code": profile.country_code,
            "currency_code": profile.currency_code,
        },
    )
    response_body = BusinessProfileOut.model_validate(profile).model_dump(mode="json")
    finish_idempotency(
        db,
        idem,
        status_code=200,
        response_body=response_body,
        resource_type="business_profile",
        resource_id=profile.id,
    )
    db.commit()
    return profile


@router.get("/branches", response_model=list[BranchOut])
def list_branches(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Branch).where(Branch.tenant_id == tenant_id).order_by(Branch.name)))


@router.post("/branches", response_model=BranchOut, status_code=201)
def create_branch(
    body: BranchIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    ctx=Depends(require_permission("organization.manage")),
):
    db, actor_id, tenant_id, _ = ctx
    idem, replay = _begin_idempotency(
        db,
        tenant_id=tenant_id,
        operation_type="organization.branch.create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    replayed = _require_replay(replay, BranchOut, resource_label="branch")
    if replayed is not None:
        db.rollback()
        return replayed
    branch = Branch(tenant_id=tenant_id, **body.model_dump())
    db.add(branch)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Branch code already exists") from exc
    return _commit_created(
        db,
        row=branch,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="organization.branch.create",
        event_type="BranchCreated",
        idem=idem,
        resource_type="branch",
        response_body=BranchOut.model_validate(branch).model_dump(mode="json"),
    )


@router.patch("/branches/{branch_id}", response_model=BranchOut)
def update_branch(
    branch_id: UUID,
    body: BranchPatch,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    ctx=Depends(require_permission("organization.manage")),
):
    db, actor_id, tenant_id, _ = ctx
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(422, "Provide at least one branch field to update")
    if any(value is None for value in updates.values()):
        raise HTTPException(422, "Branch fields cannot be null")
    idem, replay = _begin_idempotency(
        db,
        tenant_id=tenant_id,
        operation_type="organization.branch.update",
        key=idempotency_key,
        payload={"branch_id": str(branch_id), **body.model_dump(exclude_unset=True, mode="json")},
    )
    replayed = _require_replay(replay, BranchOut, resource_label="branch update")
    if replayed is not None:
        db.rollback()
        return replayed
    branch = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.tenant_id == tenant_id))
    if not branch:
        db.rollback()
        raise HTTPException(404, "Branch not found")
    for field, value in updates.items():
        setattr(branch, field, value)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Branch code already exists") from exc
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="organization.branch.update",
        target_type="branch",
        target_id=branch.id,
    )
    emit_event(
        db,
        tenant_id=tenant_id,
        event_type="BranchUpdated",
        aggregate_type="branch",
        aggregate_id=branch.id,
        actor_user_id=actor_id,
        payload={"id": str(branch.id), "changed_fields": sorted(updates), "name": branch.name, "code": branch.code},
    )
    response_body = BranchOut.model_validate(branch).model_dump(mode="json")
    finish_idempotency(
        db,
        idem,
        status_code=200,
        response_body=response_body,
        resource_type="branch",
        resource_id=branch.id,
    )
    db.commit()
    # response_body was materialized before commit; no post-commit RLS refresh is needed.
    return response_body


@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Warehouse).where(Warehouse.tenant_id == tenant_id).order_by(Warehouse.name)))


@router.post("/warehouses", response_model=WarehouseOut, status_code=201)
def create_warehouse(
    body: WarehouseIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    ctx=Depends(require_permission("organization.manage")),
):
    db, actor_id, tenant_id, _ = ctx
    idem, replay = _begin_idempotency(
        db,
        tenant_id=tenant_id,
        operation_type="organization.warehouse.create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay:
        existing = db.scalar(select(Warehouse).where(Warehouse.id == UUID(replay[1]["id"]), Warehouse.tenant_id == tenant_id))
        if existing:
            db.rollback()
            return existing
        db.rollback()
        raise HTTPException(409, "Idempotency replay resource no longer exists")
    if body.branch_id and not db.scalar(select(Branch.id).where(Branch.id == body.branch_id, Branch.tenant_id == tenant_id)):
        db.rollback()
        raise HTTPException(400, "Branch does not belong to tenant")
    warehouse = Warehouse(tenant_id=tenant_id, **body.model_dump())
    db.add(warehouse)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Warehouse code already exists") from exc
    return _commit_created(
        db,
        row=warehouse,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="organization.warehouse.create",
        event_type="WarehouseCreated",
        idem=idem,
        resource_type="warehouse",
        response_body=WarehouseOut.model_validate(warehouse).model_dump(mode="json"),
    )


@router.get("/locations", response_model=list[LocationOut])
def list_locations(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(Location).where(Location.tenant_id == tenant_id).order_by(Location.name)))


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(
    body: LocationIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    ctx=Depends(require_permission("organization.manage")),
):
    db, actor_id, tenant_id, _ = ctx
    idem, replay = _begin_idempotency(
        db,
        tenant_id=tenant_id,
        operation_type="organization.location.create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay:
        existing = db.scalar(select(Location).where(Location.id == UUID(replay[1]["id"]), Location.tenant_id == tenant_id))
        if existing:
            db.rollback()
            return existing
        db.rollback()
        raise HTTPException(409, "Idempotency replay resource no longer exists")
    if not db.scalar(select(Warehouse.id).where(Warehouse.id == body.warehouse_id, Warehouse.tenant_id == tenant_id)):
        db.rollback()
        raise HTTPException(400, "Warehouse does not belong to tenant")
    location = Location(tenant_id=tenant_id, **body.model_dump())
    db.add(location)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Location code already exists in warehouse") from exc
    return _commit_created(
        db,
        row=location,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="organization.location.create",
        event_type="LocationCreated",
        idem=idem,
        resource_type="location",
        response_body=LocationOut.model_validate(location).model_dump(mode="json"),
    )


@router.get("/pos-terminals", response_model=list[PosOut])
def list_pos(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(PosTerminal).where(PosTerminal.tenant_id == tenant_id).order_by(PosTerminal.name)))


@router.post("/pos-terminals", response_model=PosOut, status_code=201)
def create_pos(
    body: PosIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    ctx=Depends(require_permission("organization.manage")),
):
    db, actor_id, tenant_id, _ = ctx
    idem, replay = _begin_idempotency(
        db,
        tenant_id=tenant_id,
        operation_type="organization.pos_terminal.create",
        key=idempotency_key,
        payload=body.model_dump(mode="json"),
    )
    if replay:
        existing = db.scalar(select(PosTerminal).where(PosTerminal.id == UUID(replay[1]["id"]), PosTerminal.tenant_id == tenant_id))
        if existing:
            db.rollback()
            return existing
        db.rollback()
        raise HTTPException(409, "Idempotency replay resource no longer exists")
    if not db.scalar(select(Branch.id).where(Branch.id == body.branch_id, Branch.tenant_id == tenant_id)):
        db.rollback()
        raise HTTPException(400, "Branch does not belong to tenant")
    terminal = PosTerminal(tenant_id=tenant_id, **body.model_dump())
    db.add(terminal)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "POS terminal code already exists") from exc
    return _commit_created(
        db,
        row=terminal,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="organization.pos_terminal.create",
        event_type="PosTerminalCreated",
        idem=idem,
        resource_type="pos_terminal",
        response_body=PosOut.model_validate(terminal).model_dump(mode="json"),
    )
