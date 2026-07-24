"""Org / config masters (canonical §5 · data-driven types, D2).

Global type masters carry no `business_unit_id`; `category` rolls up to a BU
(real FK). Money as `*_minor` (D5); GST rate as integer basis points (`rate_bps`).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class BusinessUnit(Base, EntityMixin):
    __tablename__ = "business_unit"

    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Brand(Base, EntityMixin):
    __tablename__ = "brand"

    code: Mapped[str] = mapped_column(String(3), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProcurementModel(Base, EntityMixin):
    __tablename__ = "procurement_model"

    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Category(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "category"

    procurement_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("procurement_model.id"), nullable=True
    )
    parent_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("category.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(4), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Uom(Base, EntityMixin):
    __tablename__ = "uom"

    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UomConversion(Base, EntityMixin):
    __tablename__ = "uom_conversion"

    from_uom_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("uom.id"), nullable=False
    )
    to_uom_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("uom.id"), nullable=False
    )
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)


class CustomerType(Base, EntityMixin):
    __tablename__ = "customer_type"

    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SupplierType(Base, EntityMixin):
    __tablename__ = "supplier_type"

    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Warehouse(Base, EntityMixin):
    __tablename__ = "warehouse"

    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TaxRate(Base, EntityMixin):
    __tablename__ = "tax_rate"

    code: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NumberSequence(Base, EntityMixin):
    """Atomic per-BU, per-month document counter (SO-/INV-/PO-YYYYMM-#####)."""

    __tablename__ = "number_sequence"

    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("business_unit.id"), nullable=True
    )
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYYMM
    counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Setting(Base, EntityMixin):
    __tablename__ = "setting"

    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("business_unit.id"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, default="string")
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
