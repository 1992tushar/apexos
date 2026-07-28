"""Inventory service — record movements, derive on-hand, list low stock.

`InventoryService.record_movement` is the ONLY writer of `stock_movement` (D3);
Sales/Procurement and the Phase-B warehouse operations all go through it.
`StockTransferService` and `StockAdjustmentService` are the state-changing verbs
that each emit one `activity_log` row (D10); balances stay derived from the ledger.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.money import qty_text as _qty_text
from app.modules.activity.service import ActivityService
from app.modules.config.models import Warehouse
from app.modules.config.service import allocate_document_number, default_business_unit
from app.modules.inventory.models import (
    BIN_KINDS,
    StockCount,
    StockCountLine,
    StockMovement,
    StockReservation,
    StockTransfer,
    StorageBin,
    StorageRack,
)
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    BinStockRow,
    CountDetail,
    CountLineRead,
    LocationRollupRow,
    ReservationResult,
    StockAdjustmentResult,
    StockRow,
    StockStateRow,
    StockTransferResult,
    WarehouseStockRow,
)
from app.modules.products.models import Product


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InventoryRepository(db)

    def record_movement(
        self,
        *,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        qty_delta: Decimal,
        reason: str,
        ref_type: str | None = None,
        ref_id: uuid.UUID | None = None,
        unit_cost_minor: int | None = None,
        bin_id: uuid.UUID | None = None,
        occurred_at: datetime | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> StockMovement:
        """Append one entry to the stock ledger. Still the ONLY writer (G8).

        `bin_id` is optional on purpose (R6.3): a caller that does not address a bin
        writes NULL, which reads as "at this warehouse, bin not recorded". Every
        pre-Part-5 caller therefore keeps working unchanged.

        `occurred_at` defaults to now and exists for the same reason Part 3 gave
        `confirm(confirmed_at=…)` and `GoodsReceiptCreate.received_at`: stock received on
        Saturday and keyed in on Monday arrived on Saturday, and it is the only way the
        seed can fabricate the aged history R6.10's buckets and R7.8's dead-stock radar
        need — **at INSERT time**, without ever UPDATE-ing a ledger row, which G4 forbids.
        """
        movement = StockMovement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            bin_id=bin_id,
            qty_delta=qty_delta,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            unit_cost_minor=unit_cost_minor,
            created_by=actor_id,
        )
        if occurred_at is not None:
            movement.occurred_at = occurred_at
        return self.repo.add(movement)

    def on_hand(self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None) -> Decimal:
        return self.repo.on_hand(product_id, warehouse_id)

    def stock(self) -> list[StockRow]:
        rows = []
        for pid, sku, pname, wid, wname, qty, reorder in self.repo.stock_rows():
            qty = Decimal(qty or 0)
            reorder = Decimal(reorder or 0)
            rows.append(
                StockRow(
                    product_id=pid,
                    sku_code=sku,
                    product_name=pname,
                    warehouse_id=wid,
                    warehouse_name=wname,
                    qty_on_hand=qty,
                    reorder_level=reorder,
                    is_low=qty < reorder,
                )
            )
        return rows

    def low_stock(self) -> list[tuple]:
        return self.repo.low_stock_products()

    def low_stock_count(self) -> int:
        return len(self.repo.low_stock_products())

    def movements(self, product_id: uuid.UUID | None = None):
        return self.repo.movements(product_id)

    def warehouse_stock(self, warehouse_id: uuid.UUID | None = None) -> list[WarehouseStockRow]:
        """Per-warehouse on-hand rows (optionally filtered to one warehouse)."""
        rows: list[WarehouseStockRow] = []
        for pid, sku, pname, wid, wname, qty, reorder in self.repo.stock_rows():
            if warehouse_id is not None and wid != warehouse_id:
                continue
            qty = Decimal(qty or 0)
            reorder = Decimal(reorder or 0)
            rows.append(
                WarehouseStockRow(
                    product_id=pid,
                    sku_code=sku,
                    product_name=pname,
                    warehouse_id=wid,
                    warehouse_name=wname,
                    qty_on_hand=qty,
                    reorder_level=reorder,
                    is_low=qty < reorder,
                )
            )
        return rows

    # --- Part 5 C1: derived states (R6.4) and location rollups (R6.11) -----

    def reserved(
        self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> Decimal:
        """Outstanding reserved quantity, summed from the reservation ledger (R6.5)."""
        return self.repo.reserved(product_id, warehouse_id)

    def available(
        self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> Decimal:
        """What can still be committed: sellable on-hand − outstanding reservations.

        Sellable excludes stock sitting in `transit` or `quarantine` bins — it is
        on-hand, but it is not available to promise. Not clamped at zero: an
        over-reserved product is a real condition and hiding it behind a floor would
        make the number lie.
        """
        sellable = Decimal(0)
        for _pid, _wid, kind, qty in self.repo.qty_by_bin_kind(warehouse_id):
            if _pid == product_id and kind == "stock":
                sellable += Decimal(qty or 0)
        return sellable - self.repo.reserved(product_id, warehouse_id)

    def states(self, warehouse_id: uuid.UUID | None = None) -> list[StockStateRow]:
        """R6.4 — the four states per product per warehouse, all derived (G7).

        Two grouped queries for the whole page (bin-kind totals and reservation
        totals) plus one for display names; no per-row query.
        """
        kinds: dict[tuple, dict[str, Decimal]] = {}
        for pid, wid, kind, qty in self.repo.qty_by_bin_kind(warehouse_id):
            bucket = kinds.setdefault((pid, wid), {})
            bucket[kind] = bucket.get(kind, Decimal(0)) + Decimal(qty or 0)
        reserved_by = {
            (pid, wid): Decimal(qty or 0)
            for pid, wid, qty in self.repo.reserved_totals(warehouse_id)
        }
        names = {
            (pid, wid): (sku, pname, wname)
            for pid, sku, pname, wid, wname, _qty, _reorder in self.repo.stock_rows()
        }

        rows: list[StockStateRow] = []
        for key in sorted(kinds, key=lambda k: names.get(k, ("",))[0]):
            pid, wid = key
            if key not in names:
                continue  # a soft-deleted product or warehouse — not shown
            sku, pname, wname = names[key]
            bucket = kinds[key]
            stock = bucket.get("stock", Decimal(0))
            transit = bucket.get("transit", Decimal(0))
            quarantined = bucket.get("quarantine", Decimal(0))
            reserved = reserved_by.get(key, Decimal(0))
            rows.append(
                StockStateRow(
                    product_id=pid,
                    sku_code=sku,
                    product_name=pname,
                    warehouse_id=wid,
                    warehouse_name=wname,
                    on_hand=stock + transit + quarantined,
                    reserved=reserved,
                    in_transit=transit,
                    quarantined=quarantined,
                    available=stock - reserved,
                )
            )
        return rows

    def bin_stock(self, warehouse_id: uuid.UUID | None = None) -> list[BinStockRow]:
        """Bin-level rows, including the "no bin recorded" row R6.3 leaves behind."""
        return [
            BinStockRow(
                product_id=pid,
                sku_code=sku,
                product_name=pname,
                warehouse_id=wid,
                warehouse_name=wname,
                rack_id=rack_id,
                rack_code=rack_code,
                bin_id=bin_id,
                bin_code=bin_code,
                bin_kind=bin_kind or "stock",
                qty_on_hand=Decimal(qty or 0),
            )
            for (
                pid, sku, pname, wid, wname, rack_id, rack_code, bin_id, bin_code,
                bin_kind, qty,
            ) in self.repo.bin_rows(warehouse_id)
        ]

    def location_rollup(
        self, warehouse_id: uuid.UUID | None = None
    ) -> list[LocationRollupRow]:
        """R6.11 — warehouse → rack → bin totals, each level summed from the one below.

        Built from the same bin-level rows the location screen renders, so the levels
        cannot disagree with each other: a rack's total IS the sum of its bins by
        construction rather than by a second query that might drift.
        """
        warehouses: dict[uuid.UUID, dict] = {}
        for row in self.bin_stock(warehouse_id):
            wh = warehouses.setdefault(
                row.warehouse_id, {"name": row.warehouse_name, "racks": {}}
            )
            rack_key = row.rack_id  # None groups every unaddressed row together
            rack = wh["racks"].setdefault(
                rack_key, {"code": row.rack_code or "—", "bins": {}}
            )
            bin_key = row.bin_id
            b = rack["bins"].setdefault(
                bin_key,
                {"code": row.bin_code or "no bin recorded", "kind": row.bin_kind,
                 "qty": Decimal(0)},
            )
            b["qty"] += row.qty_on_hand

        out: list[LocationRollupRow] = []
        for wid, wh in warehouses.items():
            rack_rows: list[LocationRollupRow] = []
            for rid, rack in wh["racks"].items():
                bin_rows = [
                    LocationRollupRow(
                        level="bin", id=bid, code=b["code"], name=b["code"],
                        kind=b["kind"], qty_on_hand=b["qty"],
                    )
                    for bid, b in sorted(rack["bins"].items(), key=lambda kv: kv[1]["code"])
                ]
                rack_rows.append(
                    LocationRollupRow(
                        level="rack", id=rid, code=rack["code"], name=rack["code"],
                        qty_on_hand=sum((r.qty_on_hand for r in bin_rows), Decimal(0)),
                        children=bin_rows,
                    )
                )
            rack_rows.sort(key=lambda r: r.code)
            out.append(
                LocationRollupRow(
                    level="warehouse", id=wid, code=wh["name"], name=wh["name"],
                    qty_on_hand=sum((r.qty_on_hand for r in rack_rows), Decimal(0)),
                    children=rack_rows,
                )
            )
        out.sort(key=lambda r: r.code)
        return out


class CycleCountService:
    """R7.1 — count sheet → variance → adjustment.

    Three verbs, and the middle one is why a sheet exists at all:

    * `open`   snapshots what the ledger believes, per line. The variance is measured
               against that snapshot, not against a balance that may have moved while the
               shelf was being walked.
    * `record` stores counted quantities. A line nobody counted stays NULL, which is
               *uncounted* — not a variance of minus-everything.
    * `close`  posts one `COUNT` adjustment per line that actually varies, **and none at
               all for a sheet that matches** (R7.2). Exactly one `activity_log` row for
               the closure either way (G5), because closing a sheet is one decision.

    R7.3 reads "a count with a variance produces exactly one adjustment movement": for one
    varying line that is literally true, and a test asserts it. A sheet with three varying
    products necessarily posts three movements — different products cannot share a ledger
    entry — and the activity row still counts one.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryService(db)
        self.repo = InventoryRepository(db)
        self.activity = ActivityService(db)

    def get(self, count_id: uuid.UUID) -> StockCount:
        sheet = self.db.scalar(
            select(StockCount).where(
                StockCount.id == count_id, StockCount.deleted_at.is_(None)
            )
        )
        if sheet is None:
            raise NotFoundError(f"Count sheet {count_id} not found")
        return sheet

    def sheets(self, *, status: str | None = None) -> list[StockCount]:
        stmt = select(StockCount).where(StockCount.deleted_at.is_(None))
        if status is not None:
            stmt = stmt.where(StockCount.status == status)
        return list(
            self.db.scalars(stmt.order_by(StockCount.created_at.desc(), StockCount.id.desc()))
        )

    def _lines(self, sheet: StockCount) -> list[StockCountLine]:
        return list(
            self.db.scalars(
                select(StockCountLine)
                .where(
                    StockCountLine.stock_count_id == sheet.id,
                    StockCountLine.deleted_at.is_(None),
                )
                .order_by(StockCountLine.id)
            )
        )

    def detail(self, count_id: uuid.UUID, *, adjustments_posted: int = 0) -> CountDetail:
        sheet = self.get(count_id)
        warehouse = self.db.get(Warehouse, sheet.warehouse_id)
        rows: list[CountLineRead] = []
        for line in self._lines(sheet):
            product = self.db.get(Product, line.product_id)
            rows.append(
                CountLineRead(
                    product_id=line.product_id,
                    sku_code=product.sku_code if product else "—",
                    product_name=product.name if product else "—",
                    system_qty=Decimal(line.system_qty),
                    counted_qty=(
                        None if line.counted_qty is None else Decimal(line.counted_qty)
                    ),
                )
            )
        return CountDetail(
            id=sheet.id,
            count_no=sheet.count_no,
            warehouse_id=sheet.warehouse_id,
            warehouse_name=warehouse.name if warehouse else "—",
            status=sheet.status,
            counted_at=sheet.counted_at,
            reason=sheet.reason,
            lines=rows,
            adjustments_posted=adjustments_posted,
        )

    def open(self, payload, *, actor_id: uuid.UUID | None) -> CountDetail:
        """Open a sheet, snapshotting the system quantity per line."""
        warehouse = self.db.scalar(
            select(Warehouse).where(
                Warehouse.id == payload.warehouse_id, Warehouse.deleted_at.is_(None)
            )
        )
        if warehouse is None:
            raise NotFoundError(f"Warehouse {payload.warehouse_id} not found")

        wanted = set(payload.product_ids or ())
        balances = [
            row
            for row in self.inventory.warehouse_stock(warehouse.id)
            if not wanted or row.product_id in wanted
        ]
        if payload.limit:
            balances = balances[: payload.limit]
        if not balances:
            raise ValidationError(
                f"Nothing to count at {warehouse.name} — no stock on record for those products"
            )

        sheet = StockCount(
            count_no=allocate_document_number(
                self.db,
                doc_type="CNT",
                business_unit_id=default_business_unit(self.db),
                on_date=date.today(),
            ),
            warehouse_id=warehouse.id,
            status="open",
            created_by=actor_id,
        )
        self.db.add(sheet)
        self.db.flush()
        for row in balances:
            self.db.add(
                StockCountLine(
                    stock_count_id=sheet.id,
                    product_id=row.product_id,
                    system_qty=row.qty_on_hand,
                    created_by=actor_id,
                )
            )
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="opened",
            entity_type="stock_count",
            entity_id=sheet.id,
            summary=(
                f"Opened count sheet {sheet.count_no} for {warehouse.name} "
                f"({len(balances)} lines)"
            ),
            data={"warehouse": warehouse.code, "lines": str(len(balances))},
        )
        return self.detail(sheet.id)

    def record(self, count_id: uuid.UUID, payload, *, actor_id: uuid.UUID | None) -> CountDetail:
        """Store counted quantities. Re-recording a line overwrites what was typed —
        the sheet is a working document until it closes, and the LEDGER is what is
        append-only (G4). Nothing about stock has changed yet."""
        sheet = self.get(count_id)
        if sheet.status != "open":
            raise ConflictError(f"Count sheet {sheet.count_no} is already {sheet.status}")

        by_product = {ln.product_id: ln for ln in self._lines(sheet)}
        for entry in payload.entries:
            line = by_product.get(entry.product_id)
            if line is None:
                product = self.db.get(Product, entry.product_id)
                raise ValidationError(
                    f"{product.sku_code if product else entry.product_id} is not on "
                    f"count sheet {sheet.count_no}"
                )
            line.counted_qty = Decimal(entry.counted_qty)
        self.db.flush()
        return self.detail(count_id)

    def close(self, count_id: uuid.UUID, payload, *, actor_id: uuid.UUID | None) -> CountDetail:
        """Post the variances and close the sheet.

        R7.2/R7.3 live here: a line whose count matches its snapshot writes **no**
        movement; a line that varies writes exactly one, through `record_movement` (G8).
        """
        sheet = self.get(count_id)
        if sheet.status != "open":
            raise ConflictError(f"Count sheet {sheet.count_no} is already {sheet.status}")
        reason = (payload.reason or "").strip()
        if not reason:
            raise ValidationError(
                "Closing a count needs a reason — it may adjust stock (R7.4)"
            )

        lines = self._lines(sheet)
        if not any(ln.counted_qty is not None for ln in lines):
            raise ValidationError(
                f"No line on {sheet.count_no} has been counted yet — nothing to close"
            )

        from app.modules.pricing.service import PricingService

        pricing = PricingService(self.db)
        posted = 0
        for line in lines:
            if line.counted_qty is None:
                continue  # uncounted, not a variance — leave the stock alone
            variance = Decimal(line.counted_qty) - Decimal(line.system_qty)
            if variance == 0:
                continue  # R7.2: a match writes nothing
            self.inventory.record_movement(
                product_id=line.product_id,
                warehouse_id=sheet.warehouse_id,
                bin_id=line.bin_id,
                qty_delta=variance,
                reason="COUNT",
                ref_type="stock_count",
                ref_id=sheet.id,
                unit_cost_minor=pricing.latest_purchase_minor(line.product_id),
                actor_id=actor_id,
            )
            posted += 1

        sheet.status = "closed"
        sheet.counted_at = datetime.now(UTC)
        sheet.reason = reason
        self.db.flush()

        # One row for the closure, whatever the line count — closing is one decision (G5).
        self.activity.log(
            actor_id=actor_id,
            verb="closed",
            entity_type="stock_count",
            entity_id=sheet.id,
            summary=(
                f"Closed count {sheet.count_no}: {posted} adjustment"
                f"{'' if posted == 1 else 's'} posted — {reason}"
                if posted
                else f"Closed count {sheet.count_no}: no variance — {reason}"
            ),
            data={"adjustments": str(posted), "reason": reason},
        )
        return self.detail(sheet.id, adjustments_posted=posted)


