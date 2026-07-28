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

from decimal import Decimal

from sqlalchemy import select

from app.modules.inventory.models import StorageRack
from app.modules.inventory.schemas import BinCreate, RackCreate, ReservationCreate
from app.modules.inventory.service import (
    InventoryService,
    LocationService,
    ReservationService,
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

    db.flush()
    return {
        "warehouses": len(warehouses),
        "racks": len(warehouses) * len(_RACKS),
        "bins": sum(len(b) for b in bins_by_warehouse.values()),
        "products_put_away": put_away,
        "reserved": str(reserved.qty_delta) if reserved else None,
    }
