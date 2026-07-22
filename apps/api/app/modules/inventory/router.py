"""Inventory router — GET /inventory/stock, GET /inventory/movements."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.inventory.schemas import MovementRead, StockRow
from app.modules.inventory.service import InventoryService

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
