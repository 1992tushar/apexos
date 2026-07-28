"""Inventory service — record movements, derive on-hand, list low stock.

`InventoryService.record_movement` is the ONLY writer of `stock_movement` (D3);
Sales/Procurement and the Phase-B warehouse operations all go through it.
`StockTransferService` and `StockAdjustmentService` are the state-changing verbs
that each emit one `activity_log` row (D10); balances stay derived from the ledger.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.money import qty_text as _qty_text
from app.modules.activity.service import ActivityService
from app.modules.config.models import Warehouse
from app.modules.inventory.models import (
    BIN_KINDS,
    StockMovement,
    StockReservation,
    StorageBin,
    StorageRack,
)
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    BinStockRow,
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
        actor_id: uuid.UUID | None = None,
    ) -> StockMovement:
        """Append one entry to the stock ledger. Still the ONLY writer (G8).

        `bin_id` is optional on purpose (R6.3): a caller that does not address a bin
        writes NULL, which reads as "at this warehouse, bin not recorded". Every
        pre-Part-5 caller therefore keeps working unchanged.
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
    """Moves stock between two warehouses as two ledger movements (OUT then IN).
    Balances remain derived; nothing is stored mutably (D3)."""

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

    def transfer(self, payload, *, actor_id: uuid.UUID | None) -> StockTransferResult:
        """Post a TRANSFER OUT at the source and TRANSFER IN at the destination.

        Raises:
            ValidationError: same source/destination, or insufficient on-hand.
            NotFoundError: unknown product or warehouse.
        """
        if payload.from_warehouse_id == payload.to_warehouse_id:
            raise ValidationError("Source and destination warehouses must differ")
        product = self._require_product(payload.product_id)
        src = self._require_warehouse(payload.from_warehouse_id)
        dst = self._require_warehouse(payload.to_warehouse_id)

        available = self.inventory.on_hand(product.id, src.id)
        if payload.qty > available:
            raise ValidationError(
                f"Transfer {payload.qty} exceeds on-hand {available} at {src.name}"
            )

        from app.modules.pricing.service import PricingService

        unit_cost = PricingService(self.db).latest_purchase_minor(product.id)
        self.inventory.record_movement(
            product_id=product.id,
            warehouse_id=src.id,
            qty_delta=-Decimal(payload.qty),
            reason="TRANSFER",
            ref_type="stock_transfer",
            ref_id=product.id,
            unit_cost_minor=unit_cost,
            actor_id=actor_id,
        )
        self.inventory.record_movement(
            product_id=product.id,
            warehouse_id=dst.id,
            qty_delta=Decimal(payload.qty),
            reason="TRANSFER",
            ref_type="stock_transfer",
            ref_id=product.id,
            unit_cost_minor=unit_cost,
            actor_id=actor_id,
        )
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="transferred",
            entity_type="stock",
            entity_id=product.id,
            summary=f"Transferred {payload.qty} × {product.sku_code} from {src.name} to {dst.name}",
            data={"qty": str(payload.qty), "from": src.code, "to": dst.code},
        )
        return StockTransferResult(
            product_id=product.id,
            from_warehouse_id=src.id,
            to_warehouse_id=dst.id,
            qty=Decimal(payload.qty),
            from_on_hand=self.inventory.on_hand(product.id, src.id),
            to_on_hand=self.inventory.on_hand(product.id, dst.id),
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
        """Apply a signed correction to on-hand at a warehouse."""
        if payload.qty_delta == 0:
            raise ValidationError("Adjustment quantity must be non-zero")
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
        """Reconcile on-hand to a physically counted quantity (posts the delta)."""
        product = self._require_product(payload.product_id)
        warehouse = self._require_warehouse(payload.warehouse_id)
        current = self.inventory.on_hand(product.id, warehouse.id)
        delta = Decimal(payload.counted_qty) - current
        if delta == 0:
            raise ConflictError(
                f"Counted quantity matches on-hand ({current}); nothing to reconcile"
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
