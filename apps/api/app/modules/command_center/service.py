"""The Command Center projection (R12.1–R12.10).

**Read this before adding a tile.** Every number below is fetched from the part that
owns it, through the period-parameterised entry points R11.13 exists to provide. There
is no `select()` in this file and there must never be one: a query here is by definition
a second definition of something another part already defines, which is the exact defect
R10.x/R11.x/R13.2 exist to prevent. If a figure you want is missing, add it to the
owning service and read it here.

Who owns what:

    today's revenue, today's gross margin   MarginAnalysisService.by_dimension  (Part 8)
    collections today, cash flow            CashFlowService.cash_flow           (Part 8)
    receivables, payables, ageing           AgeingService.ar_ageing/.ap_ageing  (Part 8)
    inventory value, working capital        CashFlowService.working_capital     (Part 8)
    customer alerts (who to chase)          AgeingService.collections           (Part 8)
    margin alerts                           MarginAnalysisService.leakage       (Part 8)
    low-stock alerts                        InventoryHealthService.low_stock    (Part 5)
    vendor alerts, deliveries due           ProcurementCalendarService.arrivals (Part 4)
    sales orders pending                    SalesRepository.pending_count       (Part 7)
    purchase orders pending                 ProcurementRepository.pending_count (Part 3)
    recent activity                         ActivityService.recent              (Part 1)

Two consequences of that list worth stating, because both were nearly got wrong:

**The inventory value comes from the working-capital snapshot, not from
`ValuationService.stock_value()`.** Both would be right, but the snapshot already
contains inventory-at-cost as one of its three terms, so reading it there means the
homepage's inventory tile and its working-capital figure cannot disagree — and it costs
one fewer valuation pass over every product.

**Arrivals, not the whole calendar.** `ProcurementCalendarService.calendar()` also runs
the recommendation engine, and this page does not show recommendations. `.arrivals()` is
the half that answers "what is due to arrive", which is R12.3's "deliveries due" and, in
its overdue column, R12.3's vendor alert.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.modules.activity.service import ActivityService
from app.modules.command_center.schemas import (
    ActivityEntry,
    Alert,
    AlertRecord,
    CommandCenter,
    Figure,
    QuickAction,
)
from app.modules.finance.ageing import AgeingService
from app.modules.finance.cash import CashFlowService, default_window
from app.modules.finance.ledger import today as finance_today
from app.modules.finance.margin import MarginAnalysisService, bps_text
from app.modules.inventory.health import InventoryHealthService
from app.modules.procurement.recommend import ProcurementCalendarService
from app.modules.procurement.repository import ProcurementRepository
from app.modules.sales.repository import SalesRepository

#: How many records an alert lists inline. The rest are reachable through the alert's
#: own `href`, and `Alert.hidden_count` states how many are not shown — a silently
#: truncated list reads as "that is all there is".
RECORD_LIMIT = 5

#: How many `activity_log` rows the feed shows (R12.5).
ACTIVITY_LIMIT = 10

#: Below this many priced lines, "today's revenue" and "today's gross margin" are a
#: sample rather than a rate, and the page says so. Part 8's `_thin_window_caveat` marks
#: a day count longer than its own window for the same reason: a figure that is correct
#: and reads as precise is worse than one that admits what it is built from.
THIN_SAMPLE_LINES = 3

#: The forward window for committed cash, matching the length of `default_window`'s
#: trailing one so the two position figures are the same size and comparable.
AHEAD_DAYS = 90

#: Arrival buckets that mean "an order should be here by now or is about to be".
#: `unpromised` is deliberately absent — R5.7's rule is that an order nobody promised a
#: date for is not due, and counting it here would put the same lie on the homepage.
DUE_BUCKETS = ("overdue", "today", "this_week")


class CommandCenterService:
    """Assembles the homepage. Writes nothing, ever (G15, R12.10)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.ageing = AgeingService(db)
        self.cash = CashFlowService(db)
        self.margin = MarginAnalysisService(db)
        self.inventory_health = InventoryHealthService(db)
        self.arrivals = ProcurementCalendarService(db)
        self.sales = SalesRepository(db)
        self.procurement = ProcurementRepository(db)
        self.activity = ActivityService(db)

    # --- the page ----------------------------------------------------------

    def load(self, *, as_of: date | None = None) -> CommandCenter:
        """One page load. Each helper makes its calls once and passes them on."""
        stamp = as_of or finance_today()
        window_from, window_to = default_window(as_of=stamp)

        # Fetched once each, then read by more than one section below. The alternative —
        # each helper fetching what it needs — doubles the query count for no gain.
        ar = self.ageing.ar_ageing(as_of=stamp)
        ap = self.ageing.ap_ageing(as_of=stamp)
        capital = self.cash.working_capital(as_of=stamp)
        arrivals = self.arrivals.arrivals()

        today_margin = self.margin.by_dimension("product", date_from=stamp, date_to=stamp)
        today_cash = self.cash.cash_flow(date_from=stamp, date_to=stamp)
        window_cash = self.cash.cash_flow(date_from=window_from, date_to=window_to)

        # Committed cash is asked for over the window AHEAD, not the window behind.
        # `cash_flow`'s own `.committed` covers the same trailing 90 days as its actuals,
        # which is the right pairing on a cash-flow *report* and the wrong figure on a
        # homepage: what a founder needs to see is money that documents already existing
        # will move next, not money whose due date has passed. Driving the real page is
        # what caught this — the tile was labelled "next 90 days" over trailing data.
        ahead_from, ahead_to = stamp, stamp + timedelta(days=AHEAD_DAYS)
        committed_ahead = self.cash.committed(date_from=ahead_from, date_to=ahead_to)

        happened, caveat = self._what_happened(today_margin, today_cash, stamp)
        return CommandCenter(
            as_of=stamp,
            window_from=window_from,
            window_to=window_to,
            happened=happened,
            happened_caveat=caveat,
            position=self._position(window_cash, committed_ahead, ahead_to, capital),
            position_caveat=capital.caveat,
            attention=self._attention(ar, ap, capital, arrivals),
            alerts=self._alerts(stamp, window_from, window_to, arrivals),
            actions=list(QUICK_ACTIONS),
            activity=[
                ActivityEntry(
                    verb=row.verb,
                    entity_type=row.entity_type,
                    summary=row.summary,
                    occurred_at=row.occurred_at,
                )
                for row in self.activity.recent(ACTIVITY_LIMIT)
            ],
        )

    # --- 1: what happened (R12.2) ------------------------------------------

    def _what_happened(self, margin, cash, stamp: date) -> tuple[list[Figure], str | None]:
        """Today's revenue, today's gross margin, collections today.

        All three are *today* — the point of the section is that a founder opening the
        app at 6pm learns what the day did, not what the quarter did. Both money figures
        come from one `MarginReport` over a one-day window, so revenue and gross margin
        cannot disagree about which lines they counted.

        The margin is `Explained` and may be **unknown**: `MarginService.gp` reads a
        missing purchase price as zero and would report a 100% margin, so the projection
        excludes and counts those lines. Where every line today is one of those, there is
        no margin to report and the tile says so rather than showing a flattering number.
        """
        day = stamp.isoformat()
        margin_href = f"/finance/margin?date_from={day}&date_to={day}"
        cash_href = f"/finance/cash-flow?date_from={day}&date_to={day}"

        figures = [
            Figure(
                key="revenue_today",
                label="Revenue today",
                kind="money",
                value=margin.revenue_minor,
                href=margin_href,
                hint=(
                    f"{margin.line_count} invoice line"
                    f"{'' if margin.line_count == 1 else 's'}, tax excluded"
                ),
            ),
            Figure(
                key="gross_margin_today",
                label="Gross margin today",
                kind="money" if margin.margin_bps is not None else "text",
                value=(
                    margin.gp_minor
                    if margin.margin_bps is not None
                    else margin.explained.display
                ),
                href=margin_href,
                hint=(
                    f"{bps_text(margin.margin_bps)} of revenue"
                    if margin.margin_bps is not None
                    else "no line today has a purchase price behind it"
                ),
                explained=margin.explained,
            ),
            Figure(
                key="collections_today",
                label="Collections today",
                kind="money",
                value=cash.actual_in_minor,
                href=cash_href,
                hint=(
                    f"{sum(row.receipts for row in cash.rows)} receipt"
                    f"{'' if sum(row.receipts for row in cash.rows) == 1 else 's'} banked"
                ),
            ),
        ]
        return figures, self._thin_sample_caveat(margin)

    @staticmethod
    def _thin_sample_caveat(margin) -> str | None:
        """Say when today's figures are too few lines to read as a rate.

        Two separate admissions, because they are different problems: too few lines at
        all, and lines that were dropped for having no cost. Either makes the margin
        percentage a fact about a handful of documents rather than about the business.
        """
        notes = []
        if 0 < margin.line_count < THIN_SAMPLE_LINES:
            notes.append(
                f"today is {margin.line_count} priced line"
                f"{'' if margin.line_count == 1 else 's'} — read the margin as a sample, "
                "not a rate"
            )
        if margin.unknown_cost_lines:
            one = margin.unknown_cost_lines == 1
            notes.append(
                f"{margin.unknown_cost_lines} line{'' if one else 's'} today "
                f"{'has' if one else 'have'} no purchase price and "
                f"{'is' if one else 'are'} excluded from both revenue and margin"
            )
        return "; ".join(notes) or None

    # --- position (R12.4) --------------------------------------------------

    def _position(self, cash, committed, ahead_to: date, capital) -> list[Figure]:
        """Where the business stands: cash behind, cash committed ahead, working capital.

        The two cash figures point in opposite directions on purpose. `cash` is what
        actually moved over the trailing window; `committed` is what documents that
        already exist will move over the window ahead. Neither is a forecast — the
        pipeline (confirmed orders not yet invoiced or billed) is excluded from committed
        for the reason R11.2 gives, that no due date exists for it, and repeating that
        judgement here would be making it a second time.
        """
        behind = f"date_from={cash.date_from.isoformat()}&date_to={cash.date_to.isoformat()}"
        ahead = f"date_from={cash.date_to.isoformat()}&date_to={ahead_to.isoformat()}"
        return [
            Figure(
                key="cash_net",
                label=f"Net cash, last {AHEAD_DAYS} days",
                kind="money",
                value=cash.actual_net_minor,
                href=f"/finance/cash-flow?{behind}",
                hint=(
                    f"in {cash.actual_in_minor // 100:,} · out "
                    f"{cash.actual_out_minor // 100:,} (rupees)"
                ),
            ),
            Figure(
                key="cash_committed",
                label=f"Committed, next {AHEAD_DAYS} days",
                kind="money",
                value=committed.net_minor,
                href=f"/finance/cash-flow?{ahead}",
                hint=(
                    f"{committed.invoice_count} invoices in, {committed.bill_count} bills "
                    "out — documents that exist with a due date ahead, not a forecast"
                ),
            ),
            Figure(
                key="working_capital",
                label="Working capital",
                kind="money",
                value=capital.working_capital_minor,
                href="/finance/cash-cycle",
                hint="receivables + inventory − payables, excluding cash at bank",
            ),
        ]

    # --- 2: what needs attention (R12.3) -----------------------------------

    def _attention(self, ar, ap, capital, arrivals) -> list[Figure]:
        """The six standing figures. The four alert families follow them.

        Each carries the one number that turns it into a decision: what is overdue inside
        the receivable, how many products have no cost behind the inventory value. A tile
        that could only ever show a total was left off — R12.9 is explicit that a figure
        which does not change a decision is deleted rather than kept for symmetry.
        """
        due_now = [a for a in arrivals if a.bucket in DUE_BUCKETS]
        overdue_arrivals = sum(1 for a in arrivals if a.bucket == "overdue")
        return [
            Figure(
                key="receivables",
                label="Outstanding receivables",
                kind="money",
                value=ar.total_minor,
                href="/finance/ageing?side=receivable",
                hint=f"{ar.overdue_minor // 100:,} rupees of it overdue",
            ),
            Figure(
                key="payables",
                label="Outstanding payables",
                kind="money",
                value=ap.total_minor,
                href="/finance/ageing?side=payable",
                hint=f"{ap.overdue_minor // 100:,} rupees of it overdue",
            ),
            Figure(
                key="inventory_value",
                label="Inventory value",
                kind="money",
                value=capital.inventory_minor,
                href="/inventory",
                hint=(
                    "at weighted-average cost"
                    if capital.inventory_known
                    else f"{capital.products_without_cost} products have no recorded cost "
                    "and are excluded"
                ),
            ),
            Figure(
                key="purchase_orders_pending",
                label="Purchase orders pending",
                kind="count",
                value=self.procurement.pending_count(),
                href="/purchase-orders",
                hint="draft or confirmed, not yet fully received",
            ),
            Figure(
                key="sales_orders_pending",
                label="Sales orders pending",
                kind="count",
                value=self.sales.pending_count(),
                href="/sales",
                hint="confirmed, not yet fulfilled",
            ),
            Figure(
                key="deliveries_due",
                label="Deliveries due",
                kind="count",
                value=len(due_now),
                href="/procurement",
                hint=(
                    f"{overdue_arrivals} already past the promised date"
                    if overdue_arrivals
                    else "promised within 7 days; orders with no promised date excluded"
                ),
            ),
        ]

    # --- the four alert families (R12.3, R12.8) ----------------------------

    def _alerts(self, stamp, window_from, window_to, arrivals) -> list[Alert]:
        """Customer, vendor, low-stock and margin alerts — only where they fired.

        Every family is a filter over a list some other part already built, and every one
        of them can be empty. **An empty family is omitted, not shown as a zero** (R12.8):
        `Alert` refuses to be constructed without records, so this is enforced by the
        schema rather than remembered here.
        """
        found = [
            self._customer_alert(stamp),
            self._vendor_alert(arrivals),
            self._low_stock_alert(),
        ]
        found.extend(self._margin_alerts(window_from, window_to))
        return [alert for alert in found if alert is not None]

    def _customer_alert(self, stamp: date) -> Alert | None:
        """Customers with money past its due date — Part 8's collections list (R10.7).

        The threshold is the one R10.6 fixes and the seed tests on its edge: **due today
        is not overdue.** Nothing here re-derives it; the entries arrive already filtered
        to parties with something genuinely overdue.
        """
        entries = self.ageing.collections(as_of=stamp)
        if not entries:
            return None
        worst = entries[: RECORD_LIMIT]
        return Alert(
            key="customers_overdue",
            label="Customers to chase",
            trigger="an invoice is past its due date and still open",
            threshold=(
                "more than 0 days past due — an invoice due today is not overdue (R10.6)"
            ),
            count=len(entries),
            impact_minor=sum(e.overdue_minor for e in entries),
            records=[
                AlertRecord(
                    label=f"{e.customer_name} — {e.oldest_doc_no}",
                    href=e.oldest_doc_href,
                    detail=e.reason,
                )
                for e in worst
            ],
            href="/finance/collections",
            explained=entries[0].explained,
            source="AgeingService.collections (Part 8)",
        )

    def _vendor_alert(self, arrivals) -> Alert | None:
        """Suppliers past the date they promised — Part 4's arrivals side of R5.7.

        This is the vendor alert that has something to click. A vendor *score* does not:
        it is one number per supplier and would need a pass over every one of them to
        find the bad ones, which is the fan-out R12.12 measures. A late open order is
        both cheaper to find and more actionable — the PO is the thing to ring about.
        """
        late = [a for a in arrivals if a.bucket == "overdue"]
        if not late:
            return None
        return Alert(
            key="arrivals_overdue",
            label="Deliveries past their promised date",
            trigger="an open purchase order's promised date has passed",
            threshold=(
                "expected date before today; orders with no promised date are excluded "
                "rather than treated as due (R5.7)"
            ),
            count=len(late),
            records=[
                AlertRecord(
                    label=f"{a.po_no} — {a.supplier_name or 'unknown supplier'}",
                    href=f"/purchase-orders/{a.purchase_order_id}",
                    detail=(
                        f"{abs(a.days_away or 0)} days late, {a.open_qty} still to arrive"
                    ),
                )
                for a in late[:RECORD_LIMIT]
            ],
            href="/procurement",
            source="ProcurementCalendarService.arrivals (Part 4)",
        )

    def _low_stock_alert(self) -> Alert | None:
        """Products below their reorder level — Part 5's R7.10 list.

        On **available**, not on-hand: stock that is reserved against a confirmed order
        is not stock you can sell, and Part 5 settled that. The explanation attached is
        the worst row's own, from `low_stock_explained`, so the arithmetic on screen is
        the arithmetic that decided the row.
        """
        rows = self.inventory_health.low_stock()
        if not rows:
            return None
        worst = rows[:RECORD_LIMIT]
        return Alert(
            key="low_stock",
            label="Products below reorder level",
            trigger="available stock has fallen to or below the product's reorder level",
            threshold="available ≤ reorder level, where available excludes reserved stock",
            count=len(rows),
            records=[
                AlertRecord(
                    label=f"{row.sku_code} — {row.product_name}",
                    href=f"/products/{row.product_id}",
                    detail=(
                        f"{row.available} available against a level of {row.reorder_level}"
                        f" at {row.warehouse_name}"
                    ),
                )
                for row in worst
            ],
            href="/inventory",
            explained=self.inventory_health.low_stock_explained(worst[0]),
            source="InventoryHealthService.low_stock (Part 5)",
        )

    def _margin_alerts(self, window_from: date, window_to: date) -> list[Alert]:
        """Part 8's leakage indicators, one alert each — never one summed alert.

        C3 removed a tile that added a below-cost loss to a discount give-away, because
        the two measure different quantities about overlapping lines and the sum read as
        a loss nobody made. So each indicator that fired becomes its own alert with its
        own rule printed, and `LeakageReport.not_measured` is not turned into an alert at
        all: an indicator whose data does not exist has nothing to click (R11.8/R12.8).
        """
        report = self.margin.leakage(date_from=window_from, date_to=window_to)
        window = f"date_from={window_from.isoformat()}&date_to={window_to.isoformat()}"
        alerts = []
        for indicator in report.fired:
            alerts.append(
                Alert(
                    key=f"margin_{indicator.key}",
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
            )
        return alerts


#: R12.6's four, and why each earned its place. A fifth has to displace one of these:
#: the point of the section is that the four things done many times a day are one click
#: from the homepage, and a list of nine is a menu, which the sidebar already is.
QUICK_ACTIONS: tuple[QuickAction, ...] = (
    QuickAction(
        label="New sales order",
        href="/sales/new",
        why="the most frequent act in the business — keyboard-first entry (R8.x)",
    ),
    QuickAction(
        label="New purchase order",
        href="/purchase-orders/new",
        why="the buying side of the same day",
    ),
    QuickAction(
        label="Record a payment",
        href="/finance/collections",
        why="opens the chase list, where every open invoice takes a receipt inline",
    ),
    QuickAction(
        label="Receive stock",
        href="/purchase-orders",
        why="receipt is recorded against the purchase order it arrived for",
    ),
)
