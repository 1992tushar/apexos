"""Inventory page: read-only stock across warehouses."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.inventory.service import InventoryService
from app.web.core import render

router = APIRouter()


@router.get("/inventory")
def list_inventory(request: Request, db: Session = Depends(get_db)):
    rows = InventoryService(db).stock()
    low_count = sum(1 for r in rows if r.is_low)
    return render(request, "inventory/index.html", rows=rows, low_count=low_count)
