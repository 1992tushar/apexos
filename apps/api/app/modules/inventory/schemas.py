"""Inventory schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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


# --- Part 5 C1: locations, states, reservations ---------------------------


class BinCreate(BaseModel):
    """A new addressable bin inside a rack (R6.1)."""

    storage_rack_id: uuid.UUID
    code: str = Field(min_length=1, max_length=24)
    name: str | None = None
    kind: str = "stock"


class RackCreate(BaseModel):
    """A new rack inside a warehouse (R6.1)."""

    warehouse_id: uuid.UUID
    code: str = Field(min_length=1, max_length=24)
    name: str | None = None


class BinStockRow(BaseModel):
    """One product's quantity in one bin — the leaf of R6.11's rollup.

    `bin_id` is None for the synthetic "unaddressed" row that carries stock recorded
    against a warehouse before Part 5, or by any caller that did not name a bin (R6.3).
    """

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    rack_id: uuid.UUID | None
    rack_code: str | None
    bin_id: uuid.UUID | None
    bin_code: str | None
    bin_kind: str
    qty_on_hand: Decimal

    @property
    def location(self) -> str:
        """`WH-01 / A / A-01`, or a plain statement that no bin was recorded."""
        if self.bin_id is None:
            return "no bin recorded"
        return f"{self.rack_code} / {self.bin_code}"


class LocationRollupRow(BaseModel):
    """A rack's or warehouse's total, summed from its bins (R6.11). `children` are
    the level below — bins under a rack, racks under a warehouse."""

    level: str  # "warehouse" | "rack" | "bin"
    id: uuid.UUID | None
    code: str
    name: str
    kind: str | None = None
    qty_on_hand: Decimal
    children: list[LocationRollupRow] = Field(default_factory=list)


class StockStateRow(BaseModel):
    """R6.4's four states for one product in one warehouse, every one of them derived
    (G7) — from the movement ledger, the reservation ledger and each bin's kind.

    `available` is what can still be sold: sellable on-hand minus outstanding
    reservations. It can be driven negative by over-reservation, which is a real
    condition and is shown rather than clamped.
    """

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    on_hand: Decimal
    reserved: Decimal
    in_transit: Decimal
    quarantined: Decimal
    available: Decimal


class ReservationCreate(BaseModel):
    """Commit stock to something (R6.6). Part 7 calls this at sales-order confirm."""

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    bin_id: uuid.UUID | None = None
    ref_type: str | None = None
    ref_id: uuid.UUID | None = None
    note: str | None = None


class ReservationResult(BaseModel):
    """What the reservation ledger says after the entry was appended."""

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    qty_delta: Decimal
    reason: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal


# `LocationRollupRow.children` is the same model, so the annotation cannot resolve while
# the class body is still executing. Rebuilding here is the Pydantic v2 fix.
LocationRollupRow.model_rebuild()
