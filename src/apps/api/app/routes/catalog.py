from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalog import CatalogValidation, begin_idempotency, emit_event, finish_idempotency, normalize_code, normalize_text, utc_now, validate_minimum_quantity, validate_price, write_audit
from ..dependencies import require_permission
from ..models import (
    Barcode, Brand, Category, PriceList, Product, ProductAttributeDefinition,
    ProductAttributeValue, ProductPrice, ProductVariant, Unit,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])

class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None

class CategoryIn(BaseModel):
    name: str; code: str; description: str | None = None; parent_id: UUID | None = None; sort_order: int = 0
class CategoryPatch(BaseModel):
    name: str | None = None; description: str | None = None; parent_id: UUID | None = None; sort_order: int | None = None; status: str | None = None
class CategoryOut(ORM):
    id: UUID; tenant_id: UUID; parent_id: UUID | None; name: str; code: str; description: str | None; status: str; sort_order: int

class BrandIn(BaseModel):
    name: str; code: str | None = None; description: str | None = None
class BrandPatch(BaseModel):
    name: str | None = None; code: str | None = None; description: str | None = None; status: str | None = None
class BrandOut(ORM):
    id: UUID; tenant_id: UUID; name: str; code: str | None; description: str | None; status: str

class UnitIn(BaseModel):
    name: str; code: str; symbol: str; unit_type: str = "COUNT"; allows_fraction: bool = False; precision_scale: int = Field(default=0, ge=0, le=6)
class UnitOut(ORM):
    id: UUID; tenant_id: UUID | None; name: str; code: str; symbol: str; unit_type: str; allows_fraction: bool; precision_scale: int; is_system: bool

class ProductIn(BaseModel):
    name: str; category_id: UUID; brand_id: UUID | None = None; family_id: UUID | None = None; description: str | None = None; product_type: str = "STOCKED"; has_variants: bool = True; tax_category_id: UUID | None = None; metadata: dict[str, Any] = Field(default_factory=dict)
class ProductPatch(BaseModel):
    name: str | None = None; category_id: UUID | None = None; brand_id: UUID | None = None; family_id: UUID | None = None; description: str | None = None; status: str | None = None; has_variants: bool | None = None; tax_category_id: UUID | None = None; metadata: dict[str, Any] | None = None
class ProductOut(ORM):
    id: UUID; tenant_id: UUID; category_id: UUID; brand_id: UUID | None; family_id: UUID | None; name: str; description: str | None; product_type: str; status: str; has_variants: bool; tax_category_id: UUID | None; metadata: dict = Field(validation_alias="product_metadata")

class VariantIn(BaseModel):
    product_id: UUID; name: str; sku: str; base_unit_id: UUID; track_inventory: bool = True; allow_fractional_quantity: bool = False; costing_method: str | None = None; metadata: dict[str, Any] = Field(default_factory=dict)
class VariantPatch(BaseModel):
    name: str | None = None; base_unit_id: UUID | None = None; track_inventory: bool | None = None; allow_fractional_quantity: bool | None = None; status: str | None = None; costing_method: str | None = None; metadata: dict[str, Any] | None = None
class VariantOut(ORM):
    id: UUID; tenant_id: UUID; product_id: UUID; name: str; sku: str; base_unit_id: UUID; track_inventory: bool; allow_fractional_quantity: bool; status: str; costing_method: str | None; metadata: dict = Field(validation_alias="variant_metadata")

class BarcodeIn(BaseModel):
    variant_id: UUID; barcode: str; barcode_type: str = "OTHER"; is_primary: bool = False
class BarcodeOut(ORM):
    id: UUID; tenant_id: UUID; variant_id: UUID; barcode: str; barcode_type: str; is_primary: bool; status: str

class AttributeDefinitionIn(BaseModel):
    name: str; code: str; category_id: UUID | None = None; data_type: str; required: bool = False; options: dict[str, Any] | None = None
class AttributeDefinitionOut(ORM):
    id: UUID; tenant_id: UUID; category_id: UUID | None; name: str; code: str; data_type: str; required: bool; options: dict | None

