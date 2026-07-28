"""Part 5 C1's seed section: location depth and one live reservation (R6.14).

What this adds, and why each piece has to be here rather than in a test:

* **Racks and bins in every seeded warehouse**, including one `transit` and one
  `quarantine` bin, so R6.4's four states are all non-zero on the demo screens rather
  than three zeros and a total.
* **Putaway of the stock that already exists.** Every movement written before Part 5 has
  `bin_id IS NULL` (R6.3), so with no putaway the location view would show the entire
  catalogue under "no bin recorded" and R6.11's rollup would have nothing to roll up.
  A putaway is a NET-ZERO PAIR through `record_movement` — out of the unaddressed pool,
  into a bin — never an UPDATE of the original row, which G4 forbids. On-hand is
  therefore untouched by this section; only its *address* changes.
* **One reservation against a real sales order**, so `/inventory` shows available < on
  hand for a reason the founder can click through to.

Deliberately NOT here: the in-transit transfer awaiting receipt and the cycle counts
(R7.14) belong to C3's operations work, and the movement history for weighted-average
cost (R6.14's last clause) belongs to C2. Each section seeds what its own checkpoint
made real.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.modules.inventory.models import StockMovement, StorageRack
from app.modules.inventory.schemas import (
    BinCreate,
    CountClose,
    CountEntry,
    CountOpen,
    CountRecord,
    RackCreate,
    ReservationCreate,
    TransferDispatch,
)
from app.modules.inventory.service import (
    CycleCountService,
    InventoryService,
    LocationService,
    ReservationService,
    StockTransferService,
)
from app.seed.helpers import SeedContext

# Two racks per warehouse, and the bins under them. The last two carry a `kind` other
# than `stock`, which is how R6.4's in-transit and quarantine states are addressed.
_RACKS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    ("A", "Aisle A — fast movers", (("A-01", "stock"), ("A-02", "stock"))),
    ("B", "Aisle B — bulk and holds", (("B-01", "stock"), ("B-TR", "transit"),
                                       ("B-QA", "quarantine"))),
)

# How much of a product's unaddressed balance to put away into the first stock bin.
# A fraction, not all of it: real warehouses have stock that nobody has addressed yet,
# and R6.3's "no bin recorded" bucket should be visible on the demo screens rather than
# being a code path with no data behind it.
_PUTAWAY_SHARE = Decimal("0.6")
_PUTAWAY_PRODUCTS = 12


def seed_locations(ctx: SeedContext) -> dict | None:
    """Give every seeded warehouse a rack/bin tree, put stock away, reserve some.

    Idempotent by its own emptiness check: if any rack exists, this has already run.
    """
    db = ctx.db
    if db.scalar(select(StorageRack).limit(1)) is not None:
        return None

    from app.modules.config.models import Warehouse

    warehouses = list(
        db.scalars(
            select(Warehouse)
            .where(Warehouse.deleted_at.is_(None))
            .order_by(Warehouse.code)
        )
    )
    if not warehouses:
        return None

    locations = LocationService(db)
    inventory = InventoryService(db)
    bins_by_warehouse: dict[str, list] = {}

    for warehouse in warehouses:
        created_bins = []
        for rack_code, rack_name, bin_specs in _RACKS:
            rack = locations.create_rack(
                RackCreate(warehouse_id=warehouse.id, code=rack_code, name=rack_name),
                actor_id=ctx.actor_id,
            )
            for bin_code, kind in bin_specs:
                created_bins.append(
                    locations.create_bin(
                        BinCreate(storage_rack_id=rack.id, code=bin_code, kind=kind),
                        actor_id=ctx.actor_id,
                    )
                )
        bins_by_warehouse[str(warehouse.id)] = created_bins

    # --- putaway: address some of the stock that predates Part 5 -------------
    put_away = 0
    for row in inventory.stock():
        if put_away >= _PUTAWAY_PRODUCTS:
            break
        if row.qty_on_hand <= 0:
            continue
        stock_bins = [
            b for b in bins_by_warehouse.get(str(row.warehouse_id), []) if b.kind == "stock"
        ]
        if not stock_bins:
            continue
        # Spread across the stock bins so the rollup has more than one leaf per rack.
        target = stock_bins[put_away % len(stock_bins)]
        qty = (row.qty_on_hand * _PUTAWAY_SHARE).quantize(Decimal("1"))
        if qty <= 0:
            continue
        inventory.record_movement(
            product_id=row.product_id, warehouse_id=row.warehouse_id,
            bin_id=None, qty_delta=-qty, reason="PUTAWAY",
            ref_type="storage_bin", ref_id=target.id, actor_id=ctx.actor_id,
        )
        inventory.record_movement(
            product_id=row.product_id, warehouse_id=row.warehouse_id,
            bin_id=target.id, qty_delta=qty, reason="PUTAWAY",
            ref_type="storage_bin", ref_id=target.id, actor_id=ctx.actor_id,
        )
        put_away += 1

    # --- one reservation against a real order (R6.14) ------------------------
    reserved = None
    from app.modules.sales.models import SalesOrder

    order = db.scalar(
        select(SalesOrder)
        .where(SalesOrder.deleted_at.is_(None))
        .order_by(SalesOrder.created_at)
        .limit(1)
    )
    for row in inventory.stock():
        available = inventory.available(row.product_id, row.warehouse_id)
        if available < Decimal("10"):
            continue
        reserved = ReservationService(db).reserve(
            ReservationCreate(
                product_id=row.product_id,
                warehouse_id=row.warehouse_id,
                qty=Decimal("8"),
                ref_type="sales_order" if order is not None else None,
                ref_id=order.id if order is not None else None,
                note="Committed to a confirmed order",
            ),
            actor_id=ctx.actor_id,
        )
        break

    aged = _seed_aged_purchases(ctx, warehouses[0])
    operations = _seed_operations(ctx, warehouses)

    db.flush()
    return {
        "warehouses": len(warehouses),
        "racks": len(warehouses) * len(_RACKS),
        "bins": sum(len(b) for b in bins_by_warehouse.values()),
        "products_put_away": put_away,
        "reserved": str(reserved.qty_delta) if reserved else None,
        "aged_purchases": aged,
        "operations": operations,
    }


def _seed_operations(ctx: SeedContext, warehouses) -> dict | None:
    """R7.14 — a transfer awaiting receipt, plus a variance count and a clean one.

    All three exist so the screens have something real to show: an in-transit transfer is
    outstanding work, a variance count proves an adjustment was posted, and a zero-variance
    count proves the far more common case where nothing needed posting (R7.2). Without the
    last one, the "no adjustment" path is a code branch with no demo data behind it.
    """
    db = ctx.db
    if len(warehouses) < 2:
        return None

    inventory = InventoryService(db)
    transfers = StockTransferService(db)
    counts = CycleCountService(db)

    # An in-transit transfer, LEFT UNRECEIVED on purpose.
    in_flight = None
    if not transfers.in_transit():
        for row in inventory.stock():
            if row.warehouse_id != warehouses[0].id or row.qty_on_hand < 20:
                continue
            in_flight = transfers.dispatch(
                TransferDispatch(
                    product_id=row.product_id,
                    from_warehouse_id=warehouses[0].id,
                    to_warehouse_id=warehouses[1].id,
                    qty=Decimal("6"),
                    note="Awaiting receipt at the destination",
                ),
                actor_id=ctx.actor_id,
            )
            break

    # Two closed count sheets: one that found a discrepancy, one that did not.
    variance_sheet = clean_sheet = None
    if not counts.sheets():
        candidates = [
            r
            for r in inventory.stock()
            if r.warehouse_id == warehouses[0].id and r.qty_on_hand >= 10
        ][:2]
        if len(candidates) == 2:
            short, exact = candidates

            variance_sheet = counts.open(
                CountOpen(warehouse_id=warehouses[0].id, product_ids=[short.product_id]),
                actor_id=ctx.actor_id,
            )
            counts.record(
                variance_sheet.id,
                CountRecord(entries=[
                    CountEntry(
                        product_id=short.product_id,
                        counted_qty=short.qty_on_hand - Decimal("2"),
                    )
                ]),
                actor_id=ctx.actor_id,
            )
            variance_sheet = counts.close(
                variance_sheet.id,
                CountClose(reason="Quarterly count — two short on the shelf"),
                actor_id=ctx.actor_id,
            )

            clean_sheet = counts.open(
                CountOpen(warehouse_id=warehouses[0].id, product_ids=[exact.product_id]),
                actor_id=ctx.actor_id,
            )
            # Re-read on-hand: the sheet above may have adjusted a different product, but
            # reading it fresh keeps this correct if the seed order ever changes.
            counted = inventory.on_hand(exact.product_id, warehouses[0].id)
            counts.record(
                clean_sheet.id,
                CountRecord(entries=[
                    CountEntry(product_id=exact.product_id, counted_qty=counted)
                ]),
                actor_id=ctx.actor_id,
            )
            clean_sheet = counts.close(
                clean_sheet.id,
                CountClose(reason="Quarterly count — shelf matched the system"),
                actor_id=ctx.actor_id,
            )

    return {
        "in_transit": in_flight.transfer_no if in_flight else None,
        "variance_count": (
            f"{variance_sheet.count_no} ({variance_sheet.adjustments_posted} posted)"
            if variance_sheet
            else None
        ),
        "clean_count": (
            f"{clean_sheet.count_no} ({clean_sheet.adjustments_posted} posted)"
            if clean_sheet
            else None
        ),
    }


# Backdated purchases: (days ago, quantity, unit cost in minor units). Three arrivals at
# three different prices and three different ages, which is what makes BOTH C2 figures
# non-trivial (R6.14) — a weighted average that differs from every individual price, and
# a balance that spans more than one age bucket.
#
# The ages straddle the bucket edges deliberately: 200 and 120 days are "over 90", 75 is
# "61–90", 10 is "0–30". A seed where everything arrived today makes ageing untestable and
# leaves R7.8's dead-stock radar with nothing to find in C3.
_AGED_PURCHASES: tuple[tuple[int, str, int], ...] = (
    (200, "40", 9000),
    (120, "30", 10500),
    (75, "20", 11000),
    (10, "10", 12500),
)


def _seed_aged_purchases(ctx: SeedContext, warehouse) -> dict | None:
    """Give two products a real purchase history, backdated (R6.14, R6.10, R6.16).

    Written through `record_movement(occurred_at=…)`, which stamps history **at insert
    time**. The seed never UPDATEs a movement to change its date — `stock_movement` is an
    append-only ledger and G4 forbids it.
    """
    db = ctx.db
    inventory = InventoryService(db)

    # Two products that already carry stock, so the aged arrivals add to a real balance
    # rather than creating an orphan one.
    candidates = [r for r in inventory.stock() if r.qty_on_hand > 0][:2]
    if not candidates:
        return None

    now = datetime.now(UTC)
    seeded: list[str] = []
    for row in candidates:
        already = db.scalar(
            select(StockMovement).where(
                StockMovement.product_id == row.product_id,
                StockMovement.ref_type == "seed_aged_purchase",
            )
        )
        if already is not None:
            continue
        for days_ago, qty, unit_cost_minor in _AGED_PURCHASES:
            inventory.record_movement(
                product_id=row.product_id,
                warehouse_id=warehouse.id,
                qty_delta=Decimal(qty),
                reason="PURCHASE",
                ref_type="seed_aged_purchase",
                unit_cost_minor=unit_cost_minor,
                occurred_at=now - timedelta(days=days_ago),
                actor_id=ctx.actor_id,
            )
        seeded.append(row.sku_code)

    return {"products": seeded, "arrivals_each": len(_AGED_PURCHASES)} if seeded else None
