"""Inventory page: read-only stock across warehouses.

Part 5 C1 adds R6.4's four states and R6.11's warehouse → rack → bin rollup. Both are
derived on the way out (G7) — the page stores nothing and computes nothing itself, it
just renders what `InventoryService` measured.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.inventory.service import InventoryService
from app.web.core import render

router = APIRouter()


@router.get("/inventory")
def list_inventory(request: Request, db: Session = Depends(get_db)):
    svc = InventoryService(db)
    rows = svc.stock()
    states = svc.states()
    locations = svc.location_rollup()
    low_count = sum(1 for r in rows if r.is_low)
    # Totals for the state header. Summed from the same rows the table renders, so the
    # banner cannot disagree with the body.
    totals = {
        "on_hand": sum((s.on_hand for s in states), Decimal(0)),
        "reserved": sum((s.reserved for s in states), Decimal(0)),
        "in_transit": sum((s.in_transit for s in states), Decimal(0)),
        "quarantined": sum((s.quarantined for s in states), Decimal(0)),
        "available": sum((s.available for s in states), Decimal(0)),
    }
    # How much stock has no recorded bin (R6.3). Shown rather than hidden: it is the
    # honest read of a ledger that predates addressing.
    unaddressed = sum(
        (r.qty_on_hand for r in svc.bin_stock() if r.bin_id is None), Decimal(0)
    )
    return render(
        request,
        "inventory/index.html",
        rows=rows,
        states=states,
        locations=locations,
        totals=totals,
        unaddressed=unaddressed,
        low_count=low_count,
    )
