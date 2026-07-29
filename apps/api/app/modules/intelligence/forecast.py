"""The three forecasts (R13.7, R13.8, R13.12) — purchase, sales, cash requirement.

**Trailing averages and nothing else.** No ML dependency, no runtime LLM (G12): each figure
is one division and one multiplication over a window whose dates are printed on screen, so a
founder can redo it from the same two screens the links point at. A model that cannot be
checked by hand has no place in a number somebody is going to spend money against.

Each forecast reads a service that already owns its trailing figure, so nothing here
measures anything itself (R13.9's discipline, applied one layer down):

    sales             MarginAnalysisService.by_dimension  → tax-exclusive revenue invoiced
    purchase          CashFlowService.cash_flow           → cash actually paid out
    cash requirement  both of the above, projected forward

**Revenue for sales, receipts for cash — deliberately different sources.** A sales forecast
is about what the business will *sell*, which is invoiced revenue; a cash requirement is
about what will *move*, which is money banked and paid. Using one figure for both would make
one of the two answers wrong, and the wrong one would look consistent.

**The cash requirement does not add committed cash to its projection**, and that is the
subtle part. `CashFlowService.committed` counts bills that already exist with a due date
ahead; the trailing payment rate was measured from payments made *against bills like those*.
Adding the two would count the same money twice. So committed is carried alongside as a
documented cross-check and the screen says the two are measured differently — the same habit
Part 8 established when it refused to sum a below-cost loss with a discount give-away.

R13.8 is why `confidence` is a plain `str` and not optional: a forecast whose limitation is
merely *available* is a forecast whose limitation will not be read.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.money import minor_to_text, round_minor
from app.db.explain import Explained, Input, SourceRecord
from app.modules.finance.cash import CashFlowService, default_window
from app.modules.finance.ledger import today as finance_today
from app.modules.finance.margin import MarginAnalysisService

#: How far ahead every forecast projects. One month, because that is the horizon a founder
#: buys and collects against; a 12-month projection off 90 days of history would be four
#: times more confident-looking and no better informed.
HORIZON_DAYS = 30

#: Below this many source documents the trailing rate is a handful of events rather than a
#: rate, and `confidence` says so. Part 9's `THIN_SAMPLE_LINES` marks today's margin the same
#: way, for the same reason: correct arithmetic that reads as precise is worse than arithmetic
#: that admits its base.
THIN_RECORDS = 10


@dataclass(frozen=True)
class Forecast:
    """One projected figure, its window, and its limitation — all three mandatory.

    `value_minor` is money in integer minor units (G1). `explained` carries the arithmetic
    for `explain_panel`; `confidence` is the sentence R13.8 requires and is never empty.
    """

    key: str
    label: str
    value_minor: int
    horizon_days: int
    window_from: date
    window_to: date
    #: R13.8. Always populated — see the module docstring.
    confidence: str
    href: str
    explained: Explained

    @property
    def window_days(self) -> int:
        return (self.window_to - self.window_from).days + 1


def _project(trailing_minor: int, window_days: int, horizon_days: int) -> int:
    """Trailing total → daily rate → horizon total. The only arithmetic in this module.

    Rounded ONCE, at the end, through the one money rounding step (G1). Rounding the daily
    rate first and multiplying would compound the rounding error thirty times over.
    """
    if window_days <= 0:
        return 0
    daily = Decimal(trailing_minor) / Decimal(window_days)
    return round_minor(daily * Decimal(horizon_days))


def _confidence(record_count: int, window_days: int, *, unit: str) -> str:
    """The limitation, stated in full every time (R13.8).

    Two independent weaknesses, both named when both apply: too few documents to average,
    and a window too short to contain a season. The second is true of *every* forecast here
    and is stated even when the first is not, because 90 days of history cannot see an
    annual cycle no matter how many documents it holds.
    """
    seasonal = (
        f"a {window_days}-day window cannot see seasonality — read this as the current "
        "rate continuing, not as a prediction"
    )
    if record_count == 0:
        return f"no {unit} in the window at all, so the projection is zero rather than measured"
    if record_count < THIN_RECORDS:
        return (
            f"LOW confidence: only {record_count} {unit} in the window — a handful of "
            f"documents, not a rate; {seasonal}"
        )
    return f"based on {record_count} {unit}; {seasonal}"


class ForecastService:
    """Reads only. Every trailing figure comes from the part that owns it (G16)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.cash = CashFlowService(db)
        self.margin = MarginAnalysisService(db)

    def all(
        self, *, as_of: date | None = None, horizon_days: int = HORIZON_DAYS
    ) -> list[Forecast]:
        """The three, in the order a founder asks them: what will I sell, buy, and need."""
        stamp = as_of or finance_today()
        window_from, window_to = default_window(as_of=stamp)
        window_days = (window_to - window_from).days + 1

        revenue = self.margin.by_dimension(
            "product", date_from=window_from, date_to=window_to
        )
        flow = self.cash.cash_flow(date_from=window_from, date_to=window_to)

        sales = self._sales(revenue, window_from, window_to, window_days, horizon_days)
        purchase = self._purchase(flow, window_from, window_to, window_days, horizon_days)
        return [
            sales,
            purchase,
            self._cash_requirement(
                sales, purchase, flow, stamp, window_from, window_to, horizon_days
            ),
        ]

    # --- R13.7's three -----------------------------------------------------

    def _sales(self, revenue, window_from, window_to, window_days, horizon) -> Forecast:
        """Invoiced revenue, tax-exclusive, projected at its trailing daily rate.

        Tax-exclusive because that is what `MarginAnalysisService` reports and what the
        business earns — GST collected is the government's money passing through, and a
        sales forecast including it would overstate what the month is worth.
        """
        projected = _project(revenue.revenue_minor, window_days, horizon)
        window = f"{window_from.isoformat()} to {window_to.isoformat()} ({window_days} days)"
        href = (
            f"/finance/margin?date_from={window_from.isoformat()}"
            f"&date_to={window_to.isoformat()}"
        )
        return Forecast(
            key="sales",
            label=f"Sales, next {horizon} days",
            value_minor=projected,
            horizon_days=horizon,
            window_from=window_from,
            window_to=window_to,
            confidence=_confidence(revenue.line_count, window_days, unit="invoice lines"),
            href=href,
            explained=Explained(
                what=f"Revenue expected over the next {horizon} days at the current rate",
                value=minor_to_text(projected),
                formula=(
                    f"trailing revenue ÷ {window_days} days × {horizon} days, "
                    "tax excluded"
                ),
                window=window,
                inputs=(
                    Input(
                        label="Revenue invoiced in the window",
                        value=minor_to_text(revenue.revenue_minor),
                    ),
                    Input(label="Days measured", value=str(window_days)),
                    Input(label="Days projected", value=str(horizon)),
                    Input(label="Invoice lines behind it", value=str(revenue.line_count)),
                ),
                records=(SourceRecord(label="Margin report for the window", href=href),),
                caveat=_confidence(
                    revenue.line_count, window_days, unit="invoice lines"
                ),
            ),
        )

    def _purchase(self, flow, window_from, window_to, window_days, horizon) -> Forecast:
        """Cash paid to suppliers, projected forward.

        **Payments, not bills.** `CashFlowService` is explicit that "actual" cash is
        payments — there is no bank ledger — so this forecasts the money that will leave at
        the rate it has been leaving. A bills-raised rate would answer a different question
        and is already answered by committed cash on the cash-flow screen.
        """
        projected = _project(flow.actual_out_minor, window_days, horizon)
        window = f"{window_from.isoformat()} to {window_to.isoformat()} ({window_days} days)"
        href = (
            f"/finance/cash-flow?date_from={window_from.isoformat()}"
            f"&date_to={window_to.isoformat()}"
        )
        payments = sum(row.payments for row in flow.rows)
        return Forecast(
            key="purchase",
            label=f"Purchase outflow, next {horizon} days",
            value_minor=projected,
            horizon_days=horizon,
            window_from=window_from,
            window_to=window_to,
            confidence=_confidence(payments, window_days, unit="supplier payments"),
            href=href,
            explained=Explained(
                what=f"Cash expected to leave for suppliers over the next {horizon} days",
                value=minor_to_text(projected),
                formula=f"trailing supplier payments ÷ {window_days} days × {horizon} days",
                window=window,
                inputs=(
                    Input(
                        label="Paid out in the window",
                        value=minor_to_text(flow.actual_out_minor),
                    ),
                    Input(label="Days measured", value=str(window_days)),
                    Input(label="Days projected", value=str(horizon)),
                    Input(label="Payments behind it", value=str(payments)),
                ),
                records=(SourceRecord(label="Cash flow for the window", href=href),),
                caveat=(
                    "Payments made, not bills raised — what has actually left the business. "
                    "Bills already raised with a due date ahead are on the cash-flow screen "
                    "as committed."
                ),
            ),
        )

    def _cash_requirement(
        self, sales, purchase, flow, stamp, window_from, window_to, horizon
    ) -> Forecast:
        """Projected outflow − projected inflow. Positive means cash is needed.

        Built from the two forecasts above rather than from a third measurement, so it
        cannot disagree with them — the same reason Part 9's homepage takes revenue and
        gross margin off one `MarginReport`. Inflow is *receipts banked*, not revenue
        invoiced: an invoice that has not been paid does not fund a purchase.
        """
        window_days = (window_to - window_from).days + 1
        projected_in = _project(flow.actual_in_minor, window_days, horizon)
        requirement = purchase.value_minor - projected_in

        # A documented cross-check, NEVER added to the projection — see the module docstring.
        committed = self.cash.committed(
            date_from=stamp, date_to=stamp + timedelta(days=horizon)
        )
        committed_net = committed.out_minor - committed.in_minor

        window = f"{window_from.isoformat()} to {window_to.isoformat()} ({window_days} days)"
        href = (
            f"/finance/cash-flow?date_from={stamp.isoformat()}"
            f"&date_to={(stamp + timedelta(days=horizon)).isoformat()}"
        )
        receipts = sum(row.receipts for row in flow.rows)
        return Forecast(
            key="cash_requirement",
            label=f"Cash requirement, next {horizon} days",
            value_minor=requirement,
            horizon_days=horizon,
            window_from=window_from,
            window_to=window_to,
            confidence=(
                f"{_confidence(receipts, window_days, unit='receipts')}. Excludes cash at "
                "bank, which ApexOS does not track, so this is the shortfall to cover from "
                "an opening balance you know and it does not"
            ),
            href=href,
            explained=Explained(
                what=(
                    f"Cash needed over the next {horizon} days — what is projected to leave "
                    "less what is projected to arrive"
                ),
                value=minor_to_text(requirement),
                formula=(
                    "projected supplier payments − projected receipts, each "
                    f"= trailing total ÷ {window_days} days × {horizon} days"
                ),
                window=window,
                inputs=(
                    Input(
                        label="Projected out (suppliers)",
                        value=minor_to_text(purchase.value_minor),
                    ),
                    Input(label="Projected in (receipts)", value=minor_to_text(projected_in)),
                    Input(
                        label="Committed on documents that already exist",
                        value=(
                            f"{minor_to_text(committed_net)} net "
                            f"({committed.bill_count} bills out, "
                            f"{committed.invoice_count} invoices in)"
                        ),
                        weight="cross-check, not added",
                    ),
                ),
                records=(SourceRecord(label="Cash flow ahead", href=href),),
                caveat=(
                    "The committed figure is a cross-check measured a different way — "
                    "documents with a due date in the window — and is deliberately NOT added "
                    "to the projection, because the trailing payment rate already reflects "
                    "paying bills like those. Two answers to the same question, not two "
                    "halves of one."
                ),
            ),
        )
