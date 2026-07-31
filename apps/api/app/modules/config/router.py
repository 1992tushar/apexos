"""Config router — data-driven masters: GET lists + full Settings CRUD (Phase B)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.config.schemas import (
    BrandRead,
    BusinessUnitRead,
    CategoryCreate,
    CategoryRead,
    CategoryReparent,
    CategoryUpdate,
    CompanyProfileRead,
    CompanyProfileUpdate,
    CustomerTypeRead,
    ProcurementModelRead,
    SettingRead,
    SettingUpsert,
    SimpleMasterCreate,
    SimpleMasterUpdate,
    SupplierTypeRead,
    TaxRateRead,
    TaxRateSlabCreate,
    UomConversionRead,
    UomConversionUpsert,
    UomRead,
    WarehouseCreate,
    WarehouseRead,
    WarehouseUpdate,
)
from app.modules.config.service import (
    CategoryService,
    CompanyProfileService,
    ConfigService,
    SettingService,
    TaxRateService,
    UomConversionService,
)

router = APIRouter(tags=["config"])


# --- reads ---------------------------------------------------------------


@router.get("/business-units", response_model=list[BusinessUnitRead])
def list_business_units(db: Session = Depends(get_db)):
    return ConfigService(db).business_units()


@router.get("/brands", response_model=list[BrandRead])
def list_brands(db: Session = Depends(get_db)):
    return ConfigService(db).brands()


@router.get("/procurement-models", response_model=list[ProcurementModelRead])
def list_procurement_models(db: Session = Depends(get_db)):
    return ConfigService(db).procurement_models()


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)):
    return ConfigService(db).categories()


@router.get("/uoms", response_model=list[UomRead])
def list_uoms(db: Session = Depends(get_db)):
    return ConfigService(db).uoms()


@router.get("/customer-types", response_model=list[CustomerTypeRead])
def list_customer_types(db: Session = Depends(get_db)):
    return ConfigService(db).customer_types()


@router.get("/supplier-types", response_model=list[SupplierTypeRead])
def list_supplier_types(db: Session = Depends(get_db)):
    return ConfigService(db).supplier_types()


@router.get("/warehouses", response_model=list[WarehouseRead])
def list_warehouses(db: Session = Depends(get_db)):
    return ConfigService(db).warehouses()


@router.get("/tax-rates", response_model=list[TaxRateRead])
def list_tax_rates(db: Session = Depends(get_db)):
    return ConfigService(db).tax_rates()


@router.get("/uom-conversions", response_model=list[UomConversionRead])
def list_uom_conversions(db: Session = Depends(get_db)):
    return ConfigService(db).uom_conversions()


@router.get("/settings", response_model=list[SettingRead])
def list_settings(db: Session = Depends(get_db)):
    return ConfigService(db).settings()


@router.get("/company-profile", response_model=CompanyProfileRead)
def get_company_profile(db: Session = Depends(get_db)):
    return CompanyProfileService(db).get()


@router.patch("/company-profile", response_model=CompanyProfileRead)
def update_company_profile(
    payload: CompanyProfileUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return CompanyProfileService(db).update(payload, actor_id=actor.id)


# --- simple master writes (code/name/is_active) --------------------------


@router.post("/business-units", response_model=BusinessUnitRead, status_code=201)
def create_business_unit(
    payload: SimpleMasterCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).create_master(
        "business_unit", code=payload.code, name=payload.name, actor_id=actor.id
    )


@router.patch("/business-units/{row_id}", response_model=BusinessUnitRead)
def update_business_unit(
    row_id: uuid.UUID,
    payload: SimpleMasterUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).update_master(
        "business_unit", row_id, data=payload.model_dump(exclude_unset=True), actor_id=actor.id
    )


@router.post("/brands", response_model=BrandRead, status_code=201)
def create_brand(
    payload: SimpleMasterCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).create_master(
        "brand", code=payload.code, name=payload.name, actor_id=actor.id
    )


@router.patch("/brands/{row_id}", response_model=BrandRead)
def update_brand(
    row_id: uuid.UUID,
    payload: SimpleMasterUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).update_master(
        "brand", row_id, data=payload.model_dump(exclude_unset=True), actor_id=actor.id
    )


@router.post("/procurement-models", response_model=ProcurementModelRead, status_code=201)
def create_procurement_model(
    payload: SimpleMasterCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).create_master(
        "procurement_model", code=payload.code, name=payload.name, actor_id=actor.id
    )


@router.patch("/procurement-models/{row_id}", response_model=ProcurementModelRead)
def update_procurement_model(
    row_id: uuid.UUID,
    payload: SimpleMasterUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).update_master(
        "procurement_model", row_id, data=payload.model_dump(exclude_unset=True), actor_id=actor.id
    )


@router.post("/uoms", response_model=UomRead, status_code=201)
def create_uom(
    payload: SimpleMasterCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).create_master(
        "uom", code=payload.code, name=payload.name, actor_id=actor.id
    )


@router.patch("/uoms/{row_id}", response_model=UomRead)
def update_uom(
    row_id: uuid.UUID,
    payload: SimpleMasterUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).update_master(
        "uom", row_id, data=payload.model_dump(exclude_unset=True), actor_id=actor.id
    )


@router.post("/customer-types", response_model=CustomerTypeRead, status_code=201)
def create_customer_type(
    payload: SimpleMasterCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).create_master(
        "customer_type", code=payload.code, name=payload.name, actor_id=actor.id
    )


@router.patch("/customer-types/{row_id}", response_model=CustomerTypeRead)
def update_customer_type(
    row_id: uuid.UUID,
    payload: SimpleMasterUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).update_master(
        "customer_type", row_id, data=payload.model_dump(exclude_unset=True), actor_id=actor.id
    )


@router.post("/supplier-types", response_model=SupplierTypeRead, status_code=201)
def create_supplier_type(
    payload: SimpleMasterCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).create_master(
        "supplier_type", code=payload.code, name=payload.name, actor_id=actor.id
    )


@router.patch("/supplier-types/{row_id}", response_model=SupplierTypeRead)
def update_supplier_type(
    row_id: uuid.UUID,
    payload: SimpleMasterUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).update_master(
        "supplier_type", row_id, data=payload.model_dump(exclude_unset=True), actor_id=actor.id
    )


# --- warehouses ----------------------------------------------------------


@router.post("/warehouses", response_model=WarehouseRead, status_code=201)
def create_warehouse(
    payload: WarehouseCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).create_warehouse(
        code=payload.code, name=payload.name, city=payload.city,
        state_code=payload.state_code, actor_id=actor.id,
    )


@router.patch("/warehouses/{warehouse_id}", response_model=WarehouseRead)
def update_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return ConfigService(db).update_warehouse(
        warehouse_id, data=payload.model_dump(exclude_unset=True), actor_id=actor.id
    )


# --- categories (+ reparent) --------------------------------------------


@router.post("/categories", response_model=CategoryRead, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return CategoryService(db).create(payload, actor_id=actor.id)


@router.patch("/categories/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return CategoryService(db).update(category_id, payload, actor_id=actor.id)


@router.post("/categories/{category_id}/reparent", response_model=CategoryRead)
def reparent_category(
    category_id: uuid.UUID,
    payload: CategoryReparent,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return CategoryService(db).reparent(category_id, payload.parent_category_id, actor_id=actor.id)


# --- uom conversions -----------------------------------------------------


@router.post("/uom-conversions", response_model=UomConversionRead, status_code=201)
def upsert_uom_conversion(
    payload: UomConversionUpsert,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return UomConversionService(db).upsert(payload, actor_id=actor.id)


# --- tax rate slabs (versioned) -----------------------------------------


@router.post("/tax-rates", response_model=TaxRateRead, status_code=201)
def set_tax_slab(
    payload: TaxRateSlabCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return TaxRateService(db).set_slab(payload, actor_id=actor.id)


# --- settings (key/value upsert) ----------------------------------------


@router.post("/settings", response_model=SettingRead, status_code=201)
def set_setting(
    payload: SettingUpsert,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("config.write")),
):
    return SettingService(db).set(payload, actor_id=actor.id)
