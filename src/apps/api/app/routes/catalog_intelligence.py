from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..catalog import CatalogValidation, emit_event, normalize_code, normalize_text, utc_now, write_audit
from ..dependencies import require_permission
from ..models import (
    AttributeSet, AttributeSetDefinition, Brand, Category, PriceContext, PriceList,
    Product, ProductAttributeDefinition, ProductAttributeValue, ProductFamily,
    ProductPrice, ProductVariant, SupplierProductPrice, Unit, UnitConversion, VariantUnit,
)

router = APIRouter(prefix="/catalog", tags=["catalog-intelligence"])

class FamilyIn(BaseModel):
    name: str
    code: str
    description: str | None = None
    parent_id: UUID | None = None
    sort_order: int = 0

class AttributeSetIn(BaseModel):
    name: str
    code: str
    description: str | None = None

class AttributeSetAttachIn(BaseModel):
    attribute_definition_id: UUID
    sort_order: int = 0
    required_override: bool | None = None

class PriceContextIn(BaseModel):
    name: str
    code: str
    currency: str = "UGX"
    sales_channel: str | None = "GENERAL"
    customer_segment: str | None = None
    branch_id: UUID | None = None
    priority: int = 0

class VariantUnitIn(BaseModel):
    variant_id: UUID
    unit_id: UUID
    purpose: str = "SELLING"
    base_quantity: Decimal = Field(gt=0)
    is_default: bool = False

class UnitConversionIn(BaseModel):
    from_unit_id: UUID
    to_unit_id: UUID
    factor: Decimal = Field(gt=0)
    rounding_scale: int = Field(default=6, ge=0, le=12)

