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
    StockAdjustmentCreate,
    StockCountCreate,
    StockTransferCreate,
)
from app.modules.inventory.service import (
    InventoryService,
    StockAdjustmentService,
    StockTransferService,
)
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
    summary = []
    for wh in warehouses:
        wh_rows = [s for s in stock if s.warehouse_id == wh.id]
        summary.append(
            {
                "id": wh.id,
                "code": wh.code,
                "name": wh.name,
                "city": wh.city,
                "units": sum((r.qty_on_hand for r in wh_rows), Decimal(0)),
                "sku_count": len(wh_rows),
            }
        )
    return render(
        request,
        "warehouse/index.html",
        warehouses=warehouses,
        stock=stock,
        products=products,
        summary=summary,
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
