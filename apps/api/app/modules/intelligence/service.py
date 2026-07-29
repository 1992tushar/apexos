"""The Intelligence Layer projection (R13.3–R13.5, R13.9, R13.10).

**Read this before adding anything.** Like `command_center/service.py`, this file contains no
`select()`, no ORM model and no business arithmetic, and it must stay that way. Part 10 C1's
audit established that every score, radar and suggestion in ApexOS already has exactly one
owner; a query here would by definition be a second one. If a figure this page wants does not
exist, it goes in the OWNING service and is read here (R13.2, G16).

Who owns what on this page:

    dead stock radar          InventoryHealthService.dead_stock       (Part 5)
    margin leakage radar      MarginAnalysisService.leakage           (Part 8)
    churn risk radar          ChurnRiskService.at_risk                (Part 10 — the one new)
    working capital cockpit   CashFlowService.working_capital         (Part 8)
    category cockpit          MarginAnalysisService.by_dimension      (Part 8)
    business unit cockpit     MarginAnalysisService.by_dimension      (Part 8)
    the three forecasts       ForecastService                         (Part 10)
    the score families        named, not recomputed — see `_scores`

**The Morning Brief ranks; it does not judge (R13.9).** Every line is one alert or one
forecast that some other service already produced, ordered by the money impact that service
measured. It cannot introduce a threshold, a weighting or a verdict of its own — and the proof
that it has not is that every line names the service it came from.

**Only radars that fired appear.** `Alert` refuses to construct without records, so an empty
radar is *omitted* rather than rendered as a confident zero (R12.8). Three empty radars mean
the page says nothing needs attention, which is information.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.money import minor_to_text
from app.modules.customers.churn import AT_RISK_MULTIPLE, ChurnRiskService
from app.modules.customers.health import WINDOW_DAYS as CUSTOMER_WINDOW_DAYS
from app.modules.finance.cash import CashFlowService, default_window
from app.modules.finance.ledger import today as finance_today
from app.modules.finance.margin import MarginAnalysisService, bps_text
from app.modules.intelligence.forecast import ForecastService
from app.modules.intelligence.schemas import (
    Alert,
    AlertRecord,
    BriefItem,
    Cockpit,
    Figure,
    Intelligence,
    ScoreFamily,
)
from app.modules.inventory.health import DEAD_STOCK_DAYS, InventoryHealthService

#: Records a radar lists inline. `Alert.hidden_count` states what is not shown, so the cap is
#: never silent — the rest are reachable through the radar's own href.
RECORD_LIMIT = 5

#: Rows a cockpit shows. A cockpit is a summary; the full table is one click away on the
#: margin screen, and twenty tiles is not a summary.
TOP_ROWS = 5

#: Lines in the Morning Brief. R13.9 says *short* — a brief that lists everything is the page
#: it was meant to summarise.
BRIEF_LIMIT = 5


class IntelligenceService:
    """Assembles the Intelligence Layer. Writes nothing, computes nothing (G15, R13.9)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.cash = CashFlowService(db)
        self.margin = MarginAnalysisService(db)
        self.inventory_health = InventoryHealthService(db)
        self.churn = ChurnRiskService(db)
        self.forecasts = ForecastService(db)

    # --- the page ----------------------------------------------------------

    def load(self, *, as_of: date | None = None) -> Intelligence:
        """One page load. Each section makes its calls once."""
        stamp = as_of or finance_today()
        window_from, window_to = default_window(as_of=stamp)

        forecasts = self.forecasts.all(as_of=stamp)
        radars = self._radars(stamp, window_from, window_to)
        return Intelligence(
            as_of=stamp,
            window_from=window_from,
            window_to=window_to,
            brief=self._brief(radars, forecasts),
            forecasts=forecasts,
            radars=radars,
            cockpits=self._cockpits(stamp, window_from, window_to),
            scores=list(SCORE_FAMILIES),
        )

    # --- R13.4: the three radars -------------------------------------------

    def _radars(self, stamp: date, window_from: date, window_to: date) -> list[Alert]:
        """Dead stock, margin leakage, churn risk — only where each fired."""
        found: list[Alert | None] = [self._dead_stock(), self._churn(stamp)]
        found.extend(self._leakage(window_from, window_to))
        return [alert for alert in found if alert is not None]

    def _dead_stock(self) -> Alert | None:
        """Part 5's dead-stock list (R7.8), unchanged.

        `impact_minor` sums only the rows whose capital could be valued — a product with no
        cost basis contributes nothing rather than zero, and the threshold line says the
        measure is the last *sale*, because a cycle count must not make year-old stock look
        alive.
        """
        rows = self.inventory_health.dead_stock()
        if not rows:
            return None
        worst = rows[:RECORD_LIMIT]
        valued = [row.value_minor for row in rows if row.value_minor is not None]
        return Alert(
            key="dead_stock",
            label="Dead stock — capital not moving",
            trigger="stock is on hand and has not sold inside the window",
            threshold=(
                f"strictly more than {DEAD_STOCK_DAYS} days since the last SALE — a cycle "
                "count or a putaway does not count as movement"
            ),
            count=len(rows),
            impact_minor=sum(valued) if valued else None,
            records=[
                AlertRecord(
                    label=f"{row.sku_code} — {row.product_name}",
                    href=f"/products/{row.product_id}",
                    detail=(
                        "never sold"
                        if row.never_sold
                        else f"{row.days_since_sale} days since a sale"
                    )
                    + (
                        f", {minor_to_text(row.value_minor)} tied up"
                        if row.value_minor is not None
                        else ", no cost basis on record"
                    ),
                )
                for row in worst
            ],
            href="/inventory",
            explained=self.inventory_health.dead_stock_explained(worst[0]),
            source="InventoryHealthService.dead_stock (Part 5)",
        )

    def _churn(self, stamp: date) -> Alert | None:
        """Part 10's churn engine (R13.4) — the one radar with a new measurement behind it.

        No `impact_minor`: nothing here measures money. A quiet customer's revenue at risk
        would be a *second* forecast, made from a different window than the sales forecast on
        this same page, and two numbers on one screen disagreeing about the same customer is
        what R13.2 exists to prevent. The count and the multiple are what was measured.
        """
        rows = self.churn.at_risk(as_of=stamp)
        if not rows:
            return None
        return Alert(
            key="churn_risk",
            label="Customers going quiet",
            trigger="a customer has not ordered for several multiples of their own usual gap",
            threshold=(
                f"at least {AT_RISK_MULTIPLE}× their own mean gap between orders; customers "
                "with fewer than two orders have no gap to measure and are excluded rather "
                "than scored"
            ),
            count=len(rows),
            records=[
                AlertRecord(label=row.customer_name, href=row.href, detail=row.detail)
                for row in rows[:RECORD_LIMIT]
            ],
            href="/customers",
            explained=self.churn.explained(rows[0]),
            source="ChurnRiskService.at_risk (Part 10)",
        )

    def _leakage(self, window_from: date, window_to: date) -> list[Alert]:
        """Part 8's leakage indicators, one radar each — never one summed radar.

        The same treatment Part 9 gave them, for the reason C3 established: a below-cost loss
        and a discount give-away measure different quantities about overlapping lines, so a
        sum reads as a loss nobody made. `not_measured` becomes no radar at all — an
        indicator whose data does not exist has nothing to click (R11.8/R12.8), which is
        R11.7's still-open freight gap and is not this part's to resolve.
        """
        report = self.margin.leakage(date_from=window_from, date_to=window_to)
        window = f"date_from={window_from.isoformat()}&date_to={window_to.isoformat()}"
        return [
            Alert(
                key=f"leakage_{indicator.key}",
                label=indicator.label,
                trigger=f"an invoice line matched the {indicator.label.lower()} rule",
                threshold=indicator.rule,
                count=len(indicator.records),
                impact_minor=indicator.impact_minor,
                records=[
                    AlertRecord(
                        label=f"{record.doc_no} — {record.product_name}",
                        href=record.href,
                        detail=record.detail,
                    )
                    for record in indicator.records[:RECORD_LIMIT]
                ],
                href=f"/finance/leakage?{window}",
                explained=indicator.explained,
                source="MarginAnalysisService.leakage (Part 8)",
            )
            for indicator in report.fired
        ]

    # --- R13.5: the three cockpits -----------------------------------------

    def _cockpits(self, stamp: date, window_from: date, window_to: date) -> list[Cockpit]:
        capital = self.cash.working_capital(as_of=stamp)
        return [
            self._working_capital(capital),
            self._dimension("category", "Category performance", window_from, window_to),
            self._dimension(
                "business_unit", "Business unit performance", window_from, window_to
            ),
        ]

    def _working_capital(self, capital) -> Cockpit:
        """Part 8's snapshot, as four figures. `note` carries its own caveat verbatim.

        The caveat is not paraphrased: it says cash at bank is not included, and a working
        capital figure that silently omitted cash would be read as though it had not.
        """
        return Cockpit(
            key="working_capital",
            title="Working capital",
            note=capital.caveat,
            figures=[
                Figure(
                    key="wc_receivables",
                    label="Receivables",
                    kind="money",
                    value=capital.receivables_minor,
                    href="/finance/ageing?side=receivable",
                    hint="money owed to the business",
                ),
                Figure(
                    key="wc_inventory",
                    label="Inventory at cost",
                    kind="money",
                    value=capital.inventory_minor,
                    href="/inventory",
                    hint=(
                        "at weighted-average cost"
                        if capital.inventory_known
                        else f"{capital.products_without_cost} products have no recorded "
                        "cost and are excluded"
                    ),
                ),
                Figure(
                    key="wc_payables",
                    label="Payables",
                    kind="money",
                    value=capital.payables_minor,
                    href="/finance/ageing?side=payable",
                    hint="money the business owes",
                ),
                Figure(
                    key="wc_total",
                    label="Working capital",
                    kind="money",
                    value=capital.working_capital_minor,
                    href="/finance/cash-cycle",
                    hint="receivables + inventory − payables",
                ),
            ],
        )

    def _dimension(
        self, dimension: str, title: str, window_from: date, window_to: date
    ) -> Cockpit:
        """Category or business-unit performance, as the top rows by revenue.

        `MarginRow.href` is optional, so the report's own screen is the fallback — a figure
        with nowhere to drill through will not construct (R12.7/R13.10), and that validator
        is the reason this fallback exists rather than a `None` slipping through.
        """
        window = f"date_from={window_from.isoformat()}&date_to={window_to.isoformat()}"
        report_href = f"/finance/margin?dimension={dimension}&{window}"
        # ONE call for both the rows and the explanation. Fetching the report twice — once
        # for each — is the loop-invariant call Part 9 found inside `low_stock`, in miniature.
        report = self.margin.by_dimension(
            dimension, date_from=window_from, date_to=window_to
        )
        # `MarginRow` defines no ordering, so the key is mandatory rather than tidy: sorting
        # these objects bare raises `TypeError`.
        top = sorted(report.rows, key=lambda row: row.revenue_minor, reverse=True)[:TOP_ROWS]
        return Cockpit(
            key=dimension,
            title=title,
            explained=report.explained,
            note=(
                f"Top {len(top)} by revenue over the window, tax excluded. The full table is "
                "on the margin screen."
            )
            if top
            else "Nothing invoiced in this window.",
            figures=[
                Figure(
                    key=f"{dimension}_{index}",
                    label=row.label,
                    kind="money",
                    value=row.revenue_minor,
                    href=row.href or report_href,
                    hint=(
                        f"{bps_text(row.margin_bps)} margin, "
                        f"{minor_to_text(row.gp_minor)} gross profit"
                        if row.margin_bps is not None
                        else "margin unknown — no purchase price behind these lines"
                    )
                    + (
                        f" · {row.unknown_cost_lines} line(s) excluded for having no cost"
                        if row.unknown_cost_lines
                        else ""
                    ),
                )
                for index, row in enumerate(top)
            ],
        )

    # --- R13.9: the Morning Brief ------------------------------------------

    def _brief(self, radars: list[Alert], forecasts) -> list[BriefItem]:
        """What changed and what to do — a VIEW over the sections below it.

        The ranking rule is the whole of the logic here, and it is an *ordering*, not a
        judgement: radars that their own owner measured a money impact for come first,
        largest first, because that is the one comparable quantity on the page. Radars with
        no measured impact follow — unranked between themselves rather than given an invented
        score. The cash requirement comes last and only when it is positive, because a
        forecast surplus is not something to do today.

        Every line names its `source`. A line that could not is a line this method invented,
        which R13.9 forbids.
        """
        with_impact = sorted(
            (a for a in radars if a.impact_minor is not None),
            key=lambda a: a.impact_minor,
            reverse=True,
        )
        without = [a for a in radars if a.impact_minor is None]

        lines: list[BriefItem] = []
        for alert in [*with_impact, *without]:
            lines.append(
                BriefItem(
                    rank=len(lines) + 1,
                    headline=(
                        f"{alert.label} — {alert.count} record"
                        f"{'' if alert.count == 1 else 's'}"
                        + (
                            f", {minor_to_text(alert.impact_minor)}"
                            if alert.impact_minor is not None
                            else ""
                        )
                    ),
                    why=alert.trigger,
                    href=alert.href,
                    kind="alert",
                    impact_minor=alert.impact_minor,
                    source=alert.source,
                )
            )

        cash = next((f for f in forecasts if f.key == "cash_requirement"), None)
        if cash is not None and cash.value_minor > 0:
            lines.append(
                BriefItem(
                    rank=len(lines) + 1,
                    headline=(
                        f"{minor_to_text(cash.value_minor)} of cash needed over the next "
                        f"{cash.horizon_days} days"
                    ),
                    why=cash.confidence,
                    href=cash.href,
                    kind="forecast",
                    source="ForecastService (Part 10)",
                )
            )
        return lines[:BRIEF_LIMIT]


