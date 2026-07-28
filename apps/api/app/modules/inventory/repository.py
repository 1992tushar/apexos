"""Inventory repository — movement writes + derived-balance reads."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.config.models import Warehouse
from app.modules.inventory.models import (
    StockMovement,
    StockReservation,
    StorageBin,
    StorageRack,
)
from app.modules.products.models import Product


class InventoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, movement: StockMovement) -> StockMovement:
        self.db.add(movement)
        self.db.flush()
        return movement

    def on_hand(self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None) -> Decimal:
        stmt = select(func.coalesce(func.sum(StockMovement.qty_delta), 0)).where(
            StockMovement.product_id == product_id,
            StockMovement.deleted_at.is_(None),
        )
        if warehouse_id is not None:
            stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
        return Decimal(self.db.scalar(stmt) or 0)

    def balances(self) -> list[tuple]:
        """(product_id, warehouse_id, qty_on_hand) grouped."""
        stmt = (
            select(
                StockMovement.product_id,
                StockMovement.warehouse_id,
                func.coalesce(func.sum(StockMovement.qty_delta), 0).label("qty"),
            )
            .where(StockMovement.deleted_at.is_(None))
            .group_by(StockMovement.product_id, StockMovement.warehouse_id)
        )
        return list(self.db.execute(stmt).all())

    def stock_rows(self) -> list[tuple]:
        """Balance rows enriched with product + warehouse display fields."""
        stmt = (
            select(
                Product.id,
                Product.sku_code,
                Product.name,
                Warehouse.id,
                Warehouse.name,
                func.coalesce(func.sum(StockMovement.qty_delta), 0).label("qty"),
                Product.reorder_level,
            )
            .join(Product, Product.id == StockMovement.product_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .where(StockMovement.deleted_at.is_(None))
            .group_by(
                Product.id,
                Product.sku_code,
                Product.name,
                Warehouse.id,
                Warehouse.name,
                Product.reorder_level,
            )
            .order_by(Product.sku_code)
        )
        return list(self.db.execute(stmt).all())

    def movements(self, product_id: uuid.UUID | None = None) -> list[StockMovement]:
        stmt = select(StockMovement).where(StockMovement.deleted_at.is_(None))
        if product_id is not None:
            stmt = stmt.where(StockMovement.product_id == product_id)
        stmt = stmt.order_by(StockMovement.occurred_at.desc()).limit(500)
        return list(self.db.scalars(stmt))

    def low_stock_products(self) -> list[tuple]:
        """(product_id, qty_on_hand, reorder_level) where on_hand < reorder_level."""
        rows = []
        prod_stmt = select(Product.id, Product.reorder_level).where(Product.deleted_at.is_(None))
        for pid, reorder in self.db.execute(prod_stmt).all():
            qty = self.on_hand(pid)
            if qty < Decimal(reorder or 0):
                rows.append((pid, qty, Decimal(reorder or 0)))
        return rows

    # --- Part 5 C1: location depth (R6.1/R6.11) and reservations (R6.5) ----

    def add_reservation(self, entry: StockReservation) -> StockReservation:
        self.db.add(entry)
        self.db.flush()
        return entry

    def bin_rows(self, warehouse_id: uuid.UUID | None = None) -> list[tuple]:
        """Bin-level balances enriched for display — ONE query for the whole page.

        Outer-joins the bin and its rack so movements with `bin_id IS NULL` (R6.3's
        pre-Part-5 history) come back as rows with a NULL bin rather than vanishing.
        That row is what the screens label "no bin recorded"; dropping it would make the
        location view silently disagree with on-hand.
        """
        stmt = (
            select(
                Product.id,
                Product.sku_code,
                Product.name,
                Warehouse.id,
                Warehouse.name,
                StorageRack.id,
                StorageRack.code,
                StorageBin.id,
                StorageBin.code,
                StorageBin.kind,
                func.coalesce(func.sum(StockMovement.qty_delta), 0).label("qty"),
            )
            .join(Product, Product.id == StockMovement.product_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .outerjoin(StorageBin, StorageBin.id == StockMovement.bin_id)
            .outerjoin(StorageRack, StorageRack.id == StorageBin.storage_rack_id)
            .where(StockMovement.deleted_at.is_(None))
            .group_by(
                Product.id,
                Product.sku_code,
                Product.name,
                Warehouse.id,
                Warehouse.name,
                StorageRack.id,
                StorageRack.code,
                StorageBin.id,
                StorageBin.code,
                StorageBin.kind,
            )
            .order_by(Warehouse.name, StorageRack.code, StorageBin.code, Product.sku_code)
        )
        if warehouse_id is not None:
            stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
        return list(self.db.execute(stmt).all())

    def qty_by_bin_kind(self, warehouse_id: uuid.UUID | None = None) -> list[tuple]:
        """(product_id, warehouse_id, bin_kind, qty) — one query behind R6.4's states.

        Unaddressed stock (`bin_id IS NULL`) counts as `stock` kind: it is sellable
        on-hand that simply has no recorded location, not a fourth state.
        """
        kind = func.coalesce(StorageBin.kind, "stock").label("kind")
        stmt = (
            select(
                StockMovement.product_id,
                StockMovement.warehouse_id,
                kind,
                func.coalesce(func.sum(StockMovement.qty_delta), 0).label("qty"),
            )
            .outerjoin(StorageBin, StorageBin.id == StockMovement.bin_id)
            .where(StockMovement.deleted_at.is_(None))
            .group_by(StockMovement.product_id, StockMovement.warehouse_id, kind)
        )
        if warehouse_id is not None:
            stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
        return list(self.db.execute(stmt).all())

    def reserved(
        self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> Decimal:
        """Outstanding reserved quantity = SUM(qty_delta) over the reservation ledger.

        RESERVE adds, RELEASE and CONSUME subtract, so the sum is what is still
        committed — no row is ever edited to "un-reserve" (R6.5/G4).
        """
        stmt = select(func.coalesce(func.sum(StockReservation.qty_delta), 0)).where(
            StockReservation.product_id == product_id,
            StockReservation.deleted_at.is_(None),
        )
        if warehouse_id is not None:
            stmt = stmt.where(StockReservation.warehouse_id == warehouse_id)
        return Decimal(self.db.scalar(stmt) or 0)

    def reserved_totals(self, warehouse_id: uuid.UUID | None = None) -> list[tuple]:
        """(product_id, warehouse_id, reserved) grouped — one query for a whole page."""
        stmt = (
            select(
                StockReservation.product_id,
                StockReservation.warehouse_id,
                func.coalesce(func.sum(StockReservation.qty_delta), 0).label("qty"),
            )
            .where(StockReservation.deleted_at.is_(None))
            .group_by(StockReservation.product_id, StockReservation.warehouse_id)
        )
        if warehouse_id is not None:
            stmt = stmt.where(StockReservation.warehouse_id == warehouse_id)
        return list(self.db.execute(stmt).all())

    def reservation_entries(
        self, product_id: uuid.UUID | None = None, *, limit: int = 200
    ) -> list[StockReservation]:
        """The ledger itself, newest first — the records an explanation links to (G11).

        Ordered by `id` as well as `occurred_at`, and that second key is load-bearing:
        `occurred_at` defaults to `func.now()`, so every entry written inside one
        transaction — a reserve and its release, or the seed's reservation and a later
        one — carries an identical timestamp and `ORDER BY occurred_at` alone leaves
        their order to the query planner. Keys are UUID v7, which is time-ordered, so
        `id DESC` breaks the tie by actual write order rather than arbitrarily.
        """
        stmt = select(StockReservation).where(StockReservation.deleted_at.is_(None))
        if product_id is not None:
            stmt = stmt.where(StockReservation.product_id == product_id)
        stmt = stmt.order_by(
            StockReservation.occurred_at.desc(), StockReservation.id.desc()
        ).limit(limit)
        return list(self.db.scalars(stmt))

    # --- Part 5 C2: valuation (R6.16) and ageing (R6.10) --------------------

    # What counts as ACQUIRING stock at a cost. Only a purchase establishes a cost basis:
    #   TRANSFER  — the same units moving between warehouses. Both halves carry a cost
    #               hint, so counting them would weight the same purchase twice.
    #   PUTAWAY   — net-zero re-addressing inside one warehouse (C1). No cost at all.
    #   ADJUSTMENT/COUNT — a correction to quantity, not a purchase at a price. Counting
    #               an upward correction at today's purchase price would drag the average
    #               toward the latest price for units that were never bought.
    #   SALE      — outbound.
    ACQUISITION_REASONS: tuple[str, ...] = ("PURCHASE",)

    # An arrival for AGEING purposes: any inbound movement except the putaway pair, whose
    # inbound half is the same stock being re-addressed and would read as a fresh arrival
    # and reset the age of everything the seed put away.
    _NOT_AN_ARRIVAL: tuple[str, ...] = ("PUTAWAY",)

    def acquisition_totals(self, product_id: uuid.UUID | None = None) -> list[tuple]:
        """(product_id, qty_acquired, cost_total_minor, purchases, first_at, last_at).

        `cost_total_minor` is SUM(qty * unit_cost_minor) as a Decimal — the weighted
        numerator. Movements with no recorded unit cost are excluded from BOTH sides, so
        they cannot silently drag the average towards zero; the count of what was excluded
        is available via `acquisitions_without_cost`.
        """
        stmt = (
            select(
                StockMovement.product_id,
                func.coalesce(func.sum(StockMovement.qty_delta), 0).label("qty"),
                func.coalesce(
                    func.sum(StockMovement.qty_delta * StockMovement.unit_cost_minor), 0
                ).label("cost_total"),
                func.count().label("purchases"),
                func.min(StockMovement.occurred_at).label("first_at"),
                func.max(StockMovement.occurred_at).label("last_at"),
            )
            .where(
                StockMovement.deleted_at.is_(None),
                StockMovement.qty_delta > 0,
                StockMovement.reason.in_(self.ACQUISITION_REASONS),
                StockMovement.unit_cost_minor.isnot(None),
            )
            .group_by(StockMovement.product_id)
        )
        if product_id is not None:
            stmt = stmt.where(StockMovement.product_id == product_id)
        return list(self.db.execute(stmt).all())

    def acquisitions_without_cost(self, product_id: uuid.UUID) -> Decimal:
        """Quantity acquired with no unit cost recorded — what the average cannot see."""
        stmt = select(func.coalesce(func.sum(StockMovement.qty_delta), 0)).where(
            StockMovement.deleted_at.is_(None),
            StockMovement.product_id == product_id,
            StockMovement.qty_delta > 0,
            StockMovement.reason.in_(self.ACQUISITION_REASONS),
            StockMovement.unit_cost_minor.is_(None),
        )
        return Decimal(self.db.scalar(stmt) or 0)

    def arrivals(self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None):
        """Inbound movements newest first — the receipt dates R6.10 ages stock from.

        Ordered by `id` as well as `occurred_at`: the timestamp defaults to `func.now()`
        and ties within a transaction (the same trap C1 hit), and UUID v7 keys are
        time-ordered so `id` breaks it by real write order.
        """
        stmt = (
            select(StockMovement)
            .where(
                StockMovement.deleted_at.is_(None),
                StockMovement.product_id == product_id,
                StockMovement.qty_delta > 0,
                StockMovement.reason.notin_(self._NOT_AN_ARRIVAL),
            )
            .order_by(StockMovement.occurred_at.desc(), StockMovement.id.desc())
        )
        if warehouse_id is not None:
            stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
        return list(self.db.scalars(stmt))

    # What counts as CONSUMING stock, i.e. real demand. Deliberately narrower than
    # "anything outbound": a transfer out is the same units moving to another warehouse,
    # putaway is C1's net-zero re-addressing, and a negative adjustment or count is a
    # correction to what was already there. Counting any of them as demand would make a
    # product look like it sells when it has only been shuffled or written down — which
    # would put it in the wrong ABC class and hide it from the dead-stock radar.
    CONSUMPTION_REASONS: tuple[str, ...] = ("SALE",)

    def consumption(self, since, product_id: uuid.UUID | None = None) -> list[tuple]:
        """(product_id, qty_consumed, movements) since a cutoff — ONE query.

        Returned as a POSITIVE quantity: outbound movements are negative in the ledger, and
        a caller reasoning about "how much sells" should not have to remember the sign.
        Feeds all three of ABC (R7.7), the dead-stock radar (R7.8) and fast/slow (R7.9),
        so those three cannot disagree about what demand means.
        """
        stmt = (
            select(
                StockMovement.product_id,
                func.coalesce(func.sum(-StockMovement.qty_delta), 0).label("qty"),
                func.count().label("movements"),
            )
            .where(
                StockMovement.deleted_at.is_(None),
                StockMovement.qty_delta < 0,
                StockMovement.reason.in_(self.CONSUMPTION_REASONS),
                StockMovement.occurred_at >= since,
            )
            .group_by(StockMovement.product_id)
        )
        if product_id is not None:
            stmt = stmt.where(StockMovement.product_id == product_id)
        return list(self.db.execute(stmt).all())

    def last_movement_at(self, product_id: uuid.UUID) -> object | None:
        """When this product last moved at all — R7.8's dead-stock radar reads this."""
        return self.db.scalar(
            select(func.max(StockMovement.occurred_at)).where(
                StockMovement.deleted_at.is_(None),
                StockMovement.product_id == product_id,
            )
        )

    def last_consumption_at(self) -> list[tuple]:
        """(product_id, last_sold_at) for every product — one query, for R7.8.

        **Deliberately the last CONSUMPTION, not the last movement of any kind.** A product
        nobody has bought for a year is dead stock even if it was counted last week; using
        `last_movement_at` would let a cycle count or a putaway make dead stock look alive,
        which is the exact failure the radar exists to catch. `last_movement_at` stays for
        callers that genuinely want "any activity".
        """
        stmt = (
            select(
                StockMovement.product_id,
                func.max(StockMovement.occurred_at).label("last_at"),
            )
            .where(
                StockMovement.deleted_at.is_(None),
                StockMovement.qty_delta < 0,
                StockMovement.reason.in_(self.CONSUMPTION_REASONS),
            )
            .group_by(StockMovement.product_id)
        )
        return list(self.db.execute(stmt).all())

    def racks(self, warehouse_id: uuid.UUID | None = None) -> list[StorageRack]:
        stmt = select(StorageRack).where(StorageRack.deleted_at.is_(None))
        if warehouse_id is not None:
            stmt = stmt.where(StorageRack.warehouse_id == warehouse_id)
        return list(self.db.scalars(stmt.order_by(StorageRack.code)))

    def bin_of_kind(self, warehouse_id: uuid.UUID, kind: str) -> StorageBin | None:
        """The first bin of a given kind in a warehouse — how R7.5 finds where in-transit
        stock sits, and R7.x finds quarantine space, without hardcoding a bin code."""
        return self.db.scalar(
            select(StorageBin)
            .join(StorageRack, StorageRack.id == StorageBin.storage_rack_id)
            .where(
                StorageRack.warehouse_id == warehouse_id,
                StorageBin.kind == kind,
                StorageBin.deleted_at.is_(None),
                StorageRack.deleted_at.is_(None),
            )
            .order_by(StorageBin.code)
        )

    def bins(self, rack_id: uuid.UUID | None = None) -> list[StorageBin]:
        stmt = select(StorageBin).where(StorageBin.deleted_at.is_(None))
        if rack_id is not None:
            stmt = stmt.where(StorageBin.storage_rack_id == rack_id)
        return list(self.db.scalars(stmt.order_by(StorageBin.code)))