class LocationService:
    """Maintains R6.1's warehouse → rack → bin tree.

    Racks and bins are ordinary masters — created, renamed, soft-deleted with the one
    helper — so this class only owns what is specific to them: a code unique within its
    parent, and a bin kind restricted to `BIN_KINDS`.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InventoryRepository(db)
        self.activity = ActivityService(db)

    def _require_warehouse(self, warehouse_id: uuid.UUID) -> Warehouse:
        wh = self.db.scalar(
            select(Warehouse).where(
                Warehouse.id == warehouse_id, Warehouse.deleted_at.is_(None)
            )
        )
        if wh is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        return wh

    def require_rack(self, rack_id: uuid.UUID) -> StorageRack:
        rack = self.db.scalar(
            select(StorageRack).where(
                StorageRack.id == rack_id, StorageRack.deleted_at.is_(None)
            )
        )
        if rack is None:
            raise NotFoundError(f"Rack {rack_id} not found")
        return rack

    def require_bin(self, bin_id: uuid.UUID) -> StorageBin:
        row = self.db.scalar(
            select(StorageBin).where(
                StorageBin.id == bin_id, StorageBin.deleted_at.is_(None)
            )
        )
        if row is None:
            raise NotFoundError(f"Bin {bin_id} not found")
        return row

    def racks(self, warehouse_id: uuid.UUID | None = None) -> list[StorageRack]:
        return self.repo.racks(warehouse_id)

    def bins(self, rack_id: uuid.UUID | None = None) -> list[StorageBin]:
        return self.repo.bins(rack_id)

    def create_rack(self, payload, *, actor_id: uuid.UUID | None) -> StorageRack:
        warehouse = self._require_warehouse(payload.warehouse_id)
        code = payload.code.strip().upper()
        clash = self.db.scalar(
            select(StorageRack).where(
                StorageRack.warehouse_id == warehouse.id,
                func.upper(StorageRack.code) == code,
                StorageRack.deleted_at.is_(None),
            )
        )
        if clash is not None:
            raise ConflictError(f"Rack {code} already exists in {warehouse.name}")
        rack = StorageRack(
            warehouse_id=warehouse.id,
            code=code,
            name=(payload.name or "").strip() or None,
            created_by=actor_id,
        )
        self.db.add(rack)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="storage_rack",
            entity_id=rack.id,
            summary=f"Added rack {code} to {warehouse.name}",
            data={"warehouse": warehouse.code, "code": code},
        )
        return rack

    def create_bin(self, payload, *, actor_id: uuid.UUID | None) -> StorageBin:
        rack = self.require_rack(payload.storage_rack_id)
        kind = (payload.kind or "stock").strip().lower()
        if kind not in BIN_KINDS:
            raise ValidationError(
                f"Unknown bin kind '{kind}' — expected one of {', '.join(BIN_KINDS)}"
            )
        code = payload.code.strip().upper()
        clash = self.db.scalar(
            select(StorageBin).where(
                StorageBin.storage_rack_id == rack.id,
                func.upper(StorageBin.code) == code,
                StorageBin.deleted_at.is_(None),
            )
        )
        if clash is not None:
            raise ConflictError(f"Bin {code} already exists in rack {rack.code}")
        row = StorageBin(
            storage_rack_id=rack.id,
            code=code,
            name=(payload.name or "").strip() or None,
            kind=kind,
            created_by=actor_id,
        )
        self.db.add(row)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="storage_bin",
            entity_id=row.id,
            summary=f"Added {kind} bin {code} to rack {rack.code}",
            data={"rack": rack.code, "code": code, "kind": kind},
        )
        return row


class ReservationService:
    """R6.5/R6.6 — the one place stock is committed, released and consumed.

    Every verb appends a signed entry to `stock_reservation` and writes exactly one
    `activity_log` row (G5). Nothing is ever updated: releasing a reservation means
    appending a negative entry, not editing the positive one (G4). `stock_movement` is
    untouched by all three — committing stock does not move it, which is precisely what
    makes "reserved" different from "shipped".

    **Part 7's R9.8/R9.9 calls this and adds no second mechanism.** `reserve` at
    sales-order confirm, `consume` at fulfilment, `release` at cancellation.
    """

    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    CONSUME = "CONSUME"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryService(db)
        self.repo = InventoryRepository(db)
        self.activity = ActivityService(db)

    def _require_product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def _require_warehouse(self, warehouse_id: uuid.UUID) -> Warehouse:
        wh = self.db.scalar(
            select(Warehouse).where(
                Warehouse.id == warehouse_id, Warehouse.deleted_at.is_(None)
            )
        )
        if wh is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        return wh

    def reserved(
        self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> Decimal:
        return self.repo.reserved(product_id, warehouse_id)

    def available(
        self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> Decimal:
        return self.inventory.available(product_id, warehouse_id)

    def entries(self, product_id: uuid.UUID | None = None) -> list[StockReservation]:
        return self.repo.reservation_entries(product_id)

    def _append(
        self,
        *,
        product: Product,
        warehouse: Warehouse,
        qty_delta: Decimal,
        reason: str,
        payload,
        actor_id: uuid.UUID | None,
        summary: str,
    ) -> ReservationResult:
        entry = StockReservation(
            product_id=product.id,
            warehouse_id=warehouse.id,
            bin_id=getattr(payload, "bin_id", None),
            qty_delta=qty_delta,
            reason=reason,
            ref_type=getattr(payload, "ref_type", None),
            ref_id=getattr(payload, "ref_id", None),
            note=getattr(payload, "note", None),
            created_by=actor_id,
        )
        self.repo.add_reservation(entry)
        self.activity.log(
            actor_id=actor_id,
            verb=reason.lower() + "d" if reason != self.RESERVE else "reserved",
            entity_type="stock_reservation",
            entity_id=entry.id,
            summary=summary,
            data={
                "qty": str(abs(qty_delta)),
                "reason": reason,
                "product": product.sku_code,
                "warehouse": warehouse.code,
            },
        )
        return ReservationResult(
            product_id=product.id,
            warehouse_id=warehouse.id,
            qty_delta=qty_delta,
            reason=reason,
            on_hand=self.inventory.on_hand(product.id, warehouse.id),
            reserved=self.reserved(product.id, warehouse.id),
            available=self.inventory.available(product.id, warehouse.id),
        )

    def reserve(self, payload, *, actor_id: uuid.UUID | None) -> ReservationResult:
        """Commit `payload.qty` of a product at a warehouse.

        Refuses to commit more than is available, and the message states the numbers so
        the founder can act on it rather than just being told "no" (G11's spirit).
        """
        product = self._require_product(payload.product_id)
        warehouse = self._require_warehouse(payload.warehouse_id)
        qty = Decimal(payload.qty)
        available = self.inventory.available(product.id, warehouse.id)
        if qty > available:
            raise ConflictError(
                f"Cannot reserve {_qty_text(qty)} × {product.sku_code} at "
                f"{warehouse.name} — only {_qty_text(available)} available "
                f"(on hand {_qty_text(self.inventory.on_hand(product.id, warehouse.id))}, "
                f"already reserved {_qty_text(self.reserved(product.id, warehouse.id))})"
            )
        return self._append(
            product=product,
            warehouse=warehouse,
            qty_delta=qty,
            reason=self.RESERVE,
            payload=payload,
            actor_id=actor_id,
            summary=(
                f"Reserved {_qty_text(qty)} × {product.sku_code} at {warehouse.name}"
            ),
        )

    def release(self, payload, *, actor_id: uuid.UUID | None) -> ReservationResult:
        """Give committed stock back (cancellation) — a negative ledger entry."""
        return self._unwind(
            payload, actor_id=actor_id, reason=self.RELEASE, verb="Released"
        )

    def consume(self, payload, *, actor_id: uuid.UUID | None) -> ReservationResult:
        """Retire a reservation because the stock actually shipped (fulfilment).

        The outbound `stock_movement` is the caller's job and stays the only thing that
        moves on-hand (G8); this just stops the quantity being double-counted as both
        reserved and gone.
        """
        return self._unwind(
            payload, actor_id=actor_id, reason=self.CONSUME, verb="Consumed"
        )

    def _unwind(self, payload, *, actor_id, reason: str, verb: str) -> ReservationResult:
        product = self._require_product(payload.product_id)
        warehouse = self._require_warehouse(payload.warehouse_id)
        qty = Decimal(payload.qty)
        outstanding = self.reserved(product.id, warehouse.id)
        if qty > outstanding:
            raise ConflictError(
                f"Cannot {reason.lower()} {_qty_text(qty)} × {product.sku_code} at "
                f"{warehouse.name} — only {_qty_text(outstanding)} is reserved"
            )
        return self._append(
            product=product,
            warehouse=warehouse,
            qty_delta=-qty,
            reason=reason,
            payload=payload,
            actor_id=actor_id,
            summary=(
                f"{verb} {_qty_text(qty)} × {product.sku_code} at {warehouse.name}"
            ),
        )


class StockTransferService:
    """Moves stock between two warehouses. Balances remain derived (D3/G7).

    **R7.5 makes this two steps, so stock is never invisible mid-flight.** `dispatch`
    takes it off the source's shelf and into the destination's `transit` bin; `receive`
    takes it out of transit and onto the destination's shelf. In between, the stock is
    still on hand and `/inventory` reports it as *in transit* — the state C1 made
    derivable from `StorageBin.kind`, which is why no in-transit flag exists.

    Each step posts an OUT/IN **pair** through `record_movement` (G8) and writes exactly
    one `activity_log` row (G5). `transfer` remains as the one-call convenience for
    callers that do not model the in-flight state — the seed's original transfer and the
    quick form on `/warehouse` — and it is now literally dispatch-then-receive, so there
    is one implementation of the movement arithmetic rather than two.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryService(db)
        self.repo = InventoryRepository(db)
        self.activity = ActivityService(db)

    def _require_warehouse(self, warehouse_id: uuid.UUID) -> Warehouse:
        wh = self.db.scalar(
            select(Warehouse).where(
                Warehouse.id == warehouse_id, Warehouse.deleted_at.is_(None)
            )
        )
        if wh is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        return wh

    def _require_product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def _unit_cost(self, product_id: uuid.UUID) -> int | None:
        from app.modules.pricing.service import PricingService

        return PricingService(self.db).latest_purchase_minor(product_id)

    def in_transit(self) -> list[StockTransfer]:
        """Transfers dispatched and not yet received — outstanding work, newest first."""
        return list(
            self.db.scalars(
                select(StockTransfer)
                .where(
                    StockTransfer.status == "in_transit",
                    StockTransfer.deleted_at.is_(None),
                )
                .order_by(StockTransfer.dispatched_at.desc(), StockTransfer.id.desc())
            )
        )

    def get(self, transfer_id: uuid.UUID) -> StockTransfer:
        row = self.db.scalar(
            select(StockTransfer).where(
                StockTransfer.id == transfer_id, StockTransfer.deleted_at.is_(None)
            )
        )
        if row is None:
            raise NotFoundError(f"Transfer {transfer_id} not found")
        return row

    def dispatch(self, payload, *, actor_id: uuid.UUID | None) -> StockTransfer:
        """R7.5 step one: off the source's shelf, into the destination's transit bin.

        Two movements, so the total on hand across the business is unchanged — the stock
        has moved state, not vanished. It shows on `/inventory` as *in transit* because it
        now sits in a `transit`-kind bin.
        """
        if payload.from_warehouse_id == payload.to_warehouse_id:
            raise ValidationError("Source and destination warehouses must differ")
        product = self._require_product(payload.product_id)
        src = self._require_warehouse(payload.from_warehouse_id)
        dst = self._require_warehouse(payload.to_warehouse_id)
        qty = Decimal(payload.qty)

        available = self.inventory.on_hand(product.id, src.id)
        if qty > available:
            raise ValidationError(
                f"Transfer {_qty_text(qty)} exceeds on-hand {_qty_text(available)} "
                f"at {src.name}"
            )

        transit_bin = self.repo.bin_of_kind(dst.id, "transit")
        if transit_bin is None:
            # Refusing beats silently posting unaddressed stock: without a transit bin
            # the in-transit state would be unreportable, which is the one thing R7.5
            # exists to prevent. The message names the fix.
            raise ValidationError(
                f"{dst.name} has no transit bin, so stock in flight could not be shown "
                f"as in transit. Add a bin of kind 'transit' to {dst.name} first."
            )

        unit_cost = self._unit_cost(product.id)
        self.inventory.record_movement(
            product_id=product.id, warehouse_id=src.id, qty_delta=-qty,
            reason="TRANSFER", ref_type="stock_transfer", ref_id=product.id,
            unit_cost_minor=unit_cost, actor_id=actor_id,
        )
        self.inventory.record_movement(
            product_id=product.id, warehouse_id=dst.id, bin_id=transit_bin.id,
            qty_delta=qty, reason="TRANSFER", ref_type="stock_transfer",
            ref_id=product.id, unit_cost_minor=unit_cost, actor_id=actor_id,
        )

        transfer = StockTransfer(
            transfer_no=allocate_document_number(
                self.db,
                doc_type="TRF",
                business_unit_id=default_business_unit(self.db),
                on_date=date.today(),
            ),
            product_id=product.id,
            from_warehouse_id=src.id,
            to_warehouse_id=dst.id,
            transit_bin_id=transit_bin.id,
            qty=qty,
            status="in_transit",
            note=payload.note,
            created_by=actor_id,
        )
        self.db.add(transfer)
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="dispatched",
            entity_type="stock_transfer",
            entity_id=transfer.id,
            summary=(
                f"Dispatched {_qty_text(qty)} × {product.sku_code} from {src.name} "
                f"to {dst.name} ({transfer.transfer_no})"
            ),
            data={"qty": str(qty), "from": src.code, "to": dst.code},
        )
        return transfer

    def receive(self, transfer_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> StockTransfer:
        """R7.5 step two: out of transit, onto the destination's shelf."""
        transfer = self.get(transfer_id)
        if transfer.status != "in_transit":
            raise ConflictError(
                f"Transfer {transfer.transfer_no} is already {transfer.status}"
            )
        product = self._require_product(transfer.product_id)
        dst = self._require_warehouse(transfer.to_warehouse_id)
        qty = Decimal(transfer.qty)
        unit_cost = self._unit_cost(product.id)

        stock_bin = self.repo.bin_of_kind(dst.id, "stock")
        self.inventory.record_movement(
            product_id=product.id, warehouse_id=dst.id, bin_id=transfer.transit_bin_id,
            qty_delta=-qty, reason="TRANSFER", ref_type="stock_transfer",
            ref_id=transfer.id, unit_cost_minor=unit_cost, actor_id=actor_id,
        )
        self.inventory.record_movement(
            product_id=product.id, warehouse_id=dst.id,
            bin_id=stock_bin.id if stock_bin else None,
            qty_delta=qty, reason="TRANSFER", ref_type="stock_transfer",
            ref_id=transfer.id, unit_cost_minor=unit_cost, actor_id=actor_id,
        )
        transfer.status = "received"
        transfer.received_at = datetime.now(UTC)
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="received",
            entity_type="stock_transfer",
            entity_id=transfer.id,
            summary=(
                f"Received {_qty_text(qty)} × {product.sku_code} at {dst.name} "
                f"({transfer.transfer_no})"
            ),
            data={"qty": str(qty), "to": dst.code},
        )
        return transfer

    def transfer(self, payload, *, actor_id: uuid.UUID | None) -> StockTransferResult:
        """Dispatch and receive in one call, for callers that do not track the in-flight
        state. Literally the two steps back to back, so there is one implementation of
        the movement arithmetic rather than a second one that could drift."""
        dispatched = self.dispatch(payload, actor_id=actor_id)
        self.receive(dispatched.id, actor_id=actor_id)
        return StockTransferResult(
            product_id=dispatched.product_id,
            from_warehouse_id=dispatched.from_warehouse_id,
            to_warehouse_id=dispatched.to_warehouse_id,
            qty=Decimal(dispatched.qty),
            from_on_hand=self.inventory.on_hand(
                dispatched.product_id, dispatched.from_warehouse_id
            ),
            to_on_hand=self.inventory.on_hand(
                dispatched.product_id, dispatched.to_warehouse_id
            ),
        )


