"""Cash flow, working capital and the cash conversion cycle (R11.1–R11.4, R11.11–R11.13).

The question here is *are we going to be short of cash*, and it is a different shape from
C1's. C1 asks "what is owed **now**" and takes `as_of`; a flow asks "what moved **between**
two dates", so **every method here takes an explicit `date_from` / `date_to`**. That is
R11.13, and it is deliberate rather than stylistic: the Command Center (Part 9) and the
intelligence layer (Part 10) must be able to ask for a quarter, or last month, without
recomputing any of this. If they later need a window this module cannot express, that is a
gap here.

**Nothing is recomputed that another part already owns (R11.11, G16):**

* receivables → `CustomerRepository.outstanding_by_customer()` (C1's bulk sibling of THE
  receivable), payables → `SupplierRepository.outstanding_by_supplier()`,
* what is *due* in a window → C1's `open_invoices` / `open_bills`,
* inventory value → Part 5's `ValuationService.stock_value()`,
* cost of goods → `MarginService.gp_costed`, never a second cost derivation (R11.6). Part 10
  moved this off `gp` so the costable-line decision lives in one place (R13.2). It changes no
  figure on today's data — see `_cogs` for why, measured rather than assumed — but it removes
  a dependence on `gp` and the stored subtotal happening to agree.

**Money stays integer minor units and division appears only in a ratio (R11.12).** The two
ratios here are day counts, and they round through exactly one place — `_days()` — which
says so and is the only division in the module. No float ever returns to a money figure:
the day counts are `int`, and every `*_minor` is untouched integer arithmetic.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.money import minor_to_text
from app.db.explain import Explained, Input, SourceRecord
from app.modules.customers.repository import CustomerRepository
from app.modules.finance.ledger import open_bills, open_invoices, today
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import (
    CashCycleReport,
    CashFlowPeriodRow,
    CashFlowReport,
    CommittedCash,
    WorkingCapitalSnapshot,
)
from app.modules.suppliers.repository import SupplierRepository

#: The window a cash screen opens on when the founder has not chosen one. A quarter: long
#: enough that one large receipt does not define the trend, short enough to be this year's
#: business.
DEFAULT_WINDOW_DAYS = 90

#: What R11.2 requires to be on screen. Held here, next to the code that computes each
#: figure, so `test_r11_2_the_screen_states_every_term_of_the_committed_figure` can assert
#: the founder reads the same sentences the arithmetic implements.
COMMITTED_TERMS: tuple[str, ...] = (
    "Committed in: the unpaid balance of every invoice whose due date falls inside this "
    "window — invoice total minus payments applied minus credit notes.",
    "Committed out: the unpaid balance of every bill whose due date falls inside this window.",
    "Both exclude cancelled and deleted documents, and both are the same open balances the "
    "ageing screen shows.",
    "NOT included in committed: confirmed sales orders not yet invoiced, and confirmed "
    "purchase orders not yet billed. These are real commitments but no due date exists for "
    "them yet — one is created when the order is invoiced or the purchase order is billed — "
    "so they are reported separately as pipeline rather than dated by guesswork.",
)

_NO_BANK_BALANCE = (
    "Cash at bank is NOT included: ApexOS records payments, not a bank balance, so this is "
    "working capital excluding cash. Receivables and payables are the same figures the "
    "ageing screens show; inventory is valued at weighted-average cost."
)


def default_window(*, as_of: date | None = None) -> tuple[date, date]:
    """The default `(date_from, date_to)` — `DEFAULT_WINDOW_DAYS` ending today."""
    end = as_of or today()
    return end - timedelta(days=DEFAULT_WINDOW_DAYS - 1), end


def _days(numerator_minor: int, per_day_minor: int, window_days: int) -> int | None:
    """`numerator / (denominator / window_days)`, rounded to whole days. THE one division.

    Returns None when the denominator is zero — no revenue in the window means DSO is
    genuinely unknown, and `0 days` would read as "we collect instantly" (G11 forbids
    exactly that kind of flattering default).

    Rounded once, here, through `Decimal.quantize` — the same rounding step
    `app.core.money.round_minor` uses, but this result is a **day count, not money**, so it
    deliberately does not go through that function. No float is involved at any point, and
    nothing derived here is ever put back into a money figure.
    """
    if per_day_minor <= 0 or window_days <= 0:
        return None
    return int(
        (Decimal(numerator_minor) * Decimal(window_days) / Decimal(per_day_minor)).quantize(
            Decimal("1")
        )
    )


def month_starts(date_from: date, date_to: date) -> list[date]:
    """The first of each calendar month touched by the window, in order.

    Public because C3's GST summary buckets by month for the same reason the cash-flow view
    does, and two implementations of "which months does this window touch" would eventually
    disagree about a window ending on the 1st.
    """
    out = [date_from.replace(day=1)]
    while True:
        year, month = out[-1].year, out[-1].month
        nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        if nxt > date_to:
            return out
        out.append(nxt)


class CashFlowService:
    """Cash in, cash out, what is committed, and how long cash is tied up."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FinanceRepository(db)
        self.customers = CustomerRepository(db)
        self.suppliers = SupplierRepository(db)

    # --- R11.1 / R11.2: cash flow, actual and committed --------------------
    def cash_flow(self, *, date_from: date, date_to: date) -> CashFlowReport:
        """Actual cash movement in the window, plus what is committed (R11.1).

        "Actual" is payments — the only real cash movement the system records. Nothing here
        is accrued: an invoice raised is not cash, and the screen says so.
        """
        payments = self.repo.payments_between(date_from, date_to)

        buckets: dict[date, list[int]] = {}
        for start in month_starts(date_from, date_to):
            buckets[start] = [0, 0, 0, 0]  # in, out, receipt count, payment count
        for direction, paid_on, amount in payments:
            key = paid_on.replace(day=1)
            if key not in buckets:  # a payment dated outside every bucket cannot happen
                buckets[key] = [0, 0, 0, 0]
            slot = buckets[key]
            if direction == "in":
                slot[0] += amount
                slot[2] += 1
            else:
                slot[1] += amount
                slot[3] += 1

        rows: list[CashFlowPeriodRow] = []
        for start in sorted(buckets):
            money_in, money_out, receipts, made = buckets[start]
            year, month = start.year, start.month
            month_end = (
                date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            ) - timedelta(days=1)
            rows.append(
                CashFlowPeriodRow(
                    label=start.strftime("%b %Y"),
                    date_from=max(start, date_from),
                    date_to=min(month_end, date_to),
                    in_minor=money_in,
                    out_minor=money_out,
                    net_minor=money_in - money_out,
                    receipts=receipts,
                    payments=made,
                )
            )

        return CashFlowReport(
            date_from=date_from,
            date_to=date_to,
            rows=rows,
            actual_in_minor=sum(r.in_minor for r in rows),
            actual_out_minor=sum(r.out_minor for r in rows),
            committed=self.committed(date_from=date_from, date_to=date_to),
        )

    def committed(self, *, date_from: date, date_to: date) -> CommittedCash:
        """What is contractually due in the window, exactly as `COMMITTED_TERMS` states.

        Exposed on its own as well as inside `cash_flow` because Part 9's cash tile wants
        this figure without the monthly breakdown (R11.13).
        """
        due_in = [
            doc
            for doc in open_invoices(self.db, as_of=date_to)
            if date_from <= doc.due_date <= date_to
        ]
        due_out = [
            doc
            for doc in open_bills(self.db, as_of=date_to)
            if date_from <= doc.due_date <= date_to
        ]
        order_count, order_total = self.repo.sales_pipeline()
        po_count, po_total = self.repo.purchase_pipeline()

        return CommittedCash(
            in_minor=sum(doc.open_minor for doc in due_in),
            out_minor=sum(doc.open_minor for doc in due_out),
            pipeline_in_minor=order_total,
            pipeline_out_minor=po_total,
            invoice_count=len(due_in),
            bill_count=len(due_out),
            pipeline_order_count=order_count,
            pipeline_po_count=po_count,
            terms=list(COMMITTED_TERMS),
        )

    # --- R11.3: working capital -------------------------------------------
    def working_capital(self, *, as_of: date | None = None) -> WorkingCapitalSnapshot:
        """Receivables + inventory − payables, as at a date (R11.3).

        A snapshot, so it takes `as_of` rather than a window — a balance has no window, and
        pretending otherwise would be the kind of parameter that looks rigorous and means
        nothing.
        """
        from app.modules.inventory.valuation import ValuationService

        stamp = as_of or today()
        receivables = sum(self.customers.outstanding_by_customer().values())
        payables = sum(self.suppliers.outstanding_by_supplier().values())

        value_rows = ValuationService(self.db).stock_value()
        # A product with stock but no purchase ever recorded has no cost basis, so its value
        # is unknown rather than zero (G11). It is counted and reported, not quietly skipped.
        unpriced = sum(
            1 for row in value_rows if row.value_minor is None and row.qty_on_hand > 0
        )
        inventory = sum(row.value_minor or 0 for row in value_rows)

        caveat = _NO_BANK_BALANCE
        if unpriced:
            caveat += (
                f" {unpriced} product(s) hold stock with no recorded purchase cost, so the "
                "inventory figure is a floor rather than a total."
            )

        return WorkingCapitalSnapshot(
            as_of=stamp,
            receivables_minor=receivables,
            inventory_minor=inventory,
            payables_minor=payables,
            inventory_known=unpriced == 0,
            products_without_cost=unpriced,
            caveat=caveat,
        )

    # --- R11.4: the cash conversion cycle ---------------------------------
    def cash_conversion_cycle(self, *, date_from: date, date_to: date) -> CashCycleReport:
        """DSO + DIO − DPO, with **each component computed and explained** (R11.4)."""
        window_days = (date_to - date_from).days + 1
        window = f"{date_from.isoformat()} to {date_to.isoformat()} ({window_days} days)"

        snapshot = self.working_capital(as_of=date_to)
        revenue_subtotal, revenue_total = self.repo.invoiced_between(date_from, date_to)
        purchases_subtotal, purchases_total = self.repo.billed_between(date_from, date_to)
        cogs, uncosted_lines = self._cogs(date_from, date_to)

        dso_days = _days(snapshot.receivables_minor, revenue_total, window_days)
        dio_days = _days(snapshot.inventory_minor, cogs, window_days)
        dpo_days = _days(snapshot.payables_minor, purchases_total, window_days)

        dso = self._component(
            what="DSO — how long a sale takes to become cash",
            days=dso_days,
            window_days=window_days,
            formula=(
                "receivables ÷ (invoiced in the window ÷ days in the window). Receivables is "
                "the one receivable definition, Σ invoice − Σ payments applied − Σ credit "
                "notes, as at the end of the window."
            ),
            window=window,
            inputs=(
                Input(label="Receivables", value=minor_to_text(snapshot.receivables_minor)),
                Input(label="Invoiced in window", value=minor_to_text(revenue_total)),
                Input(label="Days in window", value=str(window_days)),
            ),
            records=(SourceRecord(label="Receivables ageing", href="/finance/ageing"),),
            missing="nothing was invoiced in this window, so there is no sales rate to divide by",
        )
        dio = self._component(
            what="DIO — how long stock sits before it sells",
            days=dio_days,
            window_days=window_days,
            formula=(
                "inventory value ÷ (cost of goods sold in the window ÷ days in the window). "
                "Cost of goods is invoiced subtotal minus gross profit, where gross profit is "
                "MarginService.gp_costed — not an inventory valuation layer (R11.6)."
            ),
            window=window,
            inputs=(
                Input(label="Inventory at cost", value=minor_to_text(snapshot.inventory_minor)),
                Input(label="Cost of goods sold", value=minor_to_text(cogs)),
                Input(label="Days in window", value=str(window_days)),
                # Named rather than folded away: these lines are in the window's sales but
                # not in its cost, so a founder comparing DIO to the margin screen can see
                # why the two count different numbers of lines (G11, R13.10).
                *(
                    (
                        Input(
                            label="Invoice lines excluded (no purchase price)",
                            value=str(uncosted_lines),
                            missing_reason=None,
                        ),
                    )
                    if uncosted_lines
                    else ()
                ),
            ),
            records=(SourceRecord(label="Stock value at cost", href="/inventory"),),
            missing=(
                "no cost of goods could be computed for this window — either nothing was "
                "invoiced, or no purchase price is recorded for what was"
            ),
            caveat=(
                None
                if snapshot.inventory_known
                else f"{snapshot.products_without_cost} product(s) hold stock with no "
                "recorded purchase cost, so inventory is a floor and DIO is understated."
            ),
        )
        dpo = self._component(
            what="DPO — how long we take to pay a supplier",
            days=dpo_days,
            window_days=window_days,
            formula=(
                "payables ÷ (billed in the window ÷ days in the window). Payables is the one "
                "payable definition, Σ bill − Σ payments applied, as at the end of the window."
            ),
            window=window,
            inputs=(
                Input(label="Payables", value=minor_to_text(snapshot.payables_minor)),
                Input(label="Billed in window", value=minor_to_text(purchases_total)),
                Input(label="Days in window", value=str(window_days)),
            ),
            records=(SourceRecord(label="Payables ageing", href="/finance/ageing?side=payable"),),
            missing=(
                "nothing was billed in this window, so there is no purchasing rate to divide by"
            ),
        )

        parts = {"DSO": dso_days, "DIO": dio_days, "DPO": dpo_days}
        unknown = [name for name, value in parts.items() if value is None]
        ccc_inputs = tuple(
            Input(
                label=name,
                value="" if value is None else f"{value} days",
                missing_reason="not computable for this window" if value is None else None,
            )
            for name, value in parts.items()
        )
        ccc_formula = (
            "DSO + DIO − DPO. Days, not money — the three components are shown above and "
            "each is computed from its own numerator and rate."
        )
        if unknown:
            ccc_days = None
            ccc = Explained.unknown(
                what="Cash conversion cycle — days between paying for stock and being paid for it",
                formula=ccc_formula,
                reason=(
                    f"{', '.join(unknown)} could not be computed for this window, and a cycle "
                    "built from the remaining terms would be a smaller number that reads as "
                    "good news"
                ),
                window=window,
                inputs=ccc_inputs,
            )
        else:
            ccc_days = dso_days + dio_days - dpo_days
            ccc = Explained(
                what="Cash conversion cycle — days between paying for stock and being paid for it",
                value=f"{ccc_days} days",
                formula=ccc_formula,
                window=window,
                inputs=ccc_inputs,
                records=(
                    SourceRecord(label="Receivables ageing", href="/finance/ageing"),
                    SourceRecord(label="Payables ageing", href="/finance/ageing?side=payable"),
                    SourceRecord(label="Stock value at cost", href="/inventory"),
                ),
                # A cycle inherits its components' weaknesses: if DIO is a direction rather
                # than a measurement, so is the total it dominates.
                caveat=" ".join(
                    part
                    for part in (dio.caveat, self._thin_window_caveat(ccc_days, window_days))
                    if part
                )
                or None,
            )

        return CashCycleReport(
            date_from=date_from,
            date_to=date_to,
            window_days=window_days,
            dso_days=dso_days,
            dio_days=dio_days,
            dpo_days=dpo_days,
            ccc_days=ccc_days,
            dso=dso,
            dio=dio,
            dpo=dpo,
            ccc=ccc,
        )

    def _cogs(self, date_from: date, date_to: date) -> tuple[int, int]:
        """Cost of goods sold in the window — **through `MarginService.gp_costed`**.

        Returns `(cogs, uncosted_line_count)`.

        `cost = subtotal − gross profit`, so no second cost derivation exists anywhere: if
        margin ever changes its mind about what a thing cost, DIO changes with it. Subtotal,
        not total, because GST is collected on the customer's behalf rather than earned.

        **Uncosted lines are excluded from BOTH terms, which Part 10 changed (R13.2).** This
        used to call `gp`, which reads a missing purchase price as zero and so returns the
        line's whole selling value as profit.

        **Measured honestly: that change moves no number on today's data.** An uncosted
        line's `gp` comes out equal to its own subtotal, so `subtotal − gross` contributed
        exactly zero to cost — which is also what excluding it contributes. COGS over the
        seeded 90-day window is 14,691.95 either way. The change is worth making anyway, for
        two reasons that are not about today's figure:

        * it stops the right answer depending on a **coincidence**. `gp` is
          `(unit_price − buy) × qty` and the subtotal is a stored column; they agree only
          while nothing discounts a line after its unit price is set. The moment they
          diverge, an uncosted line starts contributing a fictitious cost.
        * the count comes back, so the DIO panel can **say** how much of the window it could
          not cost (R13.10). That is new information for the founder, and it is the part a
          reader of this figure actually needed.

        Do not describe this as having fixed DIO. It did not; DIO is 8,283 days on the seed
        before and after, and what makes that figure hard to read is the thin window
        `_thin_window_caveat` already marks.

        The buy price `gp` reads is the product's CURRENT one, not the price at the time of
        sale — that is the existing behaviour R11.6 tells this part to reuse, and the DIO
        panel carries it as a caveat rather than hiding it.
        """
        from app.modules.pricing.service import MarginService

        margin = MarginService(self.db)
        buy_prices = margin.purchase_price_map()
        subtotal = 0
        gross = 0
        uncosted = 0
        for line in self.repo.invoice_lines_between(date_from, date_to):
            line_gross = margin.gp_costed(line, buy_prices=buy_prices)
            if line_gross is None:
                uncosted += 1
                continue
            subtotal += int(line.line_subtotal_minor)
            gross += line_gross
        return max(0, subtotal - gross), uncosted

    @staticmethod
    def _thin_window_caveat(days: int, window_days: int) -> str | None:
        """The warning a day count longer than its own window has earned.

        A ratio of `balance ÷ (flow ÷ window)` is only as trustworthy as the flow. When the
        answer comes out **longer than the window itself**, the window contained less than
        one turn of the balance, and extrapolating it to a precise day count is arithmetic
        pretending to be measurement — on the seeded data DIO lands near 10,000 days, because
        a full warehouse divided by a quiet quarter genuinely is a very large number.

        So the figure is still shown — it is not wrong, and "stock is turning slower than a
        quarter can measure" is real information — but it says so. This is what G11's caveat
        is for, and it is the same honesty R9.13 applied to a measurement that flattered.
        """
        if days <= window_days:
            return None
        # Only quote a multiple once it is worth quoting. 111 days over a 90-day window is
        # 1.23×, and "about 1×" would read as though it barely mattered while also being the
        # wrong number — so a near miss says so in words instead.
        multiple = days // window_days
        scale = f"about {multiple}× it" if multiple >= 2 else "somewhat over it"
        return (
            f"This is longer than the {window_days}-day window it was measured over — "
            f"{scale} — so the window held less than one full turn and the figure is a "
            f"direction, not a precise day count. Read it as 'more than {window_days} days' "
            f"and widen the window for a firmer number."
        )

    @classmethod
    def _component(
        cls,
        *,
        what: str,
        days: int | None,
        window_days: int,
        formula: str,
        window: str,
        inputs: tuple[Input, ...],
        records: tuple[SourceRecord, ...],
        missing: str,
        caveat: str | None = None,
    ) -> Explained:
        """One CCC component as an `Explained` — the ONE shape (G11), never a bare number."""
        if days is None:
            return Explained.unknown(
                what=what, formula=formula, reason=missing, window=window, inputs=inputs
            )
        thin = cls._thin_window_caveat(days, window_days)
        return Explained(
            what=what,
            value=f"{days} days",
            formula=formula,
            window=window,
            inputs=inputs,
            records=records,
            caveat=" ".join(part for part in (caveat, thin) if part) or None,
        )
