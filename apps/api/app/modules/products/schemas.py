"""Product schemas."""
from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    sku_code: str | None = None
    name: str
    category_id: uuid.UUID
    brand_id: uuid.UUID
    uom_id: uuid.UUID
    procurement_model_id: uuid.UUID | None = None
    default_tax_rate_id: uuid.UUID | None = None
    specification: str | None = None
    launch_phase: str | None = None
    reorder_level: Decimal = Decimal("0")
    selling_price_minor: int | None = None
    purchase_price_minor: int | None = None
    business_unit_id: uuid.UUID | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku_code: str
    name: str
    category_id: uuid.UUID
    category_name: str | None = None
    brand_id: uuid.UUID
    brand_name: str | None = None
    specification: str | None = None
    uom_id: uuid.UUID
    uom_code: str | None = None
    procurement_model_id: uuid.UUID | None = None
    procurement_model_name: str | None = None
    launch_phase: str | None = None
    status: str
    selling_price_minor: int | None = None
    purchase_price_minor: int | None = None
    stock_on_hand: Decimal = Decimal("0")


class ProductPage(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int
