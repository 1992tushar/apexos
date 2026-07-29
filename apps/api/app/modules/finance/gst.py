"""The GST summary — output tax, input tax, net position, BY PERIOD (R11.9, R11.10).

**A report, and only a report (R11.10).** No return filing, no submission, no portal
reconciliation, no challan. The founder's accountant files; this answers "what will I owe for
July" without them having to ask.

**Why this exists when `ReportService._gst_summary` already did.** That builder returned a
single three-row total for the whole window, which is not "by period" — R11.9 asks for the
position *per period*, because GST is paid monthly and one lump covering a quarter cannot be
reconciled against anything. It also could not be reached from a screen with a window on it.
So the arithmetic lives here, by month, and `_gst_summary` now DELEGATES — the same correction
C1 applied to `_ar_aging`, which had its own arithmetic and had been wrong since Part 7.

Tax is stored per document (`subtotal_minor` / `tax_minor`), so nothing is recomputed from
rates: the tax on a document is what was invoiced or billed, which is the only figure a return
can be built from. Integer minor units throughout, and no division at all — a net position is
a subtraction (R11.12).
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.modules.finance.cash import default_window, month_starts
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import GstPeriodRow, GstSummary


class GstService:
    """Output and input GST per calendar month over an explicit window (R11.9, R11.13)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FinanceRepository(db)

    def summary(self, *, date_from: date, date_to: date) -> GstSummary:
        """One row per calendar month the window touches, oldest first.

        Monthly because that is the period GST is actually paid for. Every month in the
        window appears even when nothing was traded in it — a gap in the sequence would read
        as a missing month rather than a quiet one.
        """
        buckets: dict[date, list[int]] = {
            start: [0, 0, 0, 0] for start in month_starts(date_from, date_to)
        }

        for stamp, subtotal, tax in self.repo.invoice_tax_rows_between(date_from, date_to):
            slot = buckets.setdefault(stamp.replace(day=1), [0, 0, 0, 0])
            slot[0] += subtotal
            slot[1] += tax
        for stamp, subtotal, tax in self.repo.bill_tax_rows_between(date_from, date_to):
            slot = buckets.setdefault(stamp.replace(day=1), [0, 0, 0, 0])
            slot[2] += subtotal
            slot[3] += tax

        rows: list[GstPeriodRow] = []
        for start in sorted(buckets):
            out_taxable, out_tax, in_taxable, in_tax = buckets[start]
            year, month = start.year, start.month
            month_end = (
                date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            ) - timedelta(days=1)
            rows.append(
                GstPeriodRow(
                    label=start.strftime("%b %Y"),
                    period_from=max(start, date_from),
                    period_to=min(month_end, date_to),
                    output_taxable_minor=out_taxable,
                    output_tax_minor=out_tax,
                    input_taxable_minor=in_taxable,
                    input_tax_minor=in_tax,
                )
            )

        return GstSummary(date_from=date_from, date_to=date_to, rows=rows)

    def default_summary(self) -> GstSummary:
        """The window a GST screen opens on, so callers need not know the default."""
        start, end = default_window()
        return self.summary(date_from=start, date_to=end)

    @staticmethod
    def position_text(net_minor: int) -> str:
        """Which way a signed net position points, in words rather than by its sign."""
        if net_minor > 0:
            return "payable to the government"
        if net_minor < 0:
            return "input credit carried forward"
        return "nothing to pay or reclaim"
