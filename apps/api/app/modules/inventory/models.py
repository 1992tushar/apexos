"""Inventory ledger (D3): append-only stock_movement. NO stored balance table —
on-hand is SUM(qty_delta).

Part 5 C1 adds location depth and a second append-only ledger:

* `StorageRack` / `StorageBin` — warehouse → rack → bin (R6.1). Stock is addressed to a
  bin via `StockMovement.bin_id`, which is **nullable on purpose** (R6.3): NULL means
  "at this warehouse, with no recorded bin". Backfilling the ~400 movements that predate
  this part would mean UPDATE-ing an append-only ledger, which G4 forbids, and it would
  invent a physical fact — which bin that stock sat in — that nobody ever recorded.
  Screens bucket NULL as "unaddressed" rather than hiding it.
* `StockReservation` — the reservation ledger (R6.5). A reservation is an APPEND-ONLY
  ENTRY, never a flag: there is deliberately no boolean `reserved` column anywhere.
  Reserved is SUM(qty_delta) over the ledger, so `available = on_hand - reserved` and
  both stay derived (G7).

The four reported stock states (R6.4) are all derived from these two ledgers plus
`StorageBin.kind` — nothing about a state is stored mutably:

    available  on_hand in `stock`-kind bins (and unaddressed), minus reserved
    reserved   SUM(stock_reservation.qty_delta)
    in transit on_hand in `transit`-kind bins
    damaged    on_hand in `quarantine`-kind bins

That is also the mechanism R7.5's two-step transfer uses in C3: OUT of a stock bin, IN to
a transit bin, then transit → the destination's stock bin, so stock is never invisible
mid-flight.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, EntityMixin

# What a bin is for. `stock` is sellable space; the other two are how R6.4's states are
# addressed without inventing a mutable state column (G7).
BIN_KINDS: tuple[str, ...] = ("stock", "transit", "quarantine")


class StorageRack(Base, EntityMixin):
    """A rack (aisle / shelving run) inside a warehouse — the middle of R6.1's
    warehouse → rack → bin. Carries no stock itself; its totals roll up from its
    bins (R6.11)."""

    __tablename__ = "storage_rack"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("warehouse.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StorageBin(Base, EntityMixin):
    """The addressable location stock actually sits in (R6.1).

    `kind` is what makes R6.4's four states derivable — see the module docstring. It is
    a property of the *place*, not of the stock, so moving stock between kinds is an
    ordinary pair of ledger movements rather than a status edit.
    """

    __tablename__ = "storage_bin"

    storage_rack_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("storage_rack.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="stock")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StockMovement(Base, EntityMixin):
    __tablename__ = "stock_movement"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("warehouse.id"), nullable=False, index=True
    )
    # R6.3: nullable by decision, not by omission. NULL = "at this warehouse, bin not
    # recorded" — every movement written before Part 5, and any caller that does not
    # address one. See the module docstring for why backfilling would break G4.
    bin_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("storage_bin.id"), nullable=True, index=True
    )
    qty_delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    unit_cost_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StockReservation(Base, EntityMixin):
    """R6.5 — reservation as a ledger, not a flag.

    One append-only signed entry per event: `RESERVE` adds, `RELEASE` (cancelled) and
    `CONSUME` (fulfilled) subtract. Outstanding reserved quantity is SUM(qty_delta), so
    a reservation reduces *available* without touching *on-hand* — nothing in
    `stock_movement` moves when stock is committed, which is the whole point.

    Rows are never updated or deleted (G4). Part 7's R9.8/R9.9 calls
    `ReservationService.reserve` / `.release` / `.consume` and adds no second mechanism.
    """

    __tablename__ = "stock_reservation"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("warehouse.id"), nullable=False, index=True
    )
    bin_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("storage_bin.id"), nullable=True, index=True
    )
    # Signed: + on RESERVE, − on RELEASE and CONSUME. Sum > 0 means still committed.
    qty_delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
