"""Inventory schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StockRow(BaseModel):
    product_id: uuid.UUID
    sku_code: str
    product_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    qty_on_hand: Decimal
    reorder_level: Decimal
    is_low: bool


class MovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    qty_delta: Decimal
    reason: str
    ref_type: str | None
    ref_id: uuid.UUID | None
    occurred_at: datetime
