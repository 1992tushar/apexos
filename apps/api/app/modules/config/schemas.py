"""Config read schemas (Pydantic v2)."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


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
    is_active: bool
