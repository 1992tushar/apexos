"""Config router — GET list endpoints for the data-driven masters."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.config.schemas import (
    BrandRead,
    BusinessUnitRead,
    CategoryRead,
    CustomerTypeRead,
    ProcurementModelRead,
    SupplierTypeRead,
    TaxRateRead,
    UomRead,
    WarehouseRead,
)
from app.modules.config.service import ConfigService

router = APIRouter(tags=["config"])


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
