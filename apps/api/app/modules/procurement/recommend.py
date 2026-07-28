"""Purchase planning (R5.7–R5.9) — what is due to arrive, and what to order now.

**This module is the ONE place that answers "what should I buy" (R5.9).** Part 5's
reorder suggestions and Part 10's consolidated recommendation layer call
`RecommendationService.recommend(...)`; neither reimplements it. Two implementations
of that question drifting apart is the specific failure R5.9 exists to prevent, and
R7.11/R13.6 check for a second one.

Nothing here is stored (G7, R5.10). A recommendation is recomputed from the ledger
every time it is asked for, so it cannot go stale behind a receipt. There is no ML
and no runtime model call — the whole thing is subtraction, and a founder can redo
it on paper from what the screen shows (G12, G11).

The arithmetic, in full:

    shortfall = reorder level − stock on hand − quantity already on open orders
    suggested = shortfall, raised to the supplier's minimum order quantity if one
                is agreed and the shortfall is below it

Three definitions that matter, all deliberate:

1. **"On open orders" excludes drafts.** `PurchaseOrderService.open_qty` is the one
   definition of an outstanding quantity (R4.9/G7) and it is called here rather than
   re-derived — but a *draft* order is not a commitment to a supplier, so counting it
   would suppress a recommendation for goods nobody has actually ordered. Confirmed
   and partially received count; draft does not.
2. **A stated MOQ raises the quantity and says so.** Ordering 10 units from a supplier
   whose minimum is 100 is not an order, it is a rejected order. The step is shown as
   its own term in the formula rather than folded into the number.
3. **A missing lead time does not suppress the recommendation.** Being short of stock
   is a fact about the ledger; how fast the supplier is, is a separate fact. When the
   lead time is unknown the recommendation still stands and carries the unknown as a
   caveat (R5.11) — refusing to advise because one input is missing would be worse
   than advising with a stated gap.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.explain import Explained, Input, SourceRecord
from app.modules.inventory.models import StockMovement
from app.modules.procurement.models import PurchaseOrder, PurchaseOrderLine
from app.modules.procurement.service import PurchaseOrderService, _qty_text
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.service import ProductSupplierService
from app.modules.suppliers.vendor import LEAD_TIME_WINDOW, VendorIntelService

#: An order that has been placed and has not fully arrived. Deliberately NOT
#: `references.open_po`, which includes "draft" because a draft still *reads* the
#: product it names — a different question from "are these goods coming".
OPEN_PO_STATUSES: tuple[str, ...] = ("confirmed", "partially_received")

#: How many recommendations a screen asks for by default. The engine computes all of
#: them; this only bounds what is rendered, and the caller is told the total.
DEFAULT_LIMIT = 25


@dataclass(frozen=True)
class Recommendation:
    """One "buy this much of this" with its reasoning attached (R5.8).

    `explained` is not decoration: G11 makes it part of the answer, and
    `Recommendation` deliberately has no way to hand out `qty` without it.
    """

    product_id: uuid.UUID
    sku_code: str
    product_name: str
    #: What to order. Never zero — a product that needs nothing yields no row.
    qty: Decimal
    on_hand: Decimal
    reorder_level: Decimal
    on_order: Decimal
    #: Before the MOQ step, so the two can be compared on screen.
    shortfall: Decimal
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    moq: Decimal | None
    #: The supplier's measured lead time, or None when there is no preferred supplier.
    lead_time: Explained | None
    explained: Explained

    @property
    def sentence(self) -> str:
        """R5.8's plain-language line, with the numbers in it.

        "reorder 40 of X — stock 12, reorder level 50, 0 on open PO, lead time 9 days
        measured over 6 receipts"
        """
        parts = [
            f"stock {_qty_text(self.on_hand)}",
            f"reorder level {_qty_text(self.reorder_level)}",
            f"{_qty_text(self.on_order)} on open PO",
        ]
        if self.lead_time is not None and self.lead_time.is_known:
            parts.append(f"lead time {self.lead_time.value} {self.lead_time.window}")
        elif self.supplier_id is None:
            parts.append("no preferred supplier set")
        else:
            parts.append("lead time unknown")
        return (
            f"reorder {_qty_text(self.qty)} of {self.product_name} — " + ", ".join(parts)
        )


@dataclass(frozen=True)
class Arrival:
    """One open purchase order on the calendar's "due to arrive" side (R5.7)."""

    purchase_order_id: uuid.UUID
    po_no: str
    supplier_id: uuid.UUID
    supplier_name: str | None
    status: str
    #: What the supplier committed to for this order. None when nobody promised.
    expected_date: date | None
    open_qty: Decimal
    as_of: date

    @property
    def bucket(self) -> str:
        """Which column of the calendar this sits in.

        An order with no promised date is **unpromised**, never bucketed under today
        (R5.7) — treating "we do not know" as "arriving now" is how a calendar starts
        lying about the week ahead.
        """
        if self.expected_date is None:
            return "unpromised"
        days = (self.expected_date - self.as_of).days
        if days < 0:
            return "overdue"
        if days == 0:
            return "today"
        if days <= 7:
            return "this_week"
        return "later"

    @property
    def days_away(self) -> int | None:
        if self.expected_date is None:
            return None
        return (self.expected_date - self.as_of).days


