"""Config read + write schemas (Pydantic v2)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BusinessUnitRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class BrandRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class ProcurementModelRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class CategoryRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    business_unit_id: uuid.UUID
    parent_category_id: uuid.UUID | None = None
    procurement_model_id: uuid.UUID | None
    sort_order: int
    is_active: bool


class UomRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class CustomerTypeRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class SupplierTypeRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool


class WarehouseRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    city: str | None
    state_code: str | None
    is_active: bool


class TaxRateRead(_ORM):
    id: uuid.UUID
    code: str
    name: str
    rate_bps: int
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool


class UomConversionRead(_ORM):
    id: uuid.UUID
    from_uom_id: uuid.UUID
    to_uom_id: uuid.UUID
    factor: Decimal


class SettingRead(_ORM):
    id: uuid.UUID
    key: str
    value: Any
    value_type: str
    description: str | None = None
    business_unit_id: uuid.UUID | None = None


# --- Write schemas (Phase B: full Settings CRUD) -------------------------


class SimpleMasterCreate(BaseModel):
    """Create payload for code/name masters (brand, uom, customer/supplier type…)."""

    code: str = Field(min_length=1, max_length=24)
    name: str = Field(min_length=1, max_length=120)


class SimpleMasterUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=24)
    name: str = Field(min_length=1, max_length=120)
    city: str | None = None
    state_code: str | None = None


class WarehouseUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    state_code: str | None = None
    is_active: bool | None = None


class CategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=4)
    name: str = Field(min_length=1, max_length=120)
    business_unit_id: uuid.UUID | None = None
    procurement_model_id: uuid.UUID | None = None
    parent_category_id: uuid.UUID | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    procurement_model_id: uuid.UUID | None = None
    business_unit_id: uuid.UUID | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryReparent(BaseModel):
    """Set (or clear, when null) a category's parent. Enforces the BU rollup and
    rejects cycles."""

    parent_category_id: uuid.UUID | None = None


class UomConversionUpsert(BaseModel):
    from_uom_id: uuid.UUID
    to_uom_id: uuid.UUID
    factor: Decimal = Field(gt=0)


class TaxRateSlabCreate(BaseModel):
    """Add a new versioned GST slab. Any open row for the same code is closed
    (history is never edited, D3 spirit)."""

    code: str = Field(min_length=1, max_length=24)
    name: str = Field(min_length=1, max_length=60)
    rate_bps: int = Field(ge=0, le=10000)
    valid_from: date | None = None


class SettingUpsert(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: Any
    value_type: str = "string"
    description: str | None = None
    business_unit_id: uuid.UUID | None = None
