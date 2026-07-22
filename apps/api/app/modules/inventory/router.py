"""Inventory router — stock reads + Phase-B warehouse operations."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.inventory.schemas import (
    MovementRead,
    StockAdjustmentCreate,
    StockAdjustmentResult,
    StockCountCreate,
    StockRow,
    StockTransferCreate,
    StockTransferResult,
    WarehouseStockRow,
)
from app.modules.inventory.service import (
    InventoryService,
    StockAdjustmentService,
    StockTransferService,
)

router = APIRouter(tags=["inventory"])


@router.get("/inventory/stock", response_model=list[StockRow])
def stock(db: Session = Depends(get_db)):
    return InventoryService(db).stock()


@router.get("/inventory/movements", response_model=list[MovementRead])
def movements(
    product_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return InventoryService(db).movements(product_id)


# --- Warehouse operations (Phase B) --------------------------------------


@router.get("/inventory/warehouse-stock", response_model=list[WarehouseStockRow])
def warehouse_stock(
    warehouse_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Per-warehouse on-hand rows (optionally filtered to one warehouse)."""
    return InventoryService(db).warehouse_stock(warehouse_id)


@router.post("/inventory/transfers", response_model=StockTransferResult, status_code=201)
def create_transfer(
    payload: StockTransferCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("stock.transfer")),
):
    """Move stock between two warehouses (two ledger movements)."""
    return StockTransferService(db).transfer(payload, actor_id=actor.id)


@router.post("/inventory/adjustments", response_model=StockAdjustmentResult, status_code=201)
def create_adjustment(
    payload: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("stock.adjust")),
):
    """Apply a signed manual correction to on-hand at a warehouse."""
    return StockAdjustmentService(db).adjust(payload, actor_id=actor.id)


@router.post("/inventory/counts", response_model=StockAdjustmentResult, status_code=201)
def create_count(
    payload: StockCountCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("stock.adjust")),
):
    """Reconcile on-hand to a physically counted quantity (cycle count)."""
    return StockAdjustmentService(db).count(payload, actor_id=actor.id)
