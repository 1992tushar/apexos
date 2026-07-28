"""Vendor intelligence (R5.2–R5.6) — measured, explained, and never stored.

Everything this module produces is DERIVED from what parts 1–3 already wrote:
`purchase_order.confirmed_at`, `goods_receipt.received_at`, the append-only
`supplier_evaluation` scorecard, and `purchase_price`. Nothing here is a stored
number (G7, R5.10), so a score can never drift out of step with the ledger it
came from.

Every public method returns an `Explained` (see `app/db/explain.py`) carrying the
value, the formula, the data window and the records it reasoned from, because G11
makes that mandatory rather than optional. Where the history is not there, the
return is `Explained.unknown(...)` and the screen says "unknown" — never 0, never
50 (R5.11).

Three deliberate decisions, recorded because a later part will wonder:

1. **Lead time is measured, never typed** (R5.3). `SupplierQuotation.lead_time_days`
   is what a supplier *promised* and is left alone; the gap between promised and
   measured is surfaced as a caveat, because that gap is the useful signal.
2. **On time means received on or before the promised date** (R5.4) — the boundary
   is `<=`, so arriving exactly on the promised date counts as on time. Receipts
   against an order nobody promised a date for are EXCLUDED from the rate rather
   than counted as met; assuming success from missing data is how a score starts
   lying.
3. **The vendor score renormalises over the inputs it actually has.** R5.2 wants the
   scorecard and on-time history weighted together. When only one is present the
   remaining weight is redistributed and the screen says so, which is transparent
   arithmetic a founder can redo. When NEITHER is present the score is unknown.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.explain import Explained, Input, SourceRecord
from app.modules.pricing.models import PurchasePrice
from app.modules.procurement.models import GoodsReceipt, PurchaseOrder
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.repository import SupplierRepository

#: How many of the most recent receipts the trailing average reads. Stated on
#: screen as part of the window, so changing it changes what the founder is told.
LEAD_TIME_WINDOW = 12

#: R5.2's weighting. Percentages, and they must total 100.
WEIGHT_SCORECARD = 60
WEIGHT_ON_TIME = 40

#: The scorecard is 1–5; on-time is a percentage. Both are put on a 0–100 scale
#: before weighting, and that conversion is shown rather than hidden.
SCORECARD_MAX = 5


@dataclass(frozen=True)
class Receipt:
    """One confirm→receipt pair: the raw material for lead time and on-time rate."""

    receipt_no: str
    po_no: str
    purchase_order_id: uuid.UUID
    confirmed_on: date
    received_on: date
    expected_on: date | None

    @property
    def lead_days(self) -> int:
        return (self.received_on - self.confirmed_on).days

    @property
    def is_on_time(self) -> bool | None:
        """None when nobody promised a date — excluded, not counted as met (R5.4)."""
        if self.expected_on is None:
            return None
        return self.received_on <= self.expected_on


@dataclass(frozen=True)
class PriceHistoryRow:
    """One price a supplier charged for a product, and when it applied (R5.6)."""

    supplier_id: uuid.UUID | None
    supplier_name: str
    price_minor: int
    valid_from: date
    valid_to: date | None
    is_current: bool
    #: Change from the previous price for this supplier, in minor units. None on the first.
    delta_minor: int | None


def _mean(values: list[int]) -> int:
    """Integer mean, half-up. No float anywhere in a computed figure."""
    total = Decimal(sum(values))
    return int(
        (total / Decimal(len(values))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def _window(receipts: list[Receipt]) -> str:
    """The data window, phrased for the screen."""
    n = len(receipts)
    if not n:
        return "no receipts yet"
    first = min(r.received_on for r in receipts)
    last = max(r.received_on for r in receipts)
    noun = "receipt" if n == 1 else "receipts"
    if first == last:
        return f"{n} {noun}, {first.isoformat()}"
    return f"{n} {noun}, {first.isoformat()} to {last.isoformat()}"


def _records(receipts: list[Receipt], limit: int = 5) -> tuple[SourceRecord, ...]:
    """G11's "links to the records it reasoned from"."""
    out = [
        SourceRecord(
            label=f"{r.po_no} → {r.receipt_no} ({r.lead_days}d)",
            href=f"/purchase-orders/{r.purchase_order_id}",
        )
        for r in receipts[:limit]
    ]
    if len(receipts) > limit:
        out.append(SourceRecord(label=f"and {len(receipts) - limit} more"))
    return tuple(out)


