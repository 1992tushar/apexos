"""Warehouse operations: stock overview + transfer / adjust / count."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.config.service import ConfigService
from app.modules.inventory.schemas import (
    BinCreate,
    RackCreate,
    StockAdjustmentCreate,
    StockCountCreate,
    StockTransferCreate,
)
from app.modules.inventory.service import (
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
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("stock.adjust")),
):
    def work():
        payload = StockAdjustmentCreate(
            product_id=uuid.UUID(product_id),
            warehouse_id=uuid.UUID(warehouse_id),
            qty_delta=Decimal(str(qty_delta)),
            reason="ADJUSTMENT",
            note=None,
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