class StockAdjustmentService:
    """Manual corrections and cycle counts — a single signed ledger movement
    (reason `ADJUSTMENT` or `COUNT`) plus one `activity_log` row (D10)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryService(db)
        self.activity = ActivityService(db)

    def _require_warehouse(self, warehouse_id: uuid.UUID) -> Warehouse:
        wh = self.db.scalar(
            select(Warehouse).where(
                Warehouse.id == warehouse_id, Warehouse.deleted_at.is_(None)
            )
        )
        if wh is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        return wh

    def _require_product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def _post(
        self,
        *,
        product: Product,
        warehouse: Warehouse,
        qty_delta: Decimal,
        reason: str,
        actor_id: uuid.UUID | None,
        summary: str,
    ) -> StockAdjustmentResult:
        from app.modules.pricing.service import PricingService

        self.inventory.record_movement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            qty_delta=qty_delta,
            reason=reason,
            ref_type="stock_adjustment",
            ref_id=product.id,
            unit_cost_minor=PricingService(self.db).latest_purchase_minor(product.id),
            actor_id=actor_id,
        )
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="adjusted",
            entity_type="stock",
            entity_id=product.id,
            summary=summary,
            data={"qty_delta": str(qty_delta), "reason": reason, "warehouse": warehouse.code},
        )
        return StockAdjustmentResult(
            product_id=product.id,
            warehouse_id=warehouse.id,
            qty_delta=qty_delta,
            reason=reason,
            on_hand=self.inventory.on_hand(product.id, warehouse.id),
        )

    def adjust(self, payload, *, actor_id: uuid.UUID | None) -> StockAdjustmentResult:
        """Apply a signed correction to on-hand at a warehouse.

        **R7.4: the human reason is mandatory.** The schema requires a non-empty string;
        this also refuses whitespace, because a note of `"   "` satisfies a length check
        and tells a later reader nothing.
        """
        if payload.qty_delta == 0:
            raise ValidationError("Adjustment quantity must be non-zero")
        if not (payload.note or "").strip():
            raise ValidationError(
                "An adjustment needs a reason — stock does not change by itself (R7.4)"
            )
        reason = (payload.reason or "ADJUSTMENT").upper()
        if reason not in ("ADJUSTMENT", "COUNT"):
            raise ConflictError(f"Unsupported adjustment reason '{reason}'")
        product = self._require_product(payload.product_id)
        warehouse = self._require_warehouse(payload.warehouse_id)
        sign = "+" if payload.qty_delta > 0 else ""
        return self._post(
            product=product,
            warehouse=warehouse,
            qty_delta=Decimal(payload.qty_delta),
            reason=reason,
            actor_id=actor_id,
            summary=(
                f"Adjusted {product.sku_code} at {warehouse.name} "
                f"by {sign}{payload.qty_delta}"
            ),
        )

    def count(self, payload, *, actor_id: uuid.UUID | None) -> StockAdjustmentResult:
        """Reconcile on-hand to a physically counted quantity (posts the delta).

        **A count that matches posts NOTHING and is not an error** (R7.2). This used to
        raise `ConflictError` — "nothing to reconcile" — which made the ordinary, desirable
        outcome of a stock count look like a failure and would have shown the founder a red
        flash for doing everything right. It now returns a result with a zero delta, and no
        movement is written.

        For a whole sheet of lines, use `CycleCountService` — this is the one-line quick path.
        """
        product = self._require_product(payload.product_id)
        warehouse = self._require_warehouse(payload.warehouse_id)
        current = self.inventory.on_hand(product.id, warehouse.id)
        delta = Decimal(payload.counted_qty) - current
        if delta == 0:
            return StockAdjustmentResult(
                product_id=product.id,
                warehouse_id=warehouse.id,
                qty_delta=Decimal(0),
                reason="COUNT",
                on_hand=current,
            )
        return self._post(
            product=product,
            warehouse=warehouse,
            qty_delta=delta,
            reason="COUNT",
            actor_id=actor_id,
            summary=(
                f"Cycle count {product.sku_code} at {warehouse.name}: "
                f"{current} → {payload.counted_qty}"
            ),
        )
