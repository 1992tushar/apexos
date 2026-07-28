"""Warehouse operations: stock overview + transfer / adjust / count."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ValidationError
from app.core.security import Actor
from app.modules.config.service import ConfigService
from app.modules.inventory.schemas import (
    BinCreate,
    CountClose,
    CountEntry,
    CountOpen,
    CountRecord,
    RackCreate,
    StockAdjustmentCreate,
    StockCountCreate,
    StockTransferCreate,
    TransferDispatch,
)
from app.modules.inventory.service import (
    CycleCountService,
    InventoryService,
    LocationService,
    StockAdjustmentService,
    StockTransferService,
)
from app.modules.inventory.valuation import ValuationService
from app.modules.products.service import ProductService
from app.web.core import form_action, render
from app.web.security import require_web_permission

router = APIRouter()


@router.get("/warehouse")
def warehouse_index(request: Request, db: Session = Depends(get_db)):
    warehouses = ConfigService(db).warehouses()
    stock = InventoryService(db).warehouse_stock(None)
    products, _ = ProductService(db).list(
        search=None, category_id=None, page=1, page_size=300
    )
    valuation = ValuationService(db)
    locations = LocationService(db)
    racks = locations.racks()
    bins_by_rack: dict[uuid.UUID, list] = {}
    for rack in racks:
        bins_by_rack[rack.id] = locations.bins(rack.id)

    summary = []
    for wh in warehouses:
        wh_rows = [s for s in stock if s.warehouse_id == wh.id]
        wh_racks = [r for r in racks if r.warehouse_id == wh.id]
        # R6.12's ageing view, scoped to this warehouse. Bucket totals rather than a
        # per-product table: the per-product breakdown is on /inventory, and repeating it
        # per warehouse would be the same table three times.
        ageing = valuation.ageing(wh.id)
        bucket_totals: dict[str, Decimal] = {}
        for row in ageing:
            for bucket in row.buckets:
                bucket_totals[bucket.label] = (
                    bucket_totals.get(bucket.label, Decimal(0)) + bucket.qty
                )
        summary.append(
            {
                "id": wh.id,
                "code": wh.code,
                "name": wh.name,
                "city": wh.city,
                "units": sum((r.qty_on_hand for r in wh_rows), Decimal(0)),
                "sku_count": len(wh_rows),
                "ageing": bucket_totals,
                "oldest_days": max(
                    (r.oldest_days for r in ageing if r.oldest_days is not None),
                    default=None,
                ),
                # R6.1's tree, for the location panel below the stock table.
                "racks": [
                    {"row": rack, "bins": bins_by_rack.get(rack.id, [])}
                    for rack in wh_racks
                ],
            }
        )
    return render(
        request,
        "warehouse/index.html",
        warehouses=warehouses,
        stock=stock,
        products=products,
        summary=summary,
        racks=racks,
        ageing_note=valuation.ageing_note(),
        # R7.5 — transfers dispatched and not yet received. Outstanding work, and the
        # proof that stock in flight is visible rather than missing.
        in_transit=StockTransferService(db).in_transit(),
        open_counts=CycleCountService(db).sheets(status="open"),
        product_names={p.id: f"{p.sku_code} — {p.name}" for p in products},
        warehouse_names={w.id: w.name for w in warehouses},
    )


@router.post("/inventory/transfers/dispatch")
def dispatch_transfer(
    request: Request,
    product_id: str = Form(...),
    from_warehouse_id: str = Form(...),
    to_warehouse_id: str = Form(...),
    qty: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.transfer")),
):
    """R7.5 step one — stock leaves the shelf and becomes visibly in transit."""

    def work():
        payload = TransferDispatch(
            product_id=uuid.UUID(product_id),
            from_warehouse_id=uuid.UUID(from_warehouse_id),
            to_warehouse_id=uuid.UUID(to_warehouse_id),
            qty=Decimal(str(qty)),
            note=note or None,
        )
        return StockTransferService(db).dispatch(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/warehouse",
        success=lambda t: ("/warehouse", f"{t.transfer_no} dispatched — now in transit"),
        err="Could not dispatch the transfer",
    )


@router.post("/inventory/transfers/{transfer_id}/receive")
def receive_transfer(
    request: Request,
    transfer_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.transfer")),
):
    """R7.5 step two — it lands on the destination's shelf."""
    return form_action(
        db, lambda: StockTransferService(db).receive(transfer_id, actor_id=actor.id),
        back="/warehouse",
        success=lambda t: ("/warehouse", f"{t.transfer_no} received"),
        err="Could not receive the transfer",
    )


@router.post("/warehouse/counts")
def open_count(
    request: Request,
    warehouse_id: str = Form(...),
    limit: str = Form("25"),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.adjust")),
):
    """R7.1 — open a count sheet, snapshotting what the ledger currently believes."""

    def work():
        payload = CountOpen(
            warehouse_id=uuid.UUID(warehouse_id),
            limit=int(limit) if limit.strip() else None,
        )
        return CycleCountService(db).open(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/warehouse",
        success=lambda sheet: (f"/warehouse/counts/{sheet.id}", f"{sheet.count_no} opened"),
        err="Could not open a count sheet",
    )


