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

    `reason` is the movement code — `ADJUSTMENT` (default) or `COUNT`. **`note` is the
    human reason and R7.4 makes it mandatory**: stock does not change by itself, and an
    adjustment nobody can explain later is exactly what an audit trail is for. A
    whitespace-only note is refused, not accepted and stored blank.
    """

    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    qty_delta: Decimal = Field(description="Signed change; may be negative")
    reason: str = "ADJUSTMENT"
    note: str = Field(min_length=1, description="Why the stock changed (R7.4, mandatory)")
    bin_id: uuid.UUID | None = None


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


# --- Part 5 C3b: health thresholds (R7.7–R7.10) ---------------------------
#
# Every one of these is stated on screen. R7.7 and R7.8 make that acceptance, and a
# classification whose cut-off you cannot see is a number you cannot argue with. They live
# here as constants for the same reason AGE_BUCKETS does: the screen, the explanation and
# the test all read one source.

# Cumulative share of consumption value, in order. **Upper bound INCLUSIVE** — a product
# landing exactly on 80% is class A, matching how AGE_BUCKETS treats its edges. The last
# entry must be 1.0 or a product at the very tail falls out of every class.
ABC_CLASSES: tuple[tuple[str, Decimal], ...] = (
    ("A", Decimal("0.80")),
    ("B", Decimal("0.95")),
    ("C", Decimal("1.00")),
)

# The window ABC and the fast/slow split measure demand over.
MOVEMENT_WINDOW_DAYS = 365

# No sale in strictly MORE than this many days, with stock still on hand, is dead stock.
# Exactly this many days is NOT yet dead — the boundary is stated and tested.
DEAD_STOCK_DAYS = 90

# At or below this many units sold per month is a slow mover; above it is a fast mover.
SLOW_MOVER_MAX_PER_MONTH = 5


class AbcRow(BaseModel):
    """One product's ABC classification (R7.7). `abc_class` is derived, never stored."""

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    qty_consumed: Decimal
    value_minor: int
    cumulative_share_bps: int
    abc_class: str
    window_days: int


class DeadStockRow(BaseModel):
    """Stock on hand that has not sold inside the window (R7.8).

    `days_since_sale` is None when the product has NEVER sold — the deadest case, not a
    missing value, and it sorts first rather than being hidden.
    """

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    qty_on_hand: Decimal
    value_minor: int | None
    days_since_sale: int | None
    window_days: int

    @property
    def never_sold(self) -> bool:
        return self.days_since_sale is None


class MovementRow(BaseModel):
    """How fast a product actually moves (R7.9), with the numbers behind it."""

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    qty_consumed: Decimal
    movements: int
    per_month: Decimal
    window_days: int
    is_fast: bool

    @property
    def label(self) -> str:
        return "fast" if self.is_fast else "slow"


class LowStockRow(BaseModel):
    """Below the reorder level, on AVAILABLE rather than on-hand (R7.10)."""

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    available: Decimal
    on_hand: Decimal
    reserved: Decimal
    reorder_level: Decimal

    @property
    def shortfall(self) -> Decimal:
        return self.reorder_level - self.available


# --- Part 5 C3: operations (R7.1–R7.5) ------------------------------------


class TransferDispatch(BaseModel):
    """Send stock on its way (R7.5's first step)."""

    product_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    note: str | None = None


class TransferRead(BaseModel):
    """A transfer document, in flight or landed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transfer_no: str
    product_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    qty: Decimal
    status: str
    dispatched_at: datetime
    received_at: datetime | None
    note: str | None

    @property
    def is_in_transit(self) -> bool:
        return self.status == "in_transit"


class CountOpen(BaseModel):
    """Open a count sheet for a warehouse (R7.1).

    `product_ids` empty means "every product with a balance here" — the ordinary case for
    a full count. Naming products is how a spot count of a few lines is done.
    """

    warehouse_id: uuid.UUID
    product_ids: list[uuid.UUID] = Field(default_factory=list)
    limit: int | None = None


class CountEntry(BaseModel):
    """One counted line."""

    product_id: uuid.UUID
    counted_qty: Decimal = Field(ge=0)


class CountRecord(BaseModel):
    entries: list[CountEntry]


class CountClose(BaseModel):
    """Close a sheet and post its adjustments. R7.4's reason is mandatory."""

    reason: str = Field(min_length=1)


class CountLineRead(BaseModel):
    product_id: uuid.UUID
    sku_code: str
    product_name: str
    system_qty: Decimal
    counted_qty: Decimal | None

    @property
    def variance(self) -> Decimal | None:
        """Counted − system. None while the line is uncounted — which is NOT a variance
        of minus-everything, and closing must skip it rather than zero the stock."""
        if self.counted_qty is None:
            return None
        return self.counted_qty - self.system_qty

    @property
    def is_counted(self) -> bool:
        return self.counted_qty is not None


class CountDetail(BaseModel):
    id: uuid.UUID
    count_no: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    status: str
    counted_at: datetime | None
    reason: str | None
    lines: list[CountLineRead]
    # How many adjustment movements closing this sheet actually wrote. Zero is the
    # correct, expected answer for a sheet that matched (R7.2) — not an error.
    adjustments_posted: int = 0

    @property
    def variance_lines(self) -> list[CountLineRead]:
        return [ln for ln in self.lines if ln.variance not in (None, Decimal(0))]

    @property
    def counted_lines(self) -> int:
        return sum(1 for ln in self.lines if ln.is_counted)


# --- Part 5 C2: valuation (R6.16) and ageing (R6.10) ----------------------

# Age buckets, in reading order. Each entry is (key, label, upper_bound_days) and the
# UPPER BOUND IS INCLUSIVE — stock exactly 30 days old is "0–30 days", not "31–60".
# The last bucket's bound is None, meaning "everything older". R6.10 requires the
# boundary behaviour to be defined; this tuple IS the definition, and a test asserts it.
AGE_BUCKETS: tuple[tuple[str, str, int | None], ...] = (
    ("fresh", "0–30 days", 30),
    ("thirty", "31–60 days", 60),
    ("sixty", "61–90 days", 90),
    ("stale", "over 90 days", None),
)


class StockValueRow(BaseModel):
    """One product's on-hand quantity and what it is worth (R6.16).

    `cost_basis_minor` is None when no purchase with a recorded cost exists — the figure
    is then genuinely unknown and the screen says so rather than showing zero (G11).
    """

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    qty_on_hand: Decimal
    cost_basis_minor: int | None
    value_minor: int | None

    @property
    def is_known(self) -> bool:
        return self.cost_basis_minor is not None


class AgeBucketRow(BaseModel):
    """How much of a product's balance falls in one age bucket."""

    key: str
    label: str
    qty: Decimal


class AgeingRow(BaseModel):
    """A product's on-hand balance split across the age buckets (R6.10).

    APPROXIMATE, and the approximation is named on screen: without lot tracking the
    balance cannot be tied to specific receipts, so it is attributed to the most recent
    arrivals first — the assumption that older stock leaves first. `unattributed` is the
    balance that no arrival covers (it predates the ledger, or arrived without a
    recorded movement); it is reported, not folded into the oldest bucket.
    """

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    qty_on_hand: Decimal
    buckets: list[AgeBucketRow]
    oldest_days: int | None
    unattributed: Decimal

    @property
    def stale_qty(self) -> Decimal:
        """Everything in the last bucket — what R7.8's dead-stock radar will consume."""
        return next(
            (b.qty for b in self.buckets if b.key == AGE_BUCKETS[-1][0]), Decimal(0)
        )
