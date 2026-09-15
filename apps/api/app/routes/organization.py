from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..dependencies import tenant_db, require_permission
from ..models import Branch, BusinessProfile, Warehouse, Location, PosTerminal

router = APIRouter(prefix="/organization", tags=["organization"])

class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class BusinessProfileIn(BaseModel):
    legal_name: str; display_name: str; country_code: str = "UG"; currency_code: str = "UGX"
class BusinessProfileOut(ORM):
    id: UUID; tenant_id: UUID; legal_name: str; display_name: str; country_code: str; currency_code: str
class BranchIn(BaseModel): name: str; code: str
class BranchOut(ORM): id: UUID; tenant_id: UUID; name: str; code: str; status: str
class WarehouseIn(BaseModel): name: str; code: str; branch_id: UUID | None = None
class WarehouseOut(ORM): id: UUID; tenant_id: UUID; name: str; code: str; branch_id: UUID | None; status: str
class LocationIn(BaseModel): name: str; code: str; warehouse_id: UUID
class LocationOut(ORM): id: UUID; tenant_id: UUID; warehouse_id: UUID; name: str; code: str; status: str
class PosIn(BaseModel): name: str; code: str; branch_id: UUID
class PosOut(ORM): id: UUID; tenant_id: UUID; branch_id: UUID; name: str; code: str; status: str

@router.get("/profile", response_model=BusinessProfileOut | None)
def get_profile(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx
    return db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id))

@router.post("/profile", response_model=BusinessProfileOut)
def create_profile(body: BusinessProfileIn, ctx=Depends(require_permission("organization.manage"))):
    db, _, tenant_id, _ = ctx
    if db.scalar(select(BusinessProfile).where(BusinessProfile.tenant_id == tenant_id)):
        raise HTTPException(409, "Business profile already exists")
    profile = BusinessProfile(tenant_id=tenant_id, **body.model_dump()); db.add(profile); db.commit(); db.refresh(profile); return profile

@router.get("/branches", response_model=list[BranchOut])
def list_branches(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx; return list(db.scalars(select(Branch).where(Branch.tenant_id == tenant_id).order_by(Branch.name)))

@router.post("/branches", response_model=BranchOut)
def create_branch(body: BranchIn, ctx=Depends(require_permission("organization.manage"))):
    db, _, tenant_id, _ = ctx
    branch = Branch(tenant_id=tenant_id, **body.model_dump()); db.add(branch)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "Branch code already exists")
    db.refresh(branch); return branch

@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx; return list(db.scalars(select(Warehouse).where(Warehouse.tenant_id == tenant_id).order_by(Warehouse.name)))

@router.post("/warehouses", response_model=WarehouseOut)
def create_warehouse(body: WarehouseIn, ctx=Depends(require_permission("organization.manage"))):
    db, _, tenant_id, _ = ctx
    if body.branch_id and not db.scalar(select(Branch.id).where(Branch.id == body.branch_id, Branch.tenant_id == tenant_id)):
        raise HTTPException(400, "Branch does not belong to tenant")
    warehouse = Warehouse(tenant_id=tenant_id, **body.model_dump()); db.add(warehouse)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "Warehouse code already exists")
    db.refresh(warehouse); return warehouse

@router.get("/locations", response_model=list[LocationOut])
def list_locations(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx; return list(db.scalars(select(Location).where(Location.tenant_id == tenant_id).order_by(Location.name)))

@router.post("/locations", response_model=LocationOut)
def create_location(body: LocationIn, ctx=Depends(require_permission("organization.manage"))):
    db, _, tenant_id, _ = ctx
    if not db.scalar(select(Warehouse.id).where(Warehouse.id == body.warehouse_id, Warehouse.tenant_id == tenant_id)):
        raise HTTPException(400, "Warehouse does not belong to tenant")
    location = Location(tenant_id=tenant_id, **body.model_dump()); db.add(location)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "Location code already exists in warehouse")
    db.refresh(location); return location

@router.get("/pos-terminals", response_model=list[PosOut])
def list_pos(ctx=Depends(require_permission("organization.read"))):
    db, _, tenant_id, _ = ctx; return list(db.scalars(select(PosTerminal).where(PosTerminal.tenant_id == tenant_id).order_by(PosTerminal.name)))

@router.post("/pos-terminals", response_model=PosOut)
def create_pos(body: PosIn, ctx=Depends(require_permission("organization.manage"))):
    db, _, tenant_id, _ = ctx
    if not db.scalar(select(Branch.id).where(Branch.id == body.branch_id, Branch.tenant_id == tenant_id)):
        raise HTTPException(400, "Branch does not belong to tenant")
    terminal = PosTerminal(tenant_id=tenant_id, **body.model_dump()); db.add(terminal)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409, "POS terminal code already exists")
    db.refresh(terminal); return terminal