@router.get("/warehouse/counts/{count_id}")
def count_detail(request: Request, count_id: uuid.UUID, db: Session = Depends(get_db)):
    return render(
        request, "warehouse/count.html", sheet=CycleCountService(db).detail(count_id)
    )


@router.post("/warehouse/counts/{count_id}/record")
def record_count(
    request: Request,
    count_id: uuid.UUID,
    product_id: list[str] = Form(default=[]),
    counted_qty: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.adjust")),
):
    """Store the counted quantities. Blank rows are skipped — a line nobody counted stays
    uncounted rather than being recorded as zero, which would wipe the stock on close."""

    def work():
        entries = [
            CountEntry(product_id=uuid.UUID(pid), counted_qty=Decimal(qty))
            for pid, qty in zip(product_id, counted_qty, strict=False)
            if qty.strip()
        ]
        if not entries:
            raise ValidationError("Nothing was counted — enter at least one quantity")
        return CycleCountService(db).record(
            count_id, CountRecord(entries=entries), actor_id=actor.id
        )

    return form_action(
        db, work, back=f"/warehouse/counts/{count_id}",
        success=(f"/warehouse/counts/{count_id}", "Counts saved"),
        err="Could not save the counts",
    )


@router.post("/warehouse/counts/{count_id}/close")
def close_count(
    request: Request,
    count_id: uuid.UUID,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.adjust")),
):
    """R7.2/R7.3 — post one adjustment per varying line, none for a sheet that matches."""

    def work():
        return CycleCountService(db).close(
            count_id, CountClose(reason=reason), actor_id=actor.id
        )

    return form_action(
        db, work, back=f"/warehouse/counts/{count_id}",
        success=lambda sheet: (
            f"/warehouse/counts/{count_id}",
            f"{sheet.count_no} closed — {sheet.adjustments_posted} adjustment"
            f"{'' if sheet.adjustments_posted == 1 else 's'} posted",
        ),
        err="Could not close the count",
    )


@router.post("/warehouse/racks")
def create_rack(
    request: Request,
    warehouse_id: str = Form(...),
    code: str = Form(...),
    name: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("storage_rack.create")),
):
    """Add a rack to a warehouse (R6.1)."""

    def work():
        payload = RackCreate(
            warehouse_id=uuid.UUID(warehouse_id), code=code, name=name or None
        )
        return LocationService(db).create_rack(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/warehouse", success=("/warehouse", "Rack added"),
        err="Could not add the rack",
    )


@router.post("/warehouse/bins")
def create_bin(
    request: Request,
    storage_rack_id: str = Form(...),
    code: str = Form(...),
    name: str = Form(""),
    kind: str = Form("stock"),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("storage_bin.create")),
):
    """Add an addressable bin to a rack (R6.1).

    `kind` is what makes R6.4's in-transit and quarantine states addressable; the
    service refuses anything outside the known set rather than storing it.
    """

    def work():
        payload = BinCreate(
            storage_rack_id=uuid.UUID(storage_rack_id),
            code=code,
            name=name or None,
            kind=kind,
        )
        return LocationService(db).create_bin(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/warehouse", success=("/warehouse", "Bin added"),
        err="Could not add the bin",
    )


@router.post("/inventory/transfers")
def create_transfer(
    request: Request,
    product_id: str = Form(...),
    from_warehouse_id: str = Form(...),
    to_warehouse_id: str = Form(...),
    qty: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.transfer")),
):
    def work():
        payload = StockTransferCreate(
            product_id=uuid.UUID(product_id),
            from_warehouse_id=uuid.UUID(from_warehouse_id),
            to_warehouse_id=uuid.UUID(to_warehouse_id),
            qty=Decimal(str(qty)),
            note=None,
        )
        return StockTransferService(db).transfer(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/warehouse", success=("/warehouse", "Stock transferred"),
        err="Could not transfer stock",
    )


@router.post("/inventory/adjustments")
def create_adjustment(
    request: Request,
    product_id: str = Form(...),
    warehouse_id: str = Form(...),
    qty_delta: str = Form(...),
    note: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.adjust")),
):
    """R7.4 — the reason is a required form field, not an optional note."""

    def work():
        payload = StockAdjustmentCreate(
            product_id=uuid.UUID(product_id),
            warehouse_id=uuid.UUID(warehouse_id),
            qty_delta=Decimal(str(qty_delta)),
            reason="ADJUSTMENT",
            note=note,
        )
        return StockAdjustmentService(db).adjust(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/warehouse", success=("/warehouse", "Stock adjusted"),
        err="Could not adjust stock",
    )


@router.post("/inventory/counts")
def create_count(
    request: Request,
    product_id: str = Form(...),
    warehouse_id: str = Form(...),
    counted_qty: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.adjust")),
):
    def work():
        payload = StockCountCreate(
            product_id=uuid.UUID(product_id),
            warehouse_id=uuid.UUID(warehouse_id),
            counted_qty=Decimal(str(counted_qty)),
            note=None,
        )
        return StockAdjustmentService(db).count(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/warehouse", success=("/warehouse", "Count recorded"),
        err="Could not record count",
    )
