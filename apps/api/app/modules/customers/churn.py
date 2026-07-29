"""Customer churn risk (R13.4) — the ONE new engine Part 10 adds.

Every other radar in Part 10 reads a service that already exists: dead stock has
`InventoryHealthService.dead_stock`, margin leakage has `MarginAnalysisService.leakage`.
Churn had nothing. `CustomerHealthService.recency` is the nearest thing and it is not the
same question: recency says *how long* since they ordered, which is only alarming relative
to how often that customer normally orders. Sixty days is nothing from an annual buyer and
a crisis from a weekly one.

**So the measure is the customer against their own history, never against an average.**
Their cadence is the mean gap between their own orders; the risk is how many of those gaps
have now passed in silence. One number, one comparison, redoable by hand from two dates and
a count (R13.12).

It lives here rather than in the radar screen because a churn score computed in a screen is
exactly the second definition C1 spent a checkpoint removing (R13.2). Nothing is stored
(G7) — there is no `churn_score` column and an `ast` guard fails if one appears.

**One grouped query for every customer.** Part 9 found `stock()` inside a loop and paid 274
queries for it; `CustomerHealthService.recency` is per-customer by design and calling it 253
times to build a radar would repeat that defect exactly.

Two states are deliberately NOT the same, and neither is reported as a number (R13.11):

* **fewer than two orders** — no gap has been observed, so there is no cadence to be late
  against. Not "low risk"; unmeasurable.
* **every order on one date** — a real edge on this seed, where orders share a date. The
  span is zero, so the mean gap is zero, and dividing by it would manufacture an infinity.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.explain import Explained, Input, SourceRecord
from app.modules.customers.models import Customer
from app.modules.finance.ledger import today as finance_today
from app.modules.sales.models import SalesOrder

#: Orders needed before a customer has a *gap* at all. Two orders make one gap; one order
#: makes none, and a rhythm cannot be inferred from a single event.
MIN_ORDERS = 2

#: How many of their own gaps must pass in silence before this is worth a founder's
#: attention. Two, because one gap elapsed is simply the next order not having arrived yet —
#: that is the normal state of every customer for most of their cycle.
AT_RISK_MULTIPLE = Decimal("2")

#: Rows the radar lists. The rest are reachable through the customer list.
DEFAULT_LIMIT = 10


def _as_date(value: date | datetime | None) -> date | None:
    """`order_date` is a Date column but SQLite hands back either. Normalise once."""
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


@dataclass(frozen=True)
class ChurnRisk:
    """One customer measured against their own ordering rhythm.

    `cadence_days` and `multiple` are `None` for the two unmeasurable states above, which
    is why `is_at_risk` tests `multiple is not None` rather than a threshold alone: an
    unknown must never fall through into a comparison and read as a verdict.
    """

    customer_id: uuid.UUID
    customer_name: str
    order_count: int
    first_order: date
    last_order: date
    days_since: int
    #: Mean gap between their own orders — `span / (orders - 1)`. None when unmeasurable.
    cadence_days: Decimal | None
    #: `days_since / cadence_days`. None when the cadence is.
    multiple: Decimal | None
    #: Why the cadence could not be measured, when it could not.
    unknown_reason: str | None = None

    @property
    def is_at_risk(self) -> bool:
        return self.multiple is not None and self.multiple >= AT_RISK_MULTIPLE

    @property
    def href(self) -> str:
        return f"/customers/{self.customer_id}"

    @property
    def detail(self) -> str:
        """The one line the radar prints beside the name."""
        if self.multiple is None:
            return self.unknown_reason or "cadence not measurable"
        return (
            f"{self.days_since} days quiet against a usual {self.cadence_days}-day gap "
            f"— {self.multiple}× their own rhythm"
        )


class ChurnRiskService:
    """Reads only. Writes nothing, stores nothing (G7, G15)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- the measurement ---------------------------------------------------

    def rows(self, *, as_of: date | None = None) -> list[ChurnRisk]:
        """Every customer who has ever ordered, worst multiple first — ONE query.

        Cancelled orders are excluded, matching `CustomerHealthService.frequency`: an order
        that was cancelled is not evidence the customer buys. Customers who have never
        ordered are absent rather than listed as unmeasurable — they are not *at risk of
        leaving*, they have not arrived, and R13.11's "say so" applies to a figure the
        screen is showing, not to every row it could have invented.
        """
        stamp = as_of or finance_today()
        grouped = self.db.execute(
            select(
                Customer.id,
                Customer.name,
                func.count(SalesOrder.id),
                func.min(SalesOrder.order_date),
                func.max(SalesOrder.order_date),
            )
            .join(SalesOrder, SalesOrder.customer_id == Customer.id)
            .where(
                Customer.deleted_at.is_(None),
                SalesOrder.deleted_at.is_(None),
                SalesOrder.status != "cancelled",
            )
            .group_by(Customer.id, Customer.name)
        ).all()

        rows = [
            self._measure(cid, name, int(count), _as_date(first), _as_date(last), stamp)
            for cid, name, count, first, last in grouped
        ]
        # Unmeasurable rows sort last: a screen ordered by risk must not open with the
        # customers whose risk is unknown.
        return sorted(
            rows,
            key=lambda r: (r.multiple is None, -(r.multiple or Decimal(0)), r.customer_name),
        )

    @staticmethod
    def _measure(
        customer_id: uuid.UUID,
        name: str,
        count: int,
        first: date | None,
        last: date | None,
        stamp: date,
    ) -> ChurnRisk:
        days_since = max((stamp - last).days, 0) if last else 0
        span = (last - first).days if (first and last) else 0

        reason = None
        cadence: Decimal | None = None
        multiple: Decimal | None = None
        if count < MIN_ORDERS:
            reason = (
                f"only {count} order on record — one order is not a rhythm, so there is "
                "no usual gap to be late against"
            )
        elif span <= 0:
            reason = (
                f"all {count} orders are dated {last.isoformat() if last else 'the same day'}"
                " — a zero-day span gives no gap to measure"
            )
        else:
            cadence = (Decimal(span) / Decimal(count - 1)).quantize(Decimal("0.1"))
            multiple = (Decimal(days_since) / cadence).quantize(Decimal("0.1"))

        return ChurnRisk(
            customer_id=customer_id,
            customer_name=name,
            order_count=count,
            first_order=first,
            last_order=last,
            days_since=days_since,
            cadence_days=cadence,
            multiple=multiple,
            unknown_reason=reason,
        )

    def at_risk(
        self, *, as_of: date | None = None, limit: int | None = DEFAULT_LIMIT
    ) -> list[ChurnRisk]:
        """Only the rows over the threshold. Empty is a real and common answer."""
        risky = [row for row in self.rows(as_of=as_of) if row.is_at_risk]
        return risky[:limit] if limit else risky

    # --- G11 / R13.10 ------------------------------------------------------

    def explained(self, row: ChurnRisk) -> Explained:
        """The arithmetic on screen, including when there is none to show (R13.11)."""
        what = f"How overdue {row.customer_name}'s next order is, by their own history"
        formula = (
            "mean gap = (last order − first order) ÷ (orders − 1); "
            "risk = days since last order ÷ mean gap"
        )
        window = (
            f"{row.order_count} orders, {row.first_order.isoformat()} to "
            f"{row.last_order.isoformat()}"
        )
        records = (SourceRecord(label=row.customer_name, href=row.href),)

        if row.multiple is None:
            return Explained.unknown(
                what=what,
                formula=formula,
                reason=row.unknown_reason or "cadence not measurable",
                window=window,
                records=records,
            )
        return Explained(
            what=what,
            value=f"{row.multiple}× their usual gap",
            formula=formula,
            window=window,
            inputs=(
                Input(label="Orders in the record", value=str(row.order_count)),
                Input(label="Their usual gap", value=f"{row.cadence_days} days"),
                Input(label="Days since the last order", value=str(row.days_since)),
            ),
            records=records,
            caveat=(
                "The mean gap is a mean — a customer who orders in bursts will look overdue "
                "between bursts. It measures silence against their own past, not intent."
            ),
        )
