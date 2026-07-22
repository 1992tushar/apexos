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


# --- Warehouse operations (Phase B) --------------------------------------


class WarehouseStockRow(BaseModel):
    """A product's on-hand quantity within a single warehouse."""

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    qty_on_hand: Decimal
    reorder_level: Decimal
    is_low: bool


class StockTransferCreate(BaseModel):
    """Move stock between two warehouses (posts two stock movements)."""

    product_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    note: str | None = None


class StockTransferResult(BaseModel):
    product_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    qty: Decimal
    from_on_hand: Decimal
    to_on_hand: Decimal


class StockAdjustmentCreate(BaseModel):
    """Manual correction: a signed delta applied to on-hand at a warehouse.

    `reason` is `ADJUSTMENT` (default) or `COUNT`.
    """

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    qty_delta: Decimal = Field(description="Signed change; may be negative")
    reason: str = "ADJUSTMENT"
    note: str | None = None


class StockCountCreate(BaseModel):
    """Cycle count: reconcile on-hand to a physically counted quantity. The
    service posts the difference as a `COUNT` movement (delta = counted − on_hand)."""

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    counted_qty: Decimal = Field(ge=0)
    note: str | None = None


class StockAdjustmentResult(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    qty_delta: Decimal
    reason: str
    on_hand: Decimal
