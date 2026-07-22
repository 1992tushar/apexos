"""Config repositories — thin read helpers over the type masters."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.config.models import (
    Brand,
    BusinessUnit,
    Category,
    CustomerType,
    ProcurementModel,
    Setting,
    SupplierType,
    TaxRate,
    Uom,
    UomConversion,
    Warehouse,
)


def _live(model):
    return select(model).where(model.deleted_at.is_(None))


class ConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def business_units(self) -> list[BusinessUnit]:
        return list(self.db.scalars(_live(BusinessUnit).order_by(BusinessUnit.name)))

    def brands(self) -> list[Brand]:
        return list(self.db.scalars(_live(Brand).order_by(Brand.name)))

    def procurement_models(self) -> list[ProcurementModel]:
        return list(self.db.scalars(_live(ProcurementModel).order_by(ProcurementModel.name)))

    def categories(self) -> list[Category]:
        return list(self.db.scalars(_live(Category).order_by(Category.sort_order, Category.name)))

    def uoms(self) -> list[Uom]:
        return list(self.db.scalars(_live(Uom).order_by(Uom.name)))

    def customer_types(self) -> list[CustomerType]:
        return list(self.db.scalars(_live(CustomerType).order_by(CustomerType.name)))

    def supplier_types(self) -> list[SupplierType]:
        return list(self.db.scalars(_live(SupplierType).order_by(SupplierType.name)))

    def warehouses(self) -> list[Warehouse]:
        return list(self.db.scalars(_live(Warehouse).order_by(Warehouse.name)))

    def tax_rates(self) -> list[TaxRate]:
        return list(self.db.scalars(_live(TaxRate).order_by(TaxRate.rate_bps)))

    def uom_conversions(self) -> list[UomConversion]:
        return list(self.db.scalars(_live(UomConversion).order_by(UomConversion.created_at)))

    def settings(self) -> list[Setting]:
        return list(self.db.scalars(_live(Setting).order_by(Setting.key)))