#: The calendar's columns, in the order a founder reads them, with their labels.
ARRIVAL_BUCKETS: tuple[tuple[str, str], ...] = (
    ("overdue", "Overdue"),
    ("today", "Due today"),
    ("this_week", "Within 7 days"),
    ("later", "Later"),
    ("unpromised", "No date promised"),
)


@dataclass(frozen=True)
class ProcurementCalendar:
    """R5.7 — both halves of the buying week in one read."""

    as_of: date
    arrivals: list[Arrival]
    recommendations: list[Recommendation]
    #: How many recommendations exist in total, when `arrivals`/`recommendations`
    #: were truncated by `limit`. A silently capped list reads as "that is all".
    recommendation_total: int

    def arrivals_in(self, bucket: str) -> list[Arrival]:
        return [a for a in self.arrivals if a.bucket == bucket]


class RecommendationService:
    """R5.9's single entry point. Reads only — writes nothing, logs nothing (G15)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.intel = VendorIntelService(db)
        self.mapping = ProductSupplierService(db)
        # Lead time and receipt counts are per SUPPLIER, and several short products
        # usually share one. Cached for the life of the call rather than re-queried
        # per row.
        self._lead_cache: dict[uuid.UUID, Explained] = {}
        self._receipts_cache: dict[uuid.UUID, int] = {}

    # -- the entry point --------------------------------------------------

    def recommend(
        self,
        *,
        product_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> list[Recommendation]:
        """What to buy now, worst shortfall first.

        `product_id` narrows to one SKU — used by the product page and by Part 5's
        reorder reading. `limit` bounds the result; call it without one to get the
        total, because a silently truncated list reads as "that is everything".

        Returns an empty list when nothing needs ordering. That is an answer, not a
        failure: a product at or above its reorder level with goods already on the
        way must not appear.
        """
        short = self._shortfalls(product_id=product_id)
        rows = [self._build(*row) for row in short]
        rows.sort(key=lambda r: (-r.shortfall, r.sku_code))
        return rows[:limit] if limit else rows

    # -- the arithmetic ---------------------------------------------------

    def _shortfalls(
        self, *, product_id: uuid.UUID | None
    ) -> list[tuple[Product, Decimal, Decimal, list[PurchaseOrder]]]:
        """(product, on_hand, on_order, open orders) for every product that is short.

        Two queries for the whole catalogue, not one per product: stock is summed in
        SQL against `stock_movement` — the same ledger `InventoryService.on_hand`
        reads, so the two cannot disagree (G7) — and the open order lines for the
        survivors come back in a single pass.
        """
        stock = (
            select(
                StockMovement.product_id.label("product_id"),
                func.coalesce(func.sum(StockMovement.qty_delta), 0).label("qty"),
            )
            .where(StockMovement.deleted_at.is_(None))
            .group_by(StockMovement.product_id)
            .subquery()
        )
        stmt = (
            select(Product, func.coalesce(stock.c.qty, 0))
            .outerjoin(stock, stock.c.product_id == Product.id)
            .where(
                Product.deleted_at.is_(None),
                Product.status == "active",
                Product.reorder_level > 0,
                func.coalesce(stock.c.qty, 0) < Product.reorder_level,
            )
        )
        if product_id is not None:
            stmt = stmt.where(Product.id == product_id)
        candidates = [(p, Decimal(qty or 0)) for p, qty in self.db.execute(stmt).all()]
        if not candidates:
            return []

        open_lines = self._open_lines([p.id for p, _ in candidates])
        out = []
        for product, on_hand in candidates:
            lines = open_lines.get(product.id, [])
            on_order = sum(
                (PurchaseOrderService.open_qty(ln) for ln in lines), Decimal("0")
            )
            shortfall = Decimal(product.reorder_level) - on_hand - on_order
            if shortfall <= 0:
                # Short on the shelf, but already covered by what is on the way.
                continue
            orders = []
            seen: set[uuid.UUID] = set()
            for ln in lines:
                if ln.purchase_order_id not in seen:
                    seen.add(ln.purchase_order_id)
                    orders.append(ln.order)
            out.append((product, on_hand, on_order, orders))
        return out

    def _open_lines(
        self, product_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[PurchaseOrderLine]]:
        """Open PO lines for these products, one query, keyed by product."""
        rows = self.db.scalars(
            select(PurchaseOrderLine)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
            .where(
                PurchaseOrderLine.product_id.in_(product_ids),
                PurchaseOrderLine.deleted_at.is_(None),
                PurchaseOrder.deleted_at.is_(None),
                PurchaseOrder.status.in_(OPEN_PO_STATUSES),
            )
        ).all()
        out: dict[uuid.UUID, list[PurchaseOrderLine]] = {}
        for line in rows:
            out.setdefault(line.product_id, []).append(line)
        return out

    def _lead_time(self, supplier_id: uuid.UUID) -> Explained:
        if supplier_id not in self._lead_cache:
            self._lead_cache[supplier_id] = self.intel.lead_time(supplier_id)
            self._receipts_cache[supplier_id] = len(
                self.intel.receipts(supplier_id)[:LEAD_TIME_WINDOW]
            )
        return self._lead_cache[supplier_id]

    def _build(
        self,
        product: Product,
        on_hand: Decimal,
        on_order: Decimal,
        open_orders: list[PurchaseOrder],
    ) -> Recommendation:
        shortfall = Decimal(product.reorder_level) - on_hand - on_order
        supplier_id = self.mapping.preferred_supplier_id(product.id)
        supplier_name = None
        moq = None
        lead: Explained | None = None
        if supplier_id is not None:
            supplier = self.db.get(Supplier, supplier_id)
            supplier_name = supplier.name if supplier else None
            moq = self.mapping.moq(product.id, supplier_id)
            lead = self._lead_time(supplier_id)

        qty = shortfall
        moq_step = None
        if moq is not None and moq > shortfall:
            qty = Decimal(moq)
            moq_step = (
                f"{supplier_name or 'the supplier'} will not take less than "
                f"{_qty_text(moq)}, so the order is raised to it"
            )

        return Recommendation(
            product_id=product.id,
            sku_code=product.sku_code,
            product_name=product.name,
            qty=qty,
            on_hand=on_hand,
            reorder_level=Decimal(product.reorder_level),
            on_order=on_order,
            shortfall=shortfall,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            moq=moq,
            lead_time=lead,
            explained=self._explain(
                product=product,
                on_hand=on_hand,
                on_order=on_order,
                shortfall=shortfall,
                qty=qty,
                moq_step=moq_step,
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                lead=lead,
                open_orders=open_orders,
            ),
        )

    def _explain(
        self,
        *,
        product: Product,
        on_hand: Decimal,
        on_order: Decimal,
        shortfall: Decimal,
        qty: Decimal,
        moq_step: str | None,
        supplier_id: uuid.UUID | None,
        supplier_name: str | None,
        lead: Explained | None,
        open_orders: list[PurchaseOrder],
    ) -> Explained:
        """Everything G11 requires next to the quantity."""
        level = Decimal(product.reorder_level)
        formula = (
            f"reorder level {_qty_text(level)} − stock {_qty_text(on_hand)} − "
            f"{_qty_text(on_order)} already on order = {_qty_text(shortfall)} short"
        )
        if moq_step:
            formula = f"{formula}; {moq_step} = {_qty_text(qty)}"

        inputs = [
            Input(label="Stock on hand", value=_qty_text(on_hand)),
            Input(label="Reorder level", value=_qty_text(level)),
            Input(
                label="Already on open purchase orders",
                value=_qty_text(on_order),
            ),
        ]
        if lead is not None and lead.is_known:
            inputs.append(
                Input(
                    label=f"{supplier_name}'s measured lead time",
                    value=f"{lead.value} ({lead.window})",
                )
            )
        elif supplier_id is None:
            inputs.append(
                Input(
                    label="Preferred supplier",
                    value="",
                    missing_reason="none mapped for this product yet",
                )
            )
        else:
            inputs.append(
                Input(
                    label=f"{supplier_name}'s measured lead time",
                    value="",
                    missing_reason="no confirmed order from them has been received yet",
                )
            )

        records = [SourceRecord(label=product.sku_code, href=f"/products/{product.id}")]
        records += [
            SourceRecord(
                label=f"{order.po_no} open",
                href=f"/purchase-orders/{order.id}",
            )
            for order in open_orders
        ]
        if supplier_id is not None:
            records.append(
                SourceRecord(
                    label=supplier_name or "preferred supplier",
                    href=f"/suppliers/{supplier_id}",
                )
            )

        caveat = None
        if supplier_id is None:
            caveat = (
                "No preferred supplier is mapped to this product, so there is no lead "
                "time behind this and no obvious place to send the order. Map one on "
                "the product page."
            )
        elif lead is not None and not lead.is_known:
            caveat = (
                f"{supplier_name}'s lead time has never been measured, so how early "
                "this needs ordering is unknown. The shortfall itself is measured."
            )

        return Explained(
            what=(
                "How many units to order now so that stock returns to its reorder "
                "level once everything already on order has arrived."
            ),
            value=_qty_text(qty),
            formula=formula,
            window=(
                f"stock and open orders as at {datetime.now(UTC).date().isoformat()}"
            ),
            inputs=tuple(inputs),
            records=tuple(records),
            caveat=caveat,
        )


class ProcurementCalendarService:
    """R5.7 — what is due to arrive, and what is due to order.

    The second half is not computed here: it is `RecommendationService.recommend`,
    called (G16). This class owns only the arrivals.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.recommendations = RecommendationService(db)

    def arrivals(self) -> list[Arrival]:
        """Open orders by promised date, with the unpromised ones last.

        Sorted in Python rather than SQL: a NULL `expected_date` must sort to the
        end regardless of the database's NULLS FIRST/LAST default, and SQLite and
        Postgres disagree about that.
        """
        as_of = datetime.now(UTC).date()
        orders = self.db.scalars(
            select(PurchaseOrder).where(
                PurchaseOrder.deleted_at.is_(None),
                PurchaseOrder.status.in_(OPEN_PO_STATUSES),
            )
        ).all()
        out = []
        for order in orders:
            open_qty = sum(
                (
                    PurchaseOrderService.open_qty(ln)
                    for ln in order.lines
                    if ln.deleted_at is None
                ),
                Decimal("0"),
            )
            if open_qty <= 0:
                continue
            supplier = self.db.get(Supplier, order.supplier_id)
            out.append(
                Arrival(
                    purchase_order_id=order.id,
                    po_no=order.po_no,
                    supplier_id=order.supplier_id,
                    supplier_name=supplier.name if supplier else None,
                    status=order.status,
                    expected_date=order.expected_date,
                    open_qty=open_qty,
                    as_of=as_of,
                )
            )
        out.sort(key=lambda a: (a.expected_date is None, a.expected_date or as_of, a.po_no))
        return out

    def calendar(self, *, limit: int | None = DEFAULT_LIMIT) -> ProcurementCalendar:
        """Both sides of the calendar in one read.

        The recommendations are computed once and then sliced, so the total the
        screen reports costs no second pass.
        """
        everything = self.recommendations.recommend()
        return ProcurementCalendar(
            as_of=datetime.now(UTC).date(),
            arrivals=self.arrivals(),
            recommendations=everything[:limit] if limit else everything,
            recommendation_total=len(everything),
        )