#: R13.3's three families. **Definitions and links, not computed numbers** — see
#: `ScoreFamily`'s docstring for why a headline here would be a per-row fan-out.
SCORE_FAMILIES: tuple[ScoreFamily, ...] = (
    ScoreFamily(
        key="customer_health",
        label="Customer health",
        what="How good a customer this is to keep, on four measured inputs",
        formula=(
            "frequency 25% + profitability 30% + payment 25% + recency 20%, renormalised "
            "over whichever inputs can be measured"
        ),
        window=f"the last {CUSTOMER_WINDOW_DAYS} days",
        href="/customers",
        owner="CustomerHealthService.score (Part 7)",
    ),
    ScoreFamily(
        key="vendor_reliability",
        label="Vendor reliability",
        what="Whether a supplier delivers what they promised, when they promised it",
        formula=(
            "hand-entered scorecard 60% + measured on-time rate 40%, renormalised over "
            "whichever exists; on time means received on or before the promised date"
        ),
        window="the last 12 receipts",
        href="/suppliers",
        owner="VendorIntelService.score (Part 4)",
    ),
    ScoreFamily(
        key="inventory_health",
        label="Inventory health",
        what="Which stock earns its shelf space and which is capital standing still",
        formula=(
            "ABC by cumulative share of consumption value (80/95/100 bands); dead stock is "
            f"on hand with no sale in {DEAD_STOCK_DAYS} days; movement rate is units sold "
            "per month"
        ),
        window=f"the last {DEAD_STOCK_DAYS} days for dead stock",
        href="/inventory",
        owner="InventoryHealthService (Part 5)",
    ),
)