class VendorIntelService:
    """Reads only — this writes no rows and logs no activity (G15)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SupplierRepository(db)

    # --- the raw history ------------------------------------------------

    def receipts(self, supplier_id: uuid.UUID) -> list[Receipt]:
        """Confirmed→received pairs for one supplier, newest first.

        Only receipts that can actually be measured: the order must have been
        confirmed and the receipt must have been stamped. Part 3 C2 persisted both
        timestamps for exactly this.
        """
        rows = self.db.execute(
            select(
                GoodsReceipt.receipt_no,
                PurchaseOrder.po_no,
                PurchaseOrder.id,
                PurchaseOrder.confirmed_at,
                GoodsReceipt.received_at,
                PurchaseOrder.expected_date,
            )
            .join(PurchaseOrder, PurchaseOrder.id == GoodsReceipt.purchase_order_id)
            .where(
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.confirmed_at.is_not(None),
                GoodsReceipt.received_at.is_not(None),
                GoodsReceipt.deleted_at.is_(None),
                PurchaseOrder.deleted_at.is_(None),
            )
            .order_by(GoodsReceipt.received_at.desc())
        ).all()
        return [
            Receipt(
                receipt_no=receipt_no,
                po_no=po_no,
                purchase_order_id=po_id,
                confirmed_on=confirmed_at.date(),
                received_on=received_at.date(),
                expected_on=expected_date,
            )
            for receipt_no, po_no, po_id, confirmed_at, received_at, expected_date in rows
        ]

    # --- R5.3 measured lead time ---------------------------------------

    def lead_time(self, supplier_id: uuid.UUID) -> Explained:
        """Trailing mean of confirm→receipt, in days. Measured, never typed (R5.3)."""
        history = self.receipts(supplier_id)[:LEAD_TIME_WINDOW]
        what = (
            "Average days from confirming a purchase order with this supplier to the "
            "goods arriving. Measured from the order and receipt timestamps — there is "
            "no lead-time field to type into."
        )
        formula = (
            "mean(receipt date − order confirmed date) over the "
            f"{LEAD_TIME_WINDOW} most recent receipts"
        )
        if not history:
            return Explained.unknown(
                what=what,
                formula=formula,
                reason=(
                    "No confirmed order from this supplier has been received yet, so "
                    "there is nothing to measure."
                ),
            )
        days = [r.lead_days for r in history]
        mean = _mean(days)
        promised = self._promised_days(supplier_id)
        caveat = None
        if promised is not None and promised != mean:
            direction = "slower" if mean > promised else "faster"
            caveat = (
                f"Quoted {promised} days, measuring {mean} — "
                f"{abs(mean - promised)} days {direction} than promised."
            )
        return Explained(
            what=what,
            value=f"{mean} days",
            formula=f"{formula} = ({' + '.join(str(d) for d in days)}) ÷ {len(days)}",
            window=_window(history),
            inputs=(
                Input(label="Receipts measured", value=str(len(days))),
                Input(label="Fastest", value=f"{min(days)} days"),
                Input(label="Slowest", value=f"{max(days)} days"),
            ),
            records=_records(history),
            caveat=caveat,
        )

    def _promised_days(self, supplier_id: uuid.UUID) -> int | None:
        """The most recent lead time this supplier QUOTED, for the promised-vs-measured gap.

        Never written back onto anything — `SupplierQuotation.lead_time_days` stays
        the supplier's claim (R5.3's note on the model).
        """
        from app.modules.procurement.models import SupplierQuotation

        return self.db.scalar(
            select(SupplierQuotation.lead_time_days)
            .where(
                SupplierQuotation.supplier_id == supplier_id,
                SupplierQuotation.lead_time_days.is_not(None),
                SupplierQuotation.deleted_at.is_(None),
            )
            .order_by(SupplierQuotation.quoted_on.desc())
            .limit(1)
        )

    # --- R5.4 on-time rate ---------------------------------------------

    def on_time_rate(self, supplier_id: uuid.UUID) -> Explained:
        """Share of receipts that arrived on or before the promised date.

        **The boundary is explicit (R5.4): arriving exactly on the promised date
        counts as ON TIME.** Receipts against an order with no promised date are
        excluded from both numerator and denominator.
        """
        history = self.receipts(supplier_id)
        judged = [r for r in history if r.is_on_time is not None]
        unpromised = len(history) - len(judged)
        what = (
            "Share of this supplier's deliveries that arrived on or before the date "
            "they promised. Arriving exactly on the promised date counts as on time."
        )
        formula = "on-time receipts ÷ receipts with a promised date × 100"
        if not judged:
            reason = (
                "No receipt from this supplier has a promised delivery date to judge "
                "against, so on-time performance cannot be measured."
                if history
                else "No confirmed order from this supplier has been received yet."
            )
            return Explained.unknown(
                what=what,
                formula=formula,
                reason=reason,
                window=_window(history),
                records=_records(history),
            )
        on_time = [r for r in judged if r.is_on_time]
        pct = _mean([100 if r.is_on_time else 0 for r in judged])
        late = [r for r in judged if not r.is_on_time]
        inputs = [
            Input(label="On time", value=f"{len(on_time)} of {len(judged)}"),
            Input(label="Late", value=str(len(late))),
        ]
        if unpromised:
            inputs.append(
                Input(
                    label="Excluded",
                    value=f"{unpromised} receipt(s) with no promised date",
                )
            )
        return Explained(
            what=what,
            value=f"{pct}%",
            formula=f"{len(on_time)} ÷ {len(judged)} × 100 = {pct}%",
            window=_window(judged),
            inputs=tuple(inputs),
            records=_records(late or judged),
            caveat=(
                f"{unpromised} receipt(s) had no promised date and are excluded — "
                "they are not counted as met."
            )
            if unpromised
            else None,
        )

    # --- R5.2 vendor score ---------------------------------------------

    def score(self, supplier_id: uuid.UUID) -> Explained:
        """The scorecard and on-time history, weighted (R5.2).

        Renormalises over whatever inputs exist and says so on screen; unknown only
        when neither input is available (R5.11).
        """
        scorecard = self.repo.latest_score(supplier_id)
        evaluations = self.repo.evaluation_count(supplier_id)
        on_time = self.on_time_rate(supplier_id)
        what = (
            "Overall vendor score out of 100, combining the human scorecard "
            f"(quality/price/reliability, {WEIGHT_SCORECARD}%) with measured on-time "
            f"delivery ({WEIGHT_ON_TIME}%)."
        )
        base_formula = (
            f"scorecard ÷ {SCORECARD_MAX} × 100 × {WEIGHT_SCORECARD}% "
            f"+ on-time % × {WEIGHT_ON_TIME}%"
        )
        have_card = scorecard is not None
        have_time = on_time.is_known
        if not have_card and not have_time:
            return Explained.unknown(
                what=what,
                formula=base_formula,
                reason=(
                    "This supplier has neither a scorecard nor a measurable delivery "
                    "history yet. Record an evaluation or receive a confirmed order."
                ),
                inputs=(
                    Input(
                        label="Scorecard",
                        value="",
                        weight=f"{WEIGHT_SCORECARD}%",
                        missing_reason="never evaluated",
                    ),
                    Input(
                        label="On-time delivery",
                        value="",
                        weight=f"{WEIGHT_ON_TIME}%",
                        missing_reason=on_time.unknown_reason,
                    ),
                ),
            )

        card_pct = (
            int(
                (Decimal(scorecard) / Decimal(SCORECARD_MAX) * 100).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            if have_card
            else None
        )
        time_pct = int(on_time.value.rstrip("%")) if have_time else None

        # Renormalise the weights over the inputs actually present, and show it.
        terms: list[tuple[str, int, int]] = []  # (label, value_pct, weight)
        if have_card:
            terms.append(("scorecard", card_pct, WEIGHT_SCORECARD))
        if have_time:
            terms.append(("on-time", time_pct, WEIGHT_ON_TIME))
        weight_total = sum(w for _, _, w in terms)
        weighted = sum(Decimal(v) * Decimal(w) for _, v, w in terms)
        total = int(
            (weighted / Decimal(weight_total)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

        shown_formula = " + ".join(
            f"{v} × {w}÷{weight_total}" for _, v, w in terms
        ) + f" = {total}"
        inputs = [
            Input(
                label="Scorecard",
                value=f"{scorecard}/{SCORECARD_MAX} → {card_pct}"
                if have_card
                else "",
                weight=f"{WEIGHT_SCORECARD}%"
                if weight_total == 100
                else f"{WEIGHT_SCORECARD}÷{weight_total}",
                missing_reason=None if have_card else "never evaluated",
            ),
            Input(
                label="On-time delivery",
                value=f"{time_pct}" if have_time else "",
                weight=f"{WEIGHT_ON_TIME}%"
                if weight_total == 100
                else f"{WEIGHT_ON_TIME}÷{weight_total}",
                missing_reason=None if have_time else on_time.unknown_reason,
            ),
        ]
        caveat = None
        if weight_total != 100:
            present = terms[0][0]
            caveat = (
                f"Only the {present} input exists, so it carries the whole score. "
                "The missing input is not assumed to be good or bad."
            )
        return Explained(
            what=what,
            value=str(total),
            formula=shown_formula,
            window=(
                f"{evaluations} evaluation(s); {on_time.window}"
                if have_card
                else on_time.window
            ),
            inputs=tuple(inputs),
            records=on_time.records,
            caveat=caveat,
        )

    # --- R5.6 price history --------------------------------------------

    def price_history(self, product_id: uuid.UUID) -> list[PriceHistoryRow]:
        """Every purchase price recorded for a product, per supplier, oldest first.

        Reads `purchase_price` — which already carries `supplier_id` and a
        `valid_from`/`valid_to` window — so R5.6 needs no new table.
        """
        rows = self.db.execute(
            select(
                PurchasePrice.supplier_id,
                Supplier.name,
                PurchasePrice.price_minor,
                PurchasePrice.valid_from,
                PurchasePrice.valid_to,
            )
            .outerjoin(Supplier, Supplier.id == PurchasePrice.supplier_id)
            .where(
                PurchasePrice.product_id == product_id,
                PurchasePrice.deleted_at.is_(None),
            )
            .order_by(PurchasePrice.valid_from.asc())
        ).all()
        previous: dict[uuid.UUID | None, int] = {}
        history: list[PriceHistoryRow] = []
        for supplier_id, name, price_minor, valid_from, valid_to in rows:
            prior = previous.get(supplier_id)
            history.append(
                PriceHistoryRow(
                    supplier_id=supplier_id,
                    supplier_name=name or "List price (no supplier)",
                    price_minor=int(price_minor),
                    valid_from=valid_from.date() if hasattr(valid_from, "date") else valid_from,
                    valid_to=(
                        valid_to.date() if valid_to is not None and hasattr(valid_to, "date")
                        else valid_to
                    ),
                    is_current=valid_to is None,
                    delta_minor=None if prior is None else int(price_minor) - prior,
                )
            )
            previous[supplier_id] = int(price_minor)
        return history

    def product_name(self, product_id: uuid.UUID) -> str | None:
        return self.db.scalar(select(Product.name).where(Product.id == product_id))