class AttributeValueIn(BaseModel):
    variant_id: UUID; attribute_definition_id: UUID; value_text: str | None = None; value_number: Decimal | None = None; value_boolean: bool | None = None; value_date: datetime | None = None; value_json: dict[str, Any] | list[Any] | None = None
class AttributeValueOut(ORM):
    id: UUID; tenant_id: UUID; variant_id: UUID; attribute_definition_id: UUID; value_text: str | None; value_number: float | None; value_boolean: bool | None; value_date: datetime | None; value_json: dict | list | None

class PriceListIn(BaseModel):
    name: str; currency: str = "UGX"; price_type: str = "RETAIL"; effective_from: datetime; effective_to: datetime | None = None
class PriceListOut(ORM):
    id: UUID; tenant_id: UUID; name: str; currency: str; price_type: str; status: str; effective_from: datetime; effective_to: datetime | None
class ProductPriceIn(BaseModel):
    price_list_id: UUID; variant_id: UUID; price_context_id: UUID | None = None; unit_id: UUID | None = None; priority: int = 0; unit_price: Decimal = Field(ge=0); minimum_quantity: Decimal = Field(default=Decimal("1"), gt=0); effective_from: datetime; effective_to: datetime | None = None
class ProductPriceOut(ORM):
    id: UUID; tenant_id: UUID; price_list_id: UUID; variant_id: UUID; price_context_id: UUID; unit_id: UUID; priority: int; unit_price: Decimal; minimum_quantity: Decimal; effective_from: datetime; effective_to: datetime | None


def enc_cursor(value: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps({"id": str(value)}).encode()).decode()

def dec_cursor(cursor: str | None) -> UUID | None:
    if not cursor: return None
    try: return UUID(json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())["id"])
    except Exception as exc: raise HTTPException(400, "Invalid cursor") from exc

def page(stmt, model, db: Session, limit: int, cursor: str | None):
    after = dec_cursor(cursor)
    if after: stmt = stmt.where(model.id > after)
    rows = list(db.scalars(stmt.order_by(model.id).limit(limit + 1)))
    next_cursor = enc_cursor(rows[-1].id) if len(rows) > limit else None
    return rows[:limit], next_cursor

def commit_or_409(db: Session, detail: str):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail) from exc

@router.get("/categories", response_model=Page)
def categories(limit: int = Query(50, ge=1, le=100), cursor: str | None = None, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    rows, nxt = page(select(Category).where(Category.tenant_id == tenant_id, Category.deleted_at.is_(None)), Category, db, limit, cursor)
    return Page(items=[CategoryOut.model_validate(x) for x in rows], next_cursor=nxt)

@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    try:
        code = normalize_code(body.code, "Category code"); name = normalize_text(body.name, "Category name")
        if body.parent_id and not db.scalar(select(Category.id).where(Category.id == body.parent_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None))):
            raise HTTPException(400, "Parent category does not belong to tenant")
        row = Category(tenant_id=tenant_id, name=name, code=code, description=body.description, parent_id=body.parent_id, sort_order=body.sort_order)
        db.add(row); db.flush()
        write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.category.created", target_type="category", target_id=row.id)
        emit_event(db, tenant_id=tenant_id, event_type="CategoryCreated", aggregate_type="category", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "code": code, "name": name})
    except CatalogValidation as exc: db.rollback(); raise HTTPException(422, str(exc)) from exc
    commit_or_409(db, "Category code already exists for this tenant")
    db.refresh(row); return row

@router.patch("/categories/{category_id}", response_model=CategoryOut)
def patch_category(category_id: UUID, body: CategoryPatch, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(Category).where(Category.id == category_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "Category not found")
    if body.parent_id == category_id: raise HTTPException(409, "Category cannot be its own parent")
    if body.parent_id and not db.scalar(select(Category.id).where(Category.id == body.parent_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None))): raise HTTPException(400, "Parent category does not belong to tenant")
    if body.name is not None: row.name = normalize_text(body.name, "Category name")
    if body.description is not None: row.description = body.description
    if body.parent_id is not None: row.parent_id = body.parent_id
    if body.sort_order is not None: row.sort_order = body.sort_order
    if body.status is not None: row.status = normalize_code(body.status, "Status")
    db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.category.updated", target_type="category", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="CategoryUpdated", aggregate_type="category", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "status": row.status})
    commit_or_409(db, "Category update conflicts with existing data"); db.refresh(row); return row

