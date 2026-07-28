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
from app.modules.inventory.health import InventoryHealthService
from app.modules.inventory.schemas import (
    ABC_CLASSES,
    AGE_BUCKETS,
    DEAD_STOCK_DAYS,
    MOVEMENT_WINDOW_DAYS,
    SLOW_MOVER_MAX_PER_MONTH,
)
from app.modules.inventory.service import InventoryService
from app.modules.inventory.valuation import ValuationService
from app.web.core import render

router = APIRouter()

# How many health rows to show per section. Each list is sorted worst-first, so the cut
# drops the least interesting rows — and the number dropped is stated on screen rather
# than the table implying it is the whole catalogue.
_HEALTH_LIMIT = 20

# How many ageing rows to render. The staleness sort puts the oldest stock first, so the
# cut is at the boring end — and the count that was dropped is stated on screen rather
# than the table silently implying it is the whole catalogue.
_AGEING_LIMIT = 40


@router.get("/inventory")
def list_inventory(request: Request, db: Session = Depends(get_db)):
    svc = InventoryService(db)
    valuation = ValuationService(db)
    rows = svc.stock()
    states = svc.states()
    locations = svc.location_rollup()
    low_count = sum(1 for r in rows if r.is_low)

    # R6.16 — computed once and passed to both totals, or the page pays for it three times.
    values = valuation.stock_value()
    total_value_minor = valuation.total_value_minor(values)
    unknown_basis = valuation.unknown_basis_count(values)

    # R6.10 — worst-aged first, so the truncation drops the least interesting rows.
    ageing_all = valuation.ageing()
    ageing = ageing_all[:_AGEING_LIMIT]

    # R7.7–R7.11 — health. Each list is worst-first and each carries its own thresholds.
    health = InventoryHealthService(db)
    abc_all = health.abc()
    abc_total_minor = sum(r.value_minor for r in abc_all)
    dead_all = health.dead_stock()
    movers_all = health.movement_rates()
    low_all = health.low_stock()
    # R7.11 — Part 4's engine, not a second one.
    reorder = health.reorder_suggestions(limit=10)
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
        values=values[:_AGEING_LIMIT],
        total_value_minor=total_value_minor,
        unknown_basis=unknown_basis,
        ageing=ageing,
        ageing_hidden=max(len(ageing_all) - len(ageing), 0),
        ageing_note=valuation.ageing_note(),
        age_buckets=AGE_BUCKETS,
        # --- health (R7.7–R7.11) ---
        abc=abc_all[:_HEALTH_LIMIT],
        abc_counts={
            key: sum(1 for r in abc_all if r.abc_class == key) for key, _b in ABC_CLASSES
        },
        abc_total_minor=abc_total_minor,
        abc_explained=(
            health.abc_explained(abc_all[0], total_minor=abc_total_minor)
            if abc_all
            else None
        ),
        abc_classes=ABC_CLASSES,
        dead=dead_all[:_HEALTH_LIMIT],
        dead_total=len(dead_all),
        dead_value_minor=sum(r.value_minor or 0 for r in dead_all),
        dead_explained=health.dead_stock_explained(dead_all[0]) if dead_all else None,
        dead_window=DEAD_STOCK_DAYS,
        movers=movers_all[:_HEALTH_LIMIT],
        fast_count=sum(1 for r in movers_all if r.is_fast),
        movement_window=MOVEMENT_WINDOW_DAYS,
        slow_threshold=SLOW_MOVER_MAX_PER_MONTH,
        low_stock=low_all[:_HEALTH_LIMIT],
        low_stock_total=len(low_all),
        low_stock_explained=health.low_stock_explained(low_all[0]) if low_all else None,
        reorder=reorder,
    )
