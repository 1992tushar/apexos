"""Part 5 C3b — inventory health: ABC, dead stock, fast/slow, low stock (R7.7–R7.11).

**Reads only, stores nothing** (G15/G7). An ABC class, a movement rate and a dead-stock
verdict are all derived per read — none of them is a column, and this module adds no model.

Every output states its own thresholds. That is not decoration: R7.7 and R7.8 make it
acceptance ("with its class boundaries stated", "in a stated window"), and a classification
whose cut-off you cannot see is a number you cannot argue with. The thresholds are module
constants, the screen prints them, and a test pins every edge — the pattern `AGE_BUCKETS`
established in C2.

**One definition of demand, shared by three outputs.** `InventoryRepository.consumption`
counts only `SALE` movements, so ABC, the dead-stock radar and the fast/slow split cannot
disagree about what "moves" means. A transfer is the same units relocating, a putaway is
re-addressing, and a negative adjustment is a correction — none of them is demand, and
counting them would put products in the wrong class and hide dead stock.

**R7.11: reorder suggestions are NOT implemented here.** `reorder_suggestions` delegates to
Part 4's `RecommendationService.recommend` and returns its rows unchanged. Two answers to
"what should I buy" is the specific failure R5.9/R7.11 exist to prevent, Part 4 left a source
walk that fails if a second `def recommend` appears anywhere in `app/`, and R7.13 asserts this
delegation is a pure passthrough.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.money import minor_to_text, qty_text
from app.db.explain import Explained, Input, SourceRecord
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    ABC_CLASSES,
    DEAD_STOCK_DAYS,
    MOVEMENT_WINDOW_DAYS,
    SLOW_MOVER_MAX_PER_MONTH,
    AbcRow,
    DeadStockRow,
    LowStockRow,
    MovementRow,
)
from app.modules.inventory.service import InventoryService
from app.modules.inventory.valuation import ValuationService


class InventoryHealthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InventoryRepository(db)
        self.inventory = InventoryService(db)
        self.valuation = ValuationService(db)

    # --- shared inputs ---------------------------------------------------

    def _window_start(self, days: int, *, as_of: datetime) -> datetime:
        return as_of - timedelta(days=days)

    def _consumption(self, *, days: int, as_of: datetime) -> dict[uuid.UUID, tuple]:
        """(qty, movement count) per product over the window — one query."""
        return {
            pid: (Decimal(qty or 0), int(count or 0))
            for pid, qty, count in self.repo.consumption(
                self._window_start(days, as_of=as_of)
            )
        }

    # --- R7.7: ABC ------------------------------------------------------

    def abc(
        self, *, days: int = MOVEMENT_WINDOW_DAYS, as_of: datetime | None = None
    ) -> list[AbcRow]:
        """Classify products by consumption VALUE over a stated window.

        Textbook ABC: rank by value consumed, then walk the ranking accumulating share of
        the total. `ABC_CLASSES` holds the cumulative cut-offs, and the **upper bound is
        inclusive** — a product landing exactly on 80% is class A, matching how
        `AGE_BUCKETS` treats its edges, so the two do not disagree about what a boundary means.

        A product that consumed nothing in the window has no share of the total and is
        classified `C` with a zero value: it is genuinely the lowest-priority stock, and
        leaving it unclassified would drop it off the screen entirely.
        """
        as_of = as_of or datetime.now(UTC)
        consumed = self._consumption(days=days, as_of=as_of)
        # ONE pass over stock_value(): it is two grouped queries plus arithmetic, and
        # calling it once for the cost basis and again for the names would double that.
        basis: dict[uuid.UUID, int | None] = {}
        names: dict[uuid.UUID, tuple[str, str]] = {}
        for row in self.valuation.stock_value():
            basis[row.product_id] = row.cost_basis_minor
            names[row.product_id] = (row.sku_code, row.product_name)

        valued: list[tuple[uuid.UUID, Decimal, int]] = []
        for pid in names:
            qty, _movements = consumed.get(pid, (Decimal(0), 0))
            cost = basis.get(pid)
            value = Decimal(0) if cost is None else qty * Decimal(cost)
            valued.append((pid, qty, int(value)))
        valued.sort(key=lambda r: -r[2])

        total = sum(v for _pid, _qty, v in valued)
        rows: list[AbcRow] = []
        running = 0
        for pid, qty, value in valued:
            running += value
            share = Decimal(0) if total == 0 else Decimal(running) / Decimal(total)
            sku, name = names[pid]
            rows.append(
                AbcRow(
                    product_id=pid,
                    sku_code=sku,
                    product_name=name,
                    qty_consumed=qty,
                    value_minor=value,
                    cumulative_share_bps=int(share * 10000),
                    abc_class=abc_class_for(share) if value > 0 else "C",
                    window_days=days,
                )
            )
        return rows

    def abc_explained(self, row: AbcRow, *, total_minor: int) -> Explained:
        return Explained(
            what=f"ABC class — {row.sku_code}",
            value=row.abc_class,
            formula=(
                "products ranked by value consumed, then classified by cumulative share "
                "of the total: "
                + ", ".join(
                    f"{key} up to {int(bound * 100)}%" for key, bound in ABC_CLASSES
                )
                + " (upper bound inclusive)"
            ),
            window=f"the last {row.window_days} days of sales",
            inputs=(
                Input(label="Quantity sold", value=qty_text(row.qty_consumed)),
                Input(label="Value sold", value=minor_to_text(row.value_minor)),
                Input(
                    label="Cumulative share",
                    value=f"{row.cumulative_share_bps / 100:.1f}%",
                ),
                Input(label="Total sold, all products", value=minor_to_text(total_minor)),
            ),
            records=(SourceRecord(label="sales movements in the window"),),
            caveat=(
                "Only sales count as consumption. Transfers, putaway, adjustments and "
                "counts move or correct stock without it being sold."
            ),
        )

    # --- R7.8: dead stock ------------------------------------------------

    def dead_stock(
        self, *, days: int = DEAD_STOCK_DAYS, as_of: datetime | None = None
    ) -> list[DeadStockRow]:
        """Stock on hand that has not SOLD within the window.

        **The measure is the last sale, not the last movement of any kind.** A product
        nobody has bought for a year is dead even if it was counted last week, and using
        "any movement" would let a cycle count or a putaway make dead stock look alive —
        precisely what the radar exists to catch. It also only reports products that still
        HAVE stock: nothing on hand is not dead capital, it is just discontinued.

        The boundary is stated and tested: dead means days-since-sale **strictly greater
        than** the window, so a product that sold exactly `days` ago is not yet dead.
        """
        as_of = as_of or datetime.now(UTC)
        last_sold = {
            pid: at for pid, at in self.repo.last_consumption_at() if at is not None
        }
        rows: list[DeadStockRow] = []
        for value_row in self.valuation.stock_value():
            if value_row.qty_on_hand <= 0:
                continue
            sold_at = last_sold.get(value_row.product_id)
            days_since = None
            if sold_at is not None:
                if sold_at.tzinfo is None:
                    sold_at = sold_at.replace(tzinfo=UTC)
                days_since = max((as_of - sold_at).days, 0)
            # Never sold at all, with stock on hand, is the deadest case there is.
            is_dead = days_since is None or days_since > days
            if not is_dead:
                continue
            rows.append(
                DeadStockRow(
                    product_id=value_row.product_id,
                    sku_code=value_row.sku_code,
                    product_name=value_row.product_name,
                    qty_on_hand=value_row.qty_on_hand,
                    value_minor=value_row.value_minor,
                    days_since_sale=days_since,
                    window_days=days,
                )
            )
        # Worst first: never-sold, then longest idle, then most capital tied up.
        rows.sort(key=lambda r: (-(r.days_since_sale or 10**6), -(r.value_minor or 0)))
        return rows

    def dead_stock_explained(self, row: DeadStockRow) -> Explained:
        return Explained(
            what=f"Dead stock — {row.sku_code}",
            value=(
                "never sold"
                if row.days_since_sale is None
                else f"{row.days_since_sale} days since a sale"
            ),
            formula=(
                f"on hand, and no sale in the last {row.window_days} days "
                f"(strictly more than {row.window_days} days counts as dead)"
            ),
            window=f"the last {row.window_days} days",
            inputs=(
                Input(label="On hand", value=qty_text(row.qty_on_hand)),
                Input(
                    label="Capital tied up",
                    value=(
                        minor_to_text(row.value_minor)
                        if row.value_minor is not None
                        else "unknown"
                    ),
                    missing_reason=(
                        None if row.value_minor is not None else "no cost basis on record"
                    ),
                ),
            ),
            records=(SourceRecord(label=f"{row.sku_code} stock ledger"),),
            caveat=(
                "Measured from the last SALE, not the last movement: a cycle count or a "
                "putaway does not make stock alive again."
            ),
        )

    # --- R7.9: fast and slow movers --------------------------------------

    def movement_rates(
        self, *, days: int = MOVEMENT_WINDOW_DAYS, as_of: datetime | None = None
    ) -> list[MovementRow]:
        """Units sold per month over the window, with the numbers behind it (R7.9)."""
        as_of = as_of or datetime.now(UTC)
        consumed = self._consumption(days=days, as_of=as_of)
        months = Decimal(days) / Decimal(30)
        rows: list[MovementRow] = []
        for value_row in self.valuation.stock_value():
            qty, movements = consumed.get(value_row.product_id, (Decimal(0), 0))
            per_month = (qty / months) if months else Decimal(0)
            rows.append(
                MovementRow(
                    product_id=value_row.product_id,
                    sku_code=value_row.sku_code,
                    product_name=value_row.product_name,
                    qty_consumed=qty,
                    movements=movements,
                    per_month=per_month.quantize(Decimal("0.01")),
                    window_days=days,
                    is_fast=per_month > Decimal(SLOW_MOVER_MAX_PER_MONTH),
                )
            )
        rows.sort(key=lambda r: -r.per_month)
        return rows

    # --- R7.10: low stock -------------------------------------------------

    def low_stock(self) -> list[LowStockRow]:
        """Products below their reorder level, with what triggered it (R7.10).

        Available, not on-hand, is the trigger: stock already committed to an order cannot
        cover a new one, so a product with 50 on hand and 45 reserved is short.

        The reorder levels are read **once** into a dict keyed on product. Part 9 measured
        this method at 274 queries and 979 ms of a 344-query homepage: `stock()` is a
        grouped read of the whole catalogue and it was being re-executed inside the loop,
        once per state row, then linearly scanned. `setdefault` keeps the first row per
        product, which is exactly what the `next(...)` it replaces selected.
        """
        levels: dict[uuid.UUID, Decimal] = {}
        for row in self.inventory.stock():
            levels.setdefault(row.product_id, row.reorder_level)

        rows: list[LowStockRow] = []
        for state in self.inventory.states():
            level = levels.get(state.product_id, Decimal(0))
            if level <= 0 or state.available >= level:
                continue
            rows.append(
                LowStockRow(
                    product_id=state.product_id,
                    sku_code=state.sku_code,
                    product_name=state.product_name,
                    warehouse_id=state.warehouse_id,
                    warehouse_name=state.warehouse_name,
                    available=state.available,
                    on_hand=state.on_hand,
                    reserved=state.reserved,
                    reorder_level=level,
                )
            )
        rows.sort(key=lambda r: r.shortfall, reverse=True)
        return rows

    def low_stock_explained(self, row: LowStockRow) -> Explained:
        return Explained(
            what=f"Low stock — {row.sku_code} at {row.warehouse_name}",
            value=f"{qty_text(row.shortfall)} short",
            formula=(
                f"available {qty_text(row.available)} is below the reorder level "
                f"{qty_text(row.reorder_level)}"
            ),
            window="current balances",
            inputs=(
                Input(label="On hand", value=qty_text(row.on_hand)),
                Input(label="Reserved", value=qty_text(row.reserved)),
                Input(label="Available", value=qty_text(row.available)),
                Input(label="Reorder level (the trigger)", value=qty_text(row.reorder_level)),
            ),
            records=(
                SourceRecord(
                    label=f"{row.sku_code} at {row.warehouse_name}",
                    href=f"/products/{row.product_id}",
                ),
            ),
            caveat=(
                "Triggered on AVAILABLE, not on hand: stock already committed to an order "
                "cannot cover a new one."
            ),
        )

    # --- R7.11: reorder suggestions, READ from Part 4's engine ------------

    def reorder_suggestions(
        self, *, product_id: uuid.UUID | None = None, limit: int | None = None
    ):
        """R7.11 — Part 4's engine, unchanged. **Not a second implementation.**

        Deliberately a bare delegation with no filtering, re-sorting or re-shaping: the
        moment this adds logic, the inventory screen and the procurement screen start
        answering "what should I buy" differently, which is the failure R5.9 exists to
        prevent. R7.13 asserts the passthrough is exact.
        """
        from app.modules.procurement.recommend import RecommendationService

        return RecommendationService(self.db).recommend(product_id=product_id, limit=limit)


def abc_class_for(cumulative_share: Decimal) -> str:
    """Which ABC class a cumulative share falls in. **Upper bounds inclusive** (R7.7)."""
    for key, bound in ABC_CLASSES:
        if cumulative_share <= bound:
            return key
    return ABC_CLASSES[-1][0]