@router.delete("/categories/{category_id}", response_model=CategoryOut)
def delete_category(category_id: UUID, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    row = db.scalar(select(Category).where(Category.id == category_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "Category not found")
    child = db.scalar(select(Category.id).where(Category.parent_id == row.id, Category.deleted_at.is_(None)))
    product = db.scalar(select(Product.id).where(Product.category_id == row.id, Product.deleted_at.is_(None)))
    if child or product: raise HTTPException(409, "Category is still referenced")
    row.deleted_at = utc_now(); row.deleted_by = actor; row.status = "INACTIVE"; db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.category.deleted", target_type="category", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="CategoryDeleted", aggregate_type="category", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id)})
    db.commit(); db.refresh(row); return row

@router.get("/brands", response_model=Page)
def brands(limit: int = Query(50, ge=1, le=100), cursor: str | None = None, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx; rows, nxt = page(select(Brand).where(Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None)), Brand, db, limit, cursor); return Page(items=[BrandOut.model_validate(x) for x in rows], next_cursor=nxt)

@router.post("/brands", response_model=BrandOut, status_code=201)
def create_brand(body: BrandIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    try: name = normalize_text(body.name, "Brand name"); code = normalize_code(body.code, "Brand code") if body.code else None
    except CatalogValidation as exc: raise HTTPException(422, str(exc)) from exc
    row = Brand(tenant_id=tenant_id, name=name, code=code, description=body.description); db.add(row); db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.brand.created", target_type="brand", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="BrandCreated", aggregate_type="brand", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "name": name, "code": code}); commit_or_409(db, "Brand code conflicts with existing data"); db.refresh(row); return row

@router.patch("/brands/{brand_id}", response_model=BrandOut)
def patch_brand(brand_id: UUID, body: BrandPatch, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx; row = db.scalar(select(Brand).where(Brand.id == brand_id, Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "Brand not found")
    try:
        if body.name is not None: row.name = normalize_text(body.name, "Brand name")
        if body.code is not None: row.code = normalize_code(body.code, "Brand code")
        if body.description is not None: row.description = body.description
        if body.status is not None: row.status = normalize_code(body.status, "Status")
    except CatalogValidation as exc: raise HTTPException(422, str(exc)) from exc
    db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.brand.updated", target_type="brand", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="BrandUpdated", aggregate_type="brand", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "status": row.status}); commit_or_409(db, "Brand update conflicts with existing data"); db.refresh(row); return row

@router.get("/units", response_model=Page)
def units(limit: int = Query(50, ge=1, le=100), cursor: str | None = None, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    stmt = select(Unit).where((Unit.tenant_id == tenant_id) | (Unit.tenant_id.is_(None)))
    rows, nxt = page(stmt, Unit, db, limit, cursor); return Page(items=[UnitOut.model_validate(x) for x in rows], next_cursor=nxt)

@router.post("/units", response_model=UnitOut, status_code=201)
def create_unit(body: UnitIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    try:
        name = normalize_text(body.name, "Unit name"); code = normalize_code(body.code, "Unit code")
        if body.allows_fraction and body.precision_scale < 1: raise CatalogValidation("Fractional units require a precision scale")
    except CatalogValidation as exc: raise HTTPException(422, str(exc)) from exc
    row = Unit(tenant_id=tenant_id, name=name, code=code, symbol=body.symbol.strip(), unit_type=normalize_code(body.unit_type, "Unit type"), allows_fraction=body.allows_fraction, precision_scale=body.precision_scale, is_system=False); db.add(row); db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.unit.created", target_type="unit", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="UnitCreated", aggregate_type="unit", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "code": code}); commit_or_409(db, "Unit code conflicts with existing data"); db.refresh(row); return row

@router.get("/products", response_model=Page)
def products(limit: int = Query(50, ge=1, le=100), cursor: str | None = None, q: str | None = Query(None, min_length=1), status_filter: str | None = None, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx; stmt = select(Product).where(Product.tenant_id == tenant_id, Product.deleted_at.is_(None))
    if q: stmt = stmt.where(Product.name.ilike(f"%{q.strip()}%"))
    if status_filter: stmt = stmt.where(Product.status == normalize_code(status_filter, "Status"))
    rows, nxt = page(stmt, Product, db, limit, cursor); return Page(items=[ProductOut.model_validate(x) for x in rows], next_cursor=nxt)

@router.get("/lookup", response_model=list[dict])
def catalog_lookup(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=50), ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    needle = q.strip()
    barcode_match = exists(select(1).select_from(Barcode).where(Barcode.variant_id == ProductVariant.id, Barcode.tenant_id == tenant_id, Barcode.status == "ACTIVE", Barcode.barcode == needle))
    rows = db.execute(
        select(ProductVariant, Product.name.label("product_name"))
        .join(Product, Product.id == ProductVariant.product_id)
        .where(
            ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None), ProductVariant.status == "ACTIVE", Product.deleted_at.is_(None),
            or_(ProductVariant.sku.ilike(f"%{needle}%"), ProductVariant.name.ilike(f"%{needle}%"), Product.name.ilike(f"%{needle}%"), barcode_match),
        ).order_by(ProductVariant.id).limit(limit)
    ).all()
    return [{"variant_id": v.id, "product_id": v.product_id, "product_name": product_name, "variant_name": v.name, "sku": v.sku} for v, product_name in rows]

@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(body: ProductIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    try:
        idem, replay = begin_idempotency(db, tenant_id=tenant_id, operation_type="catalog.product.create", key=idempotency_key, payload=body.model_dump(mode="json"))
    except CatalogValidation as exc:
        db.rollback(); raise HTTPException(409 if "different" in str(exc) else 422, str(exc)) from exc
    if replay:
        return JSONResponse(status_code=replay[0], content=replay[1])
    if not db.scalar(select(Category.id).where(Category.id == body.category_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None))): raise HTTPException(400, "Category does not belong to tenant")
    if body.brand_id and not db.scalar(select(Brand.id).where(Brand.id == body.brand_id, Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None))): raise HTTPException(400, "Brand does not belong to tenant")
    if body.family_id:
        from ..models import ProductFamily
        if not db.scalar(select(ProductFamily.id).where(ProductFamily.id == body.family_id, ProductFamily.tenant_id == tenant_id, ProductFamily.deleted_at.is_(None))): raise HTTPException(400, "Product family does not belong to tenant")
    try: name = normalize_text(body.name, "Product name"); product_type = normalize_code(body.product_type, "Product type")
    except CatalogValidation as exc: db.rollback(); raise HTTPException(422, str(exc)) from exc
    row = Product(tenant_id=tenant_id, category_id=body.category_id, brand_id=body.brand_id, family_id=body.family_id, name=name, description=body.description, product_type=product_type, has_variants=body.has_variants, tax_category_id=body.tax_category_id, product_metadata=body.metadata); db.add(row); db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.product.created", target_type="product", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="ProductCreated", aggregate_type="product", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "name": name, "category_id": str(body.category_id), "brand_id": str(body.brand_id) if body.brand_id else None});
    finish_idempotency(db, idem, status_code=201, response_body=ProductOut.model_validate(row).model_dump(mode="json"), resource_type="product", resource_id=row.id)
    db.commit(); db.refresh(row); return row

@router.patch("/products/{product_id}", response_model=ProductOut)
def patch_product(product_id: UUID, body: ProductPatch, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx; row = db.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id, Product.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "Product not found")
    if body.category_id is not None and not db.scalar(select(Category.id).where(Category.id == body.category_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None))): raise HTTPException(400, "Category does not belong to tenant")
    if body.brand_id is not None and not db.scalar(select(Brand.id).where(Brand.id == body.brand_id, Brand.tenant_id == tenant_id, Brand.deleted_at.is_(None))): raise HTTPException(400, "Brand does not belong to tenant")
    if body.family_id is not None:
        from ..models import ProductFamily
        if not db.scalar(select(ProductFamily.id).where(ProductFamily.id == body.family_id, ProductFamily.tenant_id == tenant_id, ProductFamily.deleted_at.is_(None))): raise HTTPException(400, "Product family does not belong to tenant")
    try:
        if body.name is not None: row.name = normalize_text(body.name, "Product name")
        for attr in ("category_id", "brand_id", "family_id", "description", "status", "has_variants", "tax_category_id"):
            value = getattr(body, attr)
            if value is not None: setattr(row, attr, value)
        if body.metadata is not None:
            row.product_metadata = body.metadata
        # metadata is a public API field; product_metadata is the ORM-safe attribute.
    except CatalogValidation as exc: raise HTTPException(422, str(exc)) from exc
    db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.product.updated", target_type="product", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="ProductUpdated", aggregate_type="product", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "status": row.status}); db.commit(); db.refresh(row); return row

@router.delete("/products/{product_id}", response_model=ProductOut)
def delete_product(product_id: UUID, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx; row = db.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id, Product.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "Product not found")
    row.deleted_at = utc_now(); row.deleted_by = actor; row.status = "INACTIVE"; db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.product.deleted", target_type="product", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="ProductDeleted", aggregate_type="product", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id)}); db.commit(); db.refresh(row); return row

@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: UUID, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    row = db.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id, Product.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "Product not found")
    return row

@router.get("/products/{product_id}/variants", response_model=list[VariantOut])
def product_variants(product_id: UUID, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    if not db.scalar(select(Product.id).where(Product.id == product_id, Product.tenant_id == tenant_id, Product.deleted_at.is_(None))): raise HTTPException(404, "Product not found")
    return list(db.scalars(select(ProductVariant).where(ProductVariant.product_id == product_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None)).order_by(ProductVariant.id)))

@router.post("/variants", response_model=VariantOut, status_code=201)
def create_variant(body: VariantIn, idempotency_key: str | None = Header(None, alias="Idempotency-Key"), ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    try:
        idem, replay = begin_idempotency(db, tenant_id=tenant_id, operation_type="catalog.variant.create", key=idempotency_key, payload=body.model_dump(mode="json"))
    except CatalogValidation as exc:
        db.rollback(); raise HTTPException(409 if "different" in str(exc) else 422, str(exc)) from exc
    if replay:
        return JSONResponse(status_code=replay[0], content=replay[1])
    if not db.scalar(select(Product.id).where(Product.id == body.product_id, Product.tenant_id == tenant_id, Product.deleted_at.is_(None))): raise HTTPException(400, "Product does not belong to tenant")
    unit = db.scalar(select(Unit).where(Unit.id == body.base_unit_id, (Unit.tenant_id == tenant_id) | (Unit.tenant_id.is_(None))))
    if not unit: raise HTTPException(400, "Unit does not belong to tenant")
    try: name = normalize_text(body.name, "Variant name"); sku = normalize_code(body.sku, "SKU")
    except CatalogValidation as exc: db.rollback(); raise HTTPException(422, str(exc)) from exc
    if body.allow_fractional_quantity and not unit.allows_fraction: db.rollback(); raise HTTPException(422, "Variant cannot allow fractional quantity with a non-fractional base unit")
    row = ProductVariant(tenant_id=tenant_id, product_id=body.product_id, name=name, sku=sku, base_unit_id=body.base_unit_id, track_inventory=body.track_inventory, allow_fractional_quantity=body.allow_fractional_quantity, costing_method=body.costing_method, variant_metadata=body.metadata); db.add(row); db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.variant.created", target_type="product_variant", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="ProductVariantCreated", aggregate_type="product_variant", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "product_id": str(body.product_id), "sku": sku});
    finish_idempotency(db, idem, status_code=201, response_body=VariantOut.model_validate(row).model_dump(mode="json"), resource_type="product_variant", resource_id=row.id)
    commit_or_409(db, "SKU already exists for this tenant"); db.refresh(row); return row

@router.patch("/variants/{variant_id}", response_model=VariantOut)
def patch_variant(variant_id: UUID, body: VariantPatch, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx; row = db.scalar(select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "Variant not found")
    if body.base_unit_id is not None:
        unit = db.scalar(select(Unit).where(Unit.id == body.base_unit_id, (Unit.tenant_id == tenant_id) | (Unit.tenant_id.is_(None))))
        if not unit: raise HTTPException(400, "Unit does not belong to tenant")
        if row.allow_fractional_quantity and not unit.allows_fraction: raise HTTPException(422, "Variant cannot use a non-fractional base unit")
    try:
        if body.name is not None: row.name = normalize_text(body.name, "Variant name")
        for attr in ("base_unit_id", "track_inventory", "allow_fractional_quantity", "status", "costing_method"):
            value = getattr(body, attr)
            if value is not None: setattr(row, attr, value)
        if body.metadata is not None:
            row.variant_metadata = body.metadata
        # metadata is a public API field; variant_metadata is the ORM-safe attribute.
        unit2 = db.scalar(select(Unit).where(Unit.id == row.base_unit_id, (Unit.tenant_id == tenant_id) | (Unit.tenant_id.is_(None))))
        if row.allow_fractional_quantity and (not unit2 or not unit2.allows_fraction): raise CatalogValidation("Variant cannot allow fractional quantity with a non-fractional base unit")
    except CatalogValidation as exc: raise HTTPException(422, str(exc)) from exc
    db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.variant.updated", target_type="product_variant", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="ProductVariantUpdated", aggregate_type="product_variant", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "sku": row.sku, "status": row.status}); commit_or_409(db, "Variant update conflicts with existing data"); db.refresh(row); return row

@router.get("/variants/{variant_id}", response_model=VariantOut)
def get_variant(variant_id: UUID, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    row = db.scalar(select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "Variant not found")
    return row

@router.get("/skus/{sku}", response_model=VariantOut)
def lookup_sku(sku: str, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    value = sku.strip().upper()
    row = db.scalar(select(ProductVariant).where(ProductVariant.tenant_id == tenant_id, ProductVariant.sku == value, ProductVariant.status == "ACTIVE", ProductVariant.deleted_at.is_(None)))
    if not row: raise HTTPException(404, "SKU not found")
    return row

@router.get("/barcodes/{barcode}", response_model=BarcodeOut)
def lookup_barcode(barcode: str, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx; value = barcode.strip()
    row = db.scalar(select(Barcode).where(Barcode.tenant_id == tenant_id, Barcode.barcode == value, Barcode.status == "ACTIVE").limit(1))
    if not row: raise HTTPException(404, "Barcode not found")
    return row

@router.post("/barcodes", response_model=BarcodeOut, status_code=201)
def create_barcode(body: BarcodeIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx; barcode = body.barcode.strip()
    if not barcode: raise HTTPException(422, "Barcode cannot be empty")
    variant = db.scalar(select(ProductVariant).where(ProductVariant.id == body.variant_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None), ProductVariant.status == "ACTIVE"))
    if not variant: raise HTTPException(400, "Variant does not belong to tenant or is inactive")
    row = Barcode(tenant_id=tenant_id, variant_id=body.variant_id, barcode=barcode, barcode_type=normalize_code(body.barcode_type, "Barcode type"), is_primary=body.is_primary); db.add(row); db.flush()
    if body.is_primary: db.query(Barcode).filter(Barcode.variant_id == body.variant_id, Barcode.tenant_id == tenant_id, Barcode.id != row.id).update({Barcode.is_primary: False}, synchronize_session=False)
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.barcode.created", target_type="barcode", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="BarcodeCreated", aggregate_type="barcode", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "variant_id": str(body.variant_id), "barcode": barcode}); commit_or_409(db, "Barcode already belongs to another active catalog identity"); db.refresh(row); return row

@router.get("/attribute-definitions", response_model=list[AttributeDefinitionOut])
def attribute_definitions(ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    return list(db.scalars(select(ProductAttributeDefinition).where(ProductAttributeDefinition.tenant_id == tenant_id).order_by(ProductAttributeDefinition.code)))

@router.get("/attribute-values/{variant_id}", response_model=list[AttributeValueOut])
def attribute_values(variant_id: UUID, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    if not db.scalar(select(ProductVariant.id).where(ProductVariant.id == variant_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None))): raise HTTPException(404, "Variant not found")
    return list(db.scalars(select(ProductAttributeValue).where(ProductAttributeValue.tenant_id == tenant_id, ProductAttributeValue.variant_id == variant_id).order_by(ProductAttributeValue.attribute_definition_id)))

@router.post("/attribute-definitions", response_model=AttributeDefinitionOut, status_code=201)
def create_attribute_definition(body: AttributeDefinitionIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    if body.category_id and not db.scalar(select(Category.id).where(Category.id == body.category_id, Category.tenant_id == tenant_id, Category.deleted_at.is_(None))): raise HTTPException(400, "Category does not belong to tenant")
    data_type = normalize_code(body.data_type, "Attribute data type")
    allowed = {"TEXT","NUMBER","BOOLEAN","DATE","SELECT","MULTI_SELECT"}
    if data_type not in allowed: raise HTTPException(422, f"Unsupported attribute data type: {data_type}")
    row = ProductAttributeDefinition(tenant_id=tenant_id, category_id=body.category_id, name=normalize_text(body.name,"Attribute name"), code=normalize_code(body.code,"Attribute code"), data_type=data_type, required=body.required, options=body.options); db.add(row); db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.attribute_definition.created", target_type="product_attribute_definition", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="ProductAttributeDefinitionCreated", aggregate_type="product_attribute_definition", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "code": row.code}); commit_or_409(db, "Attribute definition code already exists for this tenant"); db.refresh(row); return row

@router.post("/attribute-values", response_model=AttributeValueOut, status_code=201)
def create_attribute_value(body: AttributeValueIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    variant = db.scalar(select(ProductVariant).where(ProductVariant.id == body.variant_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None)))
    definition = db.scalar(select(ProductAttributeDefinition).where(ProductAttributeDefinition.id == body.attribute_definition_id, ProductAttributeDefinition.tenant_id == tenant_id))
    if not variant or not definition: raise HTTPException(400, "Variant and attribute definition must belong to tenant")
    provided = [body.value_text is not None, body.value_number is not None, body.value_boolean is not None, body.value_date is not None, body.value_json is not None]
    if sum(provided) != 1: raise HTTPException(422, "Exactly one attribute value representation is required")
    compatible = {"TEXT":"value_text","NUMBER":"value_number","BOOLEAN":"value_boolean","DATE":"value_date","SELECT":"value_text","MULTI_SELECT":"value_json"}
    field = compatible.get(definition.data_type)
    if not field or getattr(body, field) is None: raise HTTPException(422, f"Value does not match attribute data type {definition.data_type}")
    if definition.data_type == "SELECT" and definition.options:
        choices = definition.options.get("choices", [])
        if body.value_text not in choices: raise HTTPException(422, "Value is not an allowed choice")
    if definition.data_type == "MULTI_SELECT" and definition.options:
        choices = set(definition.options.get("choices", [])); values = set(body.value_json if isinstance(body.value_json, list) else []); 
        if not values.issubset(choices): raise HTTPException(422, "One or more values are not allowed choices")
    row = ProductAttributeValue(tenant_id=tenant_id, variant_id=body.variant_id, attribute_definition_id=body.attribute_definition_id, value_text=body.value_text, value_number=body.value_number, value_boolean=body.value_boolean, value_date=body.value_date, value_json=body.value_json); db.add(row); db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.attribute_value.created", target_type="product_attribute_value", target_id=row.id); db.commit(); db.refresh(row); return row

@router.get("/price-lists", response_model=list[PriceListOut])
def price_lists(ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx; return list(db.scalars(select(PriceList).where(PriceList.tenant_id == tenant_id).order_by(PriceList.effective_from.desc(), PriceList.id)))

@router.post("/price-lists", response_model=PriceListOut, status_code=201)
def create_price_list(body: PriceListIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    if body.effective_to and body.effective_to <= body.effective_from: raise HTTPException(422, "effective_to must be after effective_from")
    row = PriceList(tenant_id=tenant_id, name=normalize_text(body.name,"Price list name"), currency=normalize_code(body.currency,"Currency"), price_type=normalize_code(body.price_type,"Price type"), effective_from=body.effective_from, effective_to=body.effective_to); db.add(row); db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.price_list.created", target_type="price_list", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="PriceListCreated", aggregate_type="price_list", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "name": row.name, "currency": row.currency}); commit_or_409(db, "Price list conflicts with existing data"); db.refresh(row); return row

@router.get("/prices", response_model=list[ProductPriceOut])
def prices(variant_id: UUID | None = None, price_list_id: UUID | None = None, ctx=Depends(require_permission("catalog.read"))):
    db, _, tenant_id, _ = ctx
    stmt = select(ProductPrice).where(ProductPrice.tenant_id == tenant_id)
    if variant_id: stmt = stmt.where(ProductPrice.variant_id == variant_id)
    if price_list_id: stmt = stmt.where(ProductPrice.price_list_id == price_list_id)
    return list(db.scalars(stmt.order_by(ProductPrice.effective_from.desc(), ProductPrice.minimum_quantity)))

@router.post("/prices", response_model=ProductPriceOut, status_code=201)
def create_price(body: ProductPriceIn, ctx=Depends(require_permission("catalog.manage"))):
    db, actor, tenant_id, _ = ctx
    price_list = db.scalar(select(PriceList).where(PriceList.id == body.price_list_id, PriceList.tenant_id == tenant_id, PriceList.status == "ACTIVE")); variant = db.scalar(select(ProductVariant).where(ProductVariant.id == body.variant_id, ProductVariant.tenant_id == tenant_id, ProductVariant.deleted_at.is_(None)))
    if not price_list or not variant: raise HTTPException(400, "Price list and variant must belong to tenant")
    from ..models import PriceContext
    context_id = body.price_context_id or db.scalar(select(PriceContext.id).where(PriceContext.tenant_id == tenant_id, PriceContext.status == "ACTIVE").order_by(PriceContext.priority.desc(), PriceContext.id).limit(1))
    unit_id = body.unit_id or variant.base_unit_id
    if not context_id: raise HTTPException(400, "A price context is required")
    if not db.scalar(select(PriceContext.id).where(PriceContext.id == context_id, PriceContext.tenant_id == tenant_id, PriceContext.status == "ACTIVE")): raise HTTPException(400, "Price context does not belong to tenant")
    if not db.scalar(select(Unit.id).where(Unit.id == unit_id, or_(Unit.tenant_id == tenant_id, Unit.tenant_id.is_(None)))): raise HTTPException(400, "Price unit does not belong to tenant or system scope")
    if body.effective_to and body.effective_to <= body.effective_from: raise HTTPException(422, "effective_to must be after effective_from")
    validate_price(body.unit_price); validate_minimum_quantity(body.minimum_quantity)
    overlap = db.scalar(select(ProductPrice.id).where(
        ProductPrice.tenant_id == tenant_id, ProductPrice.price_context_id == context_id, ProductPrice.price_list_id == body.price_list_id, ProductPrice.variant_id == body.variant_id, ProductPrice.unit_id == unit_id, ProductPrice.minimum_quantity == body.minimum_quantity, ProductPrice.priority == body.priority,
        ProductPrice.effective_from < (body.effective_to or datetime.max.replace(tzinfo=timezone.utc)),
        or_(ProductPrice.effective_to.is_(None), ProductPrice.effective_to > body.effective_from),
    ).limit(1))
    if overlap: raise HTTPException(409, "Overlapping price interval exists for this variant, price context, unit, quantity tier and priority")
    row = ProductPrice(tenant_id=tenant_id, price_list_id=body.price_list_id, variant_id=body.variant_id, price_context_id=context_id, unit_id=unit_id, priority=body.priority, unit_price=body.unit_price, minimum_quantity=body.minimum_quantity, effective_from=body.effective_from, effective_to=body.effective_to); db.add(row); db.flush(); write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="catalog.product_price.created", target_type="product_price", target_id=row.id); emit_event(db, tenant_id=tenant_id, event_type="ProductPriceCreated", aggregate_type="product_price", aggregate_id=row.id, actor_user_id=actor, payload={"id": str(row.id), "variant_id": str(body.variant_id), "price_list_id": str(body.price_list_id)}); commit_or_409(db, "Overlapping or duplicate product price is not permitted"); db.refresh(row); return row