class SupplierPriceIn(BaseModel):
    supplier_id: UUID
    variant_id: UUID
    supplier_sku: str | None = None
    unit_id: UUID
    unit_cost: Decimal = Field(ge=0)
    minimum_quantity: Decimal = Field(default=Decimal("1"), gt=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    currency: str = "UGX"
    effective_from: datetime
    effective_to: datetime | None = None

class CatalogWorkspace(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None
    totals: dict[str, int]
    references: dict[str, list[dict[str, Any]]]


def _cursor_id(cursor: str | None) -> UUID | None:
    if not cursor:
        return None
    try:
        return UUID(cursor)
    except ValueError as exc:
        raise HTTPException(400, "Invalid cursor") from exc


def _commit(db: Session, detail: str = "Catalog operation conflicts with existing data"):
    from sqlalchemy.exc import IntegrityError
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail) from exc


@router.get("/workspace", response_model=CatalogWorkspace)
def catalog_workspace(
    q: str | None = Query(None),
    brand_id: UUID | None = None,
    category_id: UUID | None = None,
    family_id: UUID | None = None,
    status_filter: str | None = None,
    price_context_id: UUID | None = None,
    limit: int = Query(30, ge=1, le=100),
    cursor: str | None = None,
    ctx=Depends(require_permission("catalog.read")),
):
    """Single read model for the catalog screen. Avoids reference-data waterfalls and N+1 variant calls."""
    db, _, tenant_id, _ = ctx
    after = _cursor_id(cursor)
    stmt = (
        select(Product, Brand.name.label("brand_name"), Category.name.label("category_name"), ProductFamily.name.label("family_name"))
        .outerjoin(Brand, (Brand.id == Product.brand_id) & (Brand.tenant_id == tenant_id))
        .join(Category, (Category.id == Product.category_id) & (Category.tenant_id == tenant_id))
        .outerjoin(ProductFamily, (ProductFamily.id == Product.family_id) & (ProductFamily.tenant_id == tenant_id))
        .where(Product.tenant_id == tenant_id, Product.deleted_at.is_(None))
    )
    if after:
        stmt = stmt.where(Product.id > after)
    if q:
        needle = q.strip()
        if needle:
            like = f"%{needle}%"
            variant_exists = select(ProductVariant.id).where(
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.product_id == Product.id,
                ProductVariant.deleted_at.is_(None),
                or_(ProductVariant.name.ilike(like), ProductVariant.sku.ilike(like)),
            ).exists()
            stmt = stmt.where(or_(Product.name.ilike(like), Brand.name.ilike(like), variant_exists))
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if family_id:
        stmt = stmt.where(Product.family_id == family_id)
    if status_filter:
        stmt = stmt.where(Product.status == normalize_code(status_filter, "Status"))

    rows = db.execute(stmt.order_by(Product.id).limit(limit + 1)).all()
    more = len(rows) > limit
    rows = rows[:limit]
    ids = [row[0].id for row in rows]
    variants_by_product: dict[UUID, list[dict[str, Any]]] = {pid: [] for pid in ids}
    if ids:
        variant_rows = db.execute(
            select(ProductVariant, Unit.code.label("unit_code"))
            .join(Unit, Unit.id == ProductVariant.base_unit_id)
            .where(ProductVariant.tenant_id == tenant_id, ProductVariant.product_id.in_(ids), ProductVariant.deleted_at.is_(None))
            .order_by(ProductVariant.product_id, ProductVariant.id)
        ).all()
        for v, unit_code in variant_rows:
            if len(variants_by_product[v.product_id]) < 8:
                variants_by_product[v.product_id].append({"id": str(v.id), "name": v.name, "sku": v.sku, "status": v.status, "unit_code": unit_code, "track_inventory": v.track_inventory})

    items=[]
    for product, brand_name, category_name, family_name in rows:
        variants=variants_by_product.get(product.id, [])
        items.append({
            "id": str(product.id), "tenant_id": str(product.tenant_id), "name": product.name,
            "description": product.description, "product_type": product.product_type, "status": product.status,
            "has_variants": product.has_variants, "brand_id": str(product.brand_id) if product.brand_id else None,
            "brand_name": brand_name, "category_id": str(product.category_id), "category_name": category_name,
            "family_id": str(product.family_id) if product.family_id else None, "family_name": family_name,
            "variant_count": len(variants), "variants": variants,
        })

    # Reference data is intentionally bundled once. These are stable relative to transactional inventory reads.
    categories = db.execute(select(Category.id, Category.name, Category.code).where(Category.tenant_id==tenant_id, Category.deleted_at.is_(None)).order_by(Category.name).limit(500)).all()
    brands = db.execute(select(Brand.id, Brand.name, Brand.code).where(Brand.tenant_id==tenant_id, Brand.deleted_at.is_(None)).order_by(Brand.name).limit(500)).all()
    families = db.execute(select(ProductFamily.id, ProductFamily.name, ProductFamily.code).where(ProductFamily.tenant_id==tenant_id, ProductFamily.deleted_at.is_(None)).order_by(ProductFamily.name).limit(500)).all()
    units = db.execute(select(Unit.id, Unit.name, Unit.code, Unit.symbol, Unit.unit_type, Unit.is_system).where((Unit.tenant_id==tenant_id)|(Unit.tenant_id.is_(None))).order_by(Unit.name).limit(500)).all()
    price_lists = db.execute(select(PriceList.id, PriceList.name, PriceList.currency, PriceList.price_type, PriceList.status).where(PriceList.tenant_id==tenant_id).order_by(PriceList.name).limit(500)).all()
    contexts = db.execute(select(PriceContext.id, PriceContext.name, PriceContext.code, PriceContext.currency, PriceContext.sales_channel, PriceContext.customer_segment, PriceContext.priority, PriceContext.status).where(PriceContext.tenant_id==tenant_id).order_by(PriceContext.priority.desc(), PriceContext.name).limit(500)).all()
    totals = {"products": db.scalar(select(func.count()).select_from(Product).where(Product.tenant_id==tenant_id, Product.deleted_at.is_(None))) or 0,
              "brands": len(brands), "categories": len(categories), "families": len(families)}
    return CatalogWorkspace(
        items=items,
        next_cursor=str(rows[-1][0].id) if more else None,
        totals=totals,
        references={
            "categories":[{"id":str(x.id),"name":x.name,"code":x.code} for x in categories],
            "brands":[{"id":str(x.id),"name":x.name,"code":x.code} for x in brands],
            "families":[{"id":str(x.id),"name":x.name,"code":x.code} for x in families],
            "units":[{"id":str(x.id),"name":x.name,"code":x.code,"symbol":x.symbol,"unit_type":x.unit_type,"is_system":x.is_system} for x in units],
            "price_lists":[{"id":str(x.id),"name":x.name,"currency":x.currency,"price_type":x.price_type,"status":x.status} for x in price_lists],
            "price_contexts":[{"id":str(x.id),"name":x.name,"code":x.code,"currency":x.currency,"sales_channel":x.sales_channel,"customer_segment":x.customer_segment,"priority":x.priority,"status":x.status} for x in contexts],
        }
    )

@router.get("/families")
def families(ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.execute(select(ProductFamily).where(ProductFamily.tenant_id==tenant_id, ProductFamily.deleted_at.is_(None)).order_by(ProductFamily.sort_order, ProductFamily.name)).scalars())

@router.post("/families", status_code=201)
def create_family(body: FamilyIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    if body.parent_id and not db.scalar(select(ProductFamily.id).where(ProductFamily.id==body.parent_id, ProductFamily.tenant_id==tenant_id, ProductFamily.deleted_at.is_(None))):
        raise HTTPException(400,"Parent family does not belong to tenant")
    row=ProductFamily(tenant_id=tenant_id,name=normalize_text(body.name,"Family name"),code=normalize_code(body.code,"Family code"),description=body.description,parent_id=body.parent_id,sort_order=body.sort_order)
    db.add(row); db.flush(); write_audit(db,tenant_id=tenant_id,actor_user_id=actor,action="catalog.family.created",target_type="product_family",target_id=row.id); emit_event(db,tenant_id=tenant_id,event_type="ProductFamilyCreated",aggregate_type="product_family",aggregate_id=row.id,actor_user_id=actor,payload={"id":str(row.id),"code":row.code}); _commit(db,"Family code already exists for this tenant"); db.refresh(row); return row

@router.get("/attribute-sets")
def attribute_sets(ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(AttributeSet).where(AttributeSet.tenant_id==tenant_id).order_by(AttributeSet.name)))

@router.post("/attribute-sets", status_code=201)
def create_attribute_set(body: AttributeSetIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _=ctx
    row=AttributeSet(tenant_id=tenant_id,name=normalize_text(body.name,"Attribute set name"),code=normalize_code(body.code,"Attribute set code"),description=body.description)
    db.add(row); db.flush(); write_audit(db,tenant_id=tenant_id,actor_user_id=actor,action="catalog.attribute_set.created",target_type="attribute_set",target_id=row.id); emit_event(db,tenant_id=tenant_id,event_type="AttributeSetCreated",aggregate_type="attribute_set",aggregate_id=row.id,actor_user_id=actor,payload={"id":str(row.id),"code":row.code}); _commit(db,"Attribute set code already exists"); db.refresh(row); return row

@router.post("/attribute-sets/{attribute_set_id}/definitions", status_code=201)
def attach_attribute_definition(attribute_set_id: UUID, body: AttributeSetAttachIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _=ctx
    aset=db.scalar(select(AttributeSet).where(AttributeSet.id==attribute_set_id,AttributeSet.tenant_id==tenant_id))
    definition=db.scalar(select(ProductAttributeDefinition).where(ProductAttributeDefinition.id==body.attribute_definition_id,ProductAttributeDefinition.tenant_id==tenant_id))
    if not aset or not definition: raise HTTPException(400,"Attribute set and definition must belong to tenant")
    row=AttributeSetDefinition(tenant_id=tenant_id,attribute_set_id=attribute_set_id,attribute_definition_id=body.attribute_definition_id,sort_order=body.sort_order,required_override=body.required_override)
    db.add(row); db.flush(); write_audit(db,tenant_id=tenant_id,actor_user_id=actor,action="catalog.attribute_set.definition_attached",target_type="attribute_set_definition",target_id=row.id); _commit(db,"Attribute definition is already attached to this set"); db.refresh(row); return row

@router.get("/price-contexts")
def price_contexts(ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _=ctx
    return list(db.scalars(select(PriceContext).where(PriceContext.tenant_id==tenant_id).order_by(PriceContext.priority.desc(),PriceContext.name)))

@router.post("/price-contexts", status_code=201)
def create_price_context(body: PriceContextIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _=ctx
    if body.branch_id and not db.scalar(select(PriceContext.id).where(False)):
        # Branch ownership is enforced by FK plus the tenant-scoped branch check below.
        from ..models import Branch
        if not db.scalar(select(Branch.id).where(Branch.id==body.branch_id,Branch.tenant_id==tenant_id)): raise HTTPException(400,"Branch does not belong to tenant")
    row=PriceContext(tenant_id=tenant_id,name=normalize_text(body.name,"Price context name"),code=normalize_code(body.code,"Price context code"),currency=normalize_code(body.currency,"Currency"),sales_channel=body.sales_channel,customer_segment=body.customer_segment,branch_id=body.branch_id,priority=body.priority)
    db.add(row); db.flush(); write_audit(db,tenant_id=tenant_id,actor_user_id=actor,action="catalog.price_context.created",target_type="price_context",target_id=row.id); emit_event(db,tenant_id=tenant_id,event_type="PriceContextCreated",aggregate_type="price_context",aggregate_id=row.id,actor_user_id=actor,payload={"id":str(row.id),"code":row.code}); _commit(db,"Price context code already exists"); db.refresh(row); return row

@router.post("/variant-units", status_code=201)
def create_variant_unit(body: VariantUnitIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _=ctx
    variant=db.scalar(select(ProductVariant).where(ProductVariant.id==body.variant_id,ProductVariant.tenant_id==tenant_id,ProductVariant.deleted_at.is_(None)))
    unit=db.scalar(select(Unit.id).where(Unit.id==body.unit_id,or_(Unit.tenant_id==tenant_id,Unit.tenant_id.is_(None))))
    if not variant or not unit: raise HTTPException(400,"Variant and unit must belong to tenant or system scope")
    if body.purpose not in {"SELLING","PURCHASING","STOCKING"}: raise HTTPException(422,"Unsupported unit purpose")
    row=VariantUnit(tenant_id=tenant_id,variant_id=body.variant_id,unit_id=body.unit_id,purpose=normalize_code(body.purpose,"Purpose"),base_quantity=body.base_quantity,is_default=body.is_default)
    db.add(row); db.flush(); write_audit(db,tenant_id=tenant_id,actor_user_id=actor,action="catalog.variant_unit.created",target_type="variant_unit",target_id=row.id); _commit(db,"Variant unit configuration conflicts with existing data"); db.refresh(row); return row

@router.post("/unit-conversions", status_code=201)
def create_unit_conversion(body: UnitConversionIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _=ctx
    for uid in (body.from_unit_id,body.to_unit_id):
        if not db.scalar(select(Unit.id).where(Unit.id==uid,or_(Unit.tenant_id==tenant_id,Unit.tenant_id.is_(None)))): raise HTTPException(400,"Unit does not belong to tenant or system scope")
    if body.from_unit_id==body.to_unit_id: raise HTTPException(422,"Conversion must use different units")
    row=UnitConversion(tenant_id=tenant_id,from_unit_id=body.from_unit_id,to_unit_id=body.to_unit_id,factor=body.factor,rounding_scale=body.rounding_scale)
    db.add(row); db.flush(); write_audit(db,tenant_id=tenant_id,actor_user_id=actor,action="catalog.unit_conversion.created",target_type="unit_conversion",target_id=row.id); _commit(db,"Unit conversion already exists"); db.refresh(row); return row

@router.post("/supplier-prices", status_code=201)
def create_supplier_price(body: SupplierPriceIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _=ctx
    if body.effective_to and body.effective_to <= body.effective_from: raise HTTPException(422,"effective_to must be after effective_from")
    variant=db.scalar(select(ProductVariant).where(ProductVariant.id==body.variant_id,ProductVariant.tenant_id==tenant_id,ProductVariant.deleted_at.is_(None)))
    if not variant: raise HTTPException(400,"Variant does not belong to tenant")
    if not db.scalar(select(Unit.id).where(Unit.id==body.unit_id,or_(Unit.tenant_id==tenant_id,Unit.tenant_id.is_(None)))): raise HTTPException(400,"Unit does not belong to tenant or system scope")
    row=SupplierProductPrice(tenant_id=tenant_id,supplier_id=body.supplier_id,variant_id=body.variant_id,supplier_sku=body.supplier_sku,unit_id=body.unit_id,unit_cost=body.unit_cost,minimum_quantity=body.minimum_quantity,lead_time_days=body.lead_time_days,currency=normalize_code(body.currency,"Currency"),effective_from=body.effective_from,effective_to=body.effective_to)
    db.add(row); db.flush(); write_audit(db,tenant_id=tenant_id,actor_user_id=actor,action="catalog.supplier_price.created",target_type="supplier_product_price",target_id=row.id); emit_event(db,tenant_id=tenant_id,event_type="SupplierProductPriceCreated",aggregate_type="supplier_product_price",aggregate_id=row.id,actor_user_id=actor,payload={"id":str(row.id),"variant_id":str(body.variant_id)}); _commit(db,"Supplier price conflicts with existing data"); db.refresh(row); return row
