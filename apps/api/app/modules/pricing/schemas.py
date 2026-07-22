"""Pricing schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SellingPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    customer_id: uuid.UUID | None
    customer_type_id: uuid.UUID | None
    price_minor: int


class PurchasePriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    supplier_id: uuid.UUID | None
    price_minor: int
    valid_from: datetime
    valid_to: datetime | None = None


class PurchasePriceCreate(BaseModel):
    product_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    price_minor: int = Field(ge=0)
