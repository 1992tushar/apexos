"""Customer health score (R9.10/R9.11) — four measured inputs, weighted and explained.

**Reads only, stores nothing** (G15/G7): there is no score column and no cached rating. The
score is recomputed per read from records that already exist.

Modelled on Part 4's `VendorIntelService.score`, which is the house pattern for a weighted
figure: each input is put on a 0–100 scale, the conversion is *shown* rather than hidden, and
the weights **renormalise over whichever inputs actually exist**. A customer with orders but
no invoices yet is scored on what is known, with a caveat naming what was left out — that is
transparent arithmetic a founder can redo. Only when NO input is available is the score
`unknown` (R9.11), because inventing 50 for a brand-new customer would read as a fact.

The four inputs, and why each is measured the way it is:

* **Frequency** — orders per month over the window. Capped at a target rather than unbounded:
  the difference between four orders a month and forty is not what this score is for.
* **Profitability** — gross margin on their order lines, through `MarginService.gp_costed`.
  The EXISTING margin logic (R11.6): selling minus the buy price, never a valuation layer.
  A line whose product has no recorded purchase price is **excluded and counted**, not scored
  at a 100% margin — Part 10's R13.2 unification, and the same treatment
  `MarginAnalysisService` has always given those lines.
* **Payment** — how much of what they owe is past its due date. Being *late* is what costs,
  not merely being invoiced, so an invoiced-and-settled customer scores full marks. A customer
  who has **never been invoiced** is a MISSING input, not a perfect one: there is no behaviour
  to judge. Collapsing those two cases made a brand-new customer score 100, which is a worse
  lie than the default number R9.11 forbids, because it reads as a compliment.
* **Recency** — days since their last order, decaying to zero at the stale threshold.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.money import minor_to_text
from app.db.explain import Explained, Input, SourceRecord
from app.modules.customers.repository import CustomerRepository

# Weights, in percent. They sum to 100 and renormalise when an input is missing.
WEIGHT_FREQUENCY = 25
WEIGHT_PROFITABILITY = 30
WEIGHT_PAYMENT = 25
WEIGHT_RECENCY = 20

# The window every rate is measured over.
WINDOW_DAYS = 365

# Orders per month that counts as full marks. Beyond this the score does not keep climbing —
# the difference between a weekly and a daily customer is not what this figure is for.
TARGET_ORDERS_PER_MONTH = Decimal("4")

# Gross margin percentage that counts as full marks.
TARGET_MARGIN_PCT = Decimal("25")

# Days since the last order at which recency scores zero.
RECENCY_STALE_DAYS = 180


def _aware(value) -> datetime:
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), tzinfo=UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _clamp_pct(value: Decimal) -> Decimal:
    return max(Decimal(0), min(Decimal(100), value))


class CustomerHealthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CustomerRepository(db)

    # --- the four inputs --------------------------------------------------

    def _orders(self, customer_id: uuid.UUID, *, since: datetime):
        from app.modules.sales.models import SalesOrder

        return list(
            self.db.scalars(
                select(SalesOrder).where(
                    SalesOrder.customer_id == customer_id,
                    SalesOrder.deleted_at.is_(None),
                    SalesOrder.status != "cancelled",
                )
            )
        )

    def frequency(self, customer_id: uuid.UUID, *, as_of: datetime) -> tuple[Decimal | None, int]:
        """(orders per month, order count in the window). None when they have never ordered."""
        since = as_of - timedelta(days=WINDOW_DAYS)
        orders = [
            o
            for o in self._orders(customer_id, since=since)
            if _aware(o.order_date) >= since
        ]
        if not orders:
            return None, 0
        months = Decimal(WINDOW_DAYS) / Decimal(30)
        return (Decimal(len(orders)) / months).quantize(Decimal("0.01")), len(orders)

    def profitability(self, customer_id: uuid.UUID, *, as_of: datetime):
        """(margin %, revenue minor, gp minor, uncosted line count) over the window.

        Margin % is None when there is no revenue this profitability can be measured on —
        either no order lines at all, or none whose product has a recorded purchase price.

        **Part 10 changed this (R13.2).** It used to call `MarginService.gp`, which reads a
        missing purchase price as zero and therefore reports the line's whole selling value
        as profit. A customer who happened to buy a product nothing had ever been purchased
        for was scored toward a **100% margin** — 30 points of a 100-point score, awarded for
        a number nobody measured, which is precisely the flattering default G11 forbids. It
        was known and recorded at Part 8 C3's close rather than changed, because margin was
        that part's scope and this score was not.

        `gp_costed` is now the one place that decides whether a line is costable at all, and
        uncosted lines are **excluded and counted** — the same treatment
        `MarginAnalysisService` has always given them. The count comes back so `score` can
        name it on screen instead of quietly averaging over fewer lines than it implies.
        """
        from app.modules.pricing.service import MarginService
        from app.modules.sales.models import SalesOrder, SalesOrderLine

        since = as_of - timedelta(days=WINDOW_DAYS)
        lines = list(
            self.db.scalars(
                select(SalesOrderLine)
                .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
                .where(
                    SalesOrder.customer_id == customer_id,
                    SalesOrder.deleted_at.is_(None),
                    SalesOrder.status != "cancelled",
                    SalesOrderLine.deleted_at.is_(None),
                )
            )
        )
        lines = [ln for ln in lines if _aware(ln.order.order_date) >= since]
        if not lines:
            return None, 0, 0, 0

        margin = MarginService(self.db)
        buy_prices = margin.purchase_price_map()
        revenue = 0
        gp = 0
        uncosted = 0
        for line in lines:
            line_gp = margin.gp_costed(line, buy_prices=buy_prices)
            if line_gp is None:
                uncosted += 1
                continue
            revenue += int(line.line_subtotal_minor)
            gp += line_gp

        if revenue <= 0:
            return None, 0, 0, uncosted
        pct = (Decimal(gp) / Decimal(revenue) * 100).quantize(Decimal("0.1"))
        return pct, revenue, gp, uncosted

    def payment(self, customer_id: uuid.UUID, *, as_of: datetime):
        """(overdue minor, outstanding minor, invoice count).

        The invoice COUNT matters as much as the amounts. A customer who has never been
        invoiced owes nothing — but that is not good payment behaviour, it is the absence of
        any behaviour to judge. Scoring it as full marks made a brand-new customer come out
        at 100, which is a worse lie than the default number R9.11 forbids. Payment is
        therefore only measurable once at least one invoice exists.

        Outstanding is the ONE receivable definition — `CustomerRepository.outstanding_minor`,
        already net of credit notes (R9.7).
        """
        from app.modules.finance.models import Invoice, PaymentAllocation

        outstanding = self.repo.outstanding_minor(customer_id)
        invoice_count = self.db.scalar(
            select(func.count()).select_from(Invoice).where(
                Invoice.customer_id == customer_id,
                Invoice.status != "cancelled",
                Invoice.deleted_at.is_(None),
            )
        ) or 0
        today = as_of.date()
        rows = self.db.execute(
            select(
                Invoice.id,
                Invoice.total_minor,
                Invoice.due_date,
                func.coalesce(
                    select(func.sum(PaymentAllocation.amount_minor))
                    .where(PaymentAllocation.invoice_id == Invoice.id)
                    .scalar_subquery(),
                    0,
                ),
            ).where(
                Invoice.customer_id == customer_id,
                Invoice.status != "cancelled",
                Invoice.deleted_at.is_(None),
            )
        ).all()
        overdue = 0
        for _id, total, due, allocated in rows:
            unpaid = int(total) - int(allocated or 0)
            if unpaid > 0 and due is not None and due < today:
                overdue += unpaid
        return overdue, outstanding, int(invoice_count)

    def recency(self, customer_id: uuid.UUID, *, as_of: datetime) -> int | None:
        """Days since their last order, or None if they have never ordered."""
        from app.modules.sales.models import SalesOrder

        last = self.db.scalar(
            select(func.max(SalesOrder.order_date)).where(
                SalesOrder.customer_id == customer_id,
                SalesOrder.deleted_at.is_(None),
                SalesOrder.status != "cancelled",
            )
        )
        if last is None:
            return None
        return max((as_of.date() - last).days, 0)

    # --- R9.10/R9.11: the score ------------------------------------------

    def score(self, customer_id: uuid.UUID, *, as_of: datetime | None = None) -> Explained:
        """The four inputs, weighted, renormalised over what exists, and explained.

        `as_of` is injectable so a test can pin a date rather than depend on when it runs.
        """
        as_of = as_of or datetime.now(UTC)
        customer = self.repo.get(customer_id)
        if customer is None:
            from app.core.errors import NotFoundError

            raise NotFoundError(f"Customer {customer_id} not found")

        rate, order_count = self.frequency(customer_id, as_of=as_of)
        margin_pct, revenue, gp, uncosted_lines = self.profitability(customer_id, as_of=as_of)
        overdue, outstanding, invoice_count = self.payment(customer_id, as_of=as_of)
        days_since = self.recency(customer_id, as_of=as_of)

        what = f"Health score — {customer.name}"
        formula_parts = (
            f"order frequency {WEIGHT_FREQUENCY}%",
            f"profitability {WEIGHT_PROFITABILITY}%",
            f"payment behaviour {WEIGHT_PAYMENT}%",
            f"recency {WEIGHT_RECENCY}%",
        )
        base_formula = "weighted 0–100: " + " + ".join(formula_parts)

        # Each entry: (label, weight, points 0-100 or None, rendered value, missing reason)
        components: list[tuple[str, int, Decimal | None, str, str | None]] = []

        if rate is None:
            components.append(
                ("Order frequency", WEIGHT_FREQUENCY, None, "no orders", "never ordered")
            )
        else:
            points = _clamp_pct(rate / TARGET_ORDERS_PER_MONTH * 100)
            components.append(
                (
                    "Order frequency",
                    WEIGHT_FREQUENCY,
                    points,
                    f"{rate}/month ({order_count} in {WINDOW_DAYS} days)",
                    None,
                )
            )

        if margin_pct is None:
            # Two different reasons, named separately (G11, R13.11). "Nothing invoiced" and
            # "everything they bought has no purchase price behind it" both leave the margin
            # unmeasurable, and a founder can act on the second — record what those products
            # cost — but not on a message describing the first.
            reason = (
                f"none of their {uncosted_lines} order line"
                f"{'' if uncosted_lines == 1 else 's'} has a purchase price recorded"
                if uncosted_lines
                else "nothing invoiced yet"
            )
            components.append(
                ("Profitability", WEIGHT_PROFITABILITY, None, "no measurable margin", reason)
            )
        else:
            points = _clamp_pct(margin_pct / TARGET_MARGIN_PCT * 100)
            value = f"{margin_pct}% margin ({minor_to_text(gp)} on {minor_to_text(revenue)})"
            if uncosted_lines:
                # Averaging over fewer lines than the customer actually bought is defensible;
                # not saying so is not.
                value += (
                    f", excluding {uncosted_lines} line"
                    f"{'' if uncosted_lines == 1 else 's'} with no purchase price"
                )
            components.append(
                ("Profitability", WEIGHT_PROFITABILITY, points, value, None)
            )

        if invoice_count == 0:
            # Never invoiced: there is no payment behaviour to judge. Treating "owes
            # nothing" as perfect made a customer with no history at all score 100.
            components.append(
                (
                    "Payment behaviour",
                    WEIGHT_PAYMENT,
                    None,
                    "never invoiced",
                    "no invoice has been raised yet",
                )
            )
        elif outstanding <= 0 and overdue <= 0:
            # Invoiced and settled — paying up IS the behaviour, and it earns full marks.
            components.append(
                ("Payment behaviour", WEIGHT_PAYMENT, Decimal(100), "nothing outstanding", None)
            )
        else:
            share_overdue = (
                Decimal(overdue) / Decimal(outstanding) if outstanding > 0 else Decimal(1)
            )
            points = _clamp_pct((Decimal(1) - share_overdue) * 100)
            components.append(
                (
                    "Payment behaviour",
                    WEIGHT_PAYMENT,
                    points,
                    f"{minor_to_text(overdue)} overdue of {minor_to_text(outstanding)} outstanding",
                    None,
                )
            )

        if days_since is None:
            components.append(
                ("Recency", WEIGHT_RECENCY, None, "never ordered", "never ordered")
            )
        else:
            points = _clamp_pct(
                (Decimal(RECENCY_STALE_DAYS - days_since) / Decimal(RECENCY_STALE_DAYS)) * 100
            )
            components.append(
                ("Recency", WEIGHT_RECENCY, points, f"{days_since} days since last order", None)
            )

        present = [(label, weight, points) for label, weight, points, _v, _m in components
                   if points is not None]
        if not present:
            # R9.11 — no input at all. Not a default, not a zero.
            return Explained.unknown(
                what=what,
                formula=base_formula,
                reason=(
                    "this customer has no orders, no revenue and no invoices yet — there is "
                    "nothing measured to score"
                ),
                window=f"the last {WINDOW_DAYS} days",
                inputs=tuple(
                    Input(label=label, value=value, weight=f"{weight}%", missing_reason=missing)
                    for label, weight, _p, value, missing in components
                ),
            )

        available_weight = sum(weight for _l, weight, _p in present)
        weighted = sum(points * Decimal(weight) for _l, weight, points in present)
        score = int((weighted / Decimal(available_weight)).quantize(Decimal("1")))

        missing = [label for label, _w, points, _v, _m in components if points is None]
        caveat = None
        if missing:
            caveat = (
                f"{', '.join(missing)} could not be measured, so the remaining "
                f"{available_weight}% of the weighting was renormalised over what is known. "
                f"The score is on a partial basis, not a complete one."
            )

        return Explained(
            what=what,
            value=str(score),
            formula=(
                base_formula
                + f"; measured over {available_weight}% of the weighting"
                if missing
                else base_formula
            ),
            window=f"the last {WINDOW_DAYS} days",
            inputs=tuple(
                Input(
                    label=label,
                    value=(
                        f"{value} → {int(points)}/100" if points is not None else value
                    ),
                    weight=f"{weight}%",
                    missing_reason=missing_reason,
                )
                for label, weight, points, value, missing_reason in components
            ),
            records=(
                SourceRecord(
                    label=customer.name, href=f"/customers/{customer_id}"
                ),
            ),
            caveat=caveat,
        )
