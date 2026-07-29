"""Margin across four dimensions, and where money leaks (R11.5–R11.8, R11.11–R11.14).

**Cost comes from `MarginService.gp` and nowhere else (R11.6).** D-A removed FIFO and margin
never needed a valuation layer: gross profit is the selling price minus the purchase price,
times quantity. C2 already consumes the same `gp` for COGS (`cash.py:_cogs`), so a second cost
derivation here would put margin and DIO out of step with each other as well as with the rule.

**One thing `gp` cannot tell you, and this module must.** `gp` reads a missing purchase price
as zero — `latest_purchase_minor(...) or 0` — which makes an unpriced product report a **100%
margin**. That is the most misleading number this checkpoint could ship, so every line is first
checked against `purchase_prices_by_product()`: a line whose product has no recorded buy price
is counted as `unknown_cost_lines` and kept out of the margin arithmetic entirely, and the
screen says how many were excluded (G11). `gp` itself is left alone — R11.6 says to reuse it,
Part 7's health score depends on it, and the honest fix belongs where the count can be shown.

**Revenue is tax-exclusive.** GST is collected on the customer's behalf, not earned, so it has
no place in a margin ratio. `line_subtotal_minor`, not `line_total_minor`.

**Division appears only in the margin ratio (R11.12)**, it rounds in exactly one place —
`_bps()` — and it returns None rather than a flattering zero when it cannot be computed. No
float goes near a money figure: basis points are integers and every `*_minor` is untouched.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.core.money import minor_to_text, qty_text
from app.db.explain import Explained, Input, SourceRecord
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import (
    DISCOUNT_CREEP_BPS,
    MARGIN_DIMENSIONS,
    LeakageIndicator,
    LeakageRecord,
    LeakageReport,
    MarginReport,
    MarginRow,
)

DIMENSION_LABELS: dict[str, str] = dict(MARGIN_DIMENSIONS)

#: How many offending records an indicator lists before it stops. An indicator exists to be
#: acted on, and a list of 400 lines is not a list of actions — the count is always reported
#: in full even where the records are capped, so nothing is silently dropped.
_RECORD_LIMIT = 50

#: Freight. Reported as NOT MEASURED rather than as an indicator that found nothing, because
#: those are different claims and only one of them is true. See `LeakageReport.not_measured`.
_FREIGHT_GAP = {
    "key": "freight_not_recovered",
    "label": "Freight not recovered",
    "reason": (
        "Not measured: ApexOS records no freight, shipping, carriage or delivery charge "
        "anywhere on an order, invoice, bill or line, so there is nothing to compare a "
        "recovery against. Adding one is a product decision, not a reporting one — until "
        "then this indicator would have nothing to click, and R11.8 says an indicator like "
        "that must not exist rather than sit here showing zero."
    ),
}


def _bps(numerator_minor: int, denominator_minor: int) -> int | None:
    """`numerator / denominator` in integer basis points. THE one division in this module.

    Returns None when the denominator is zero — a margin on no revenue is not 0%, it is
    undefined, and G11 forbids the flattering default. Rounded once here through
    `Decimal.quantize`, the same step `round_minor` uses, but the result is a **ratio, not
    money**, so it deliberately does not go through that function. `ROUND_HALF_EVEN` is
    Decimal's default and is applied to the basis-point figure only; no float exists at any
    point and nothing computed here is ever put back into a money value.
    """
    if denominator_minor == 0:
        return None
    return int(
        (Decimal(numerator_minor) * Decimal(10000) / Decimal(denominator_minor)).quantize(
            Decimal("1")
        )
    )


def bps_text(bps: int | None) -> str:
    """Basis points as a percentage for a service message: 1850 -> "18.5%"."""
    if bps is None:
        return "unknown"
    whole, fraction = divmod(abs(bps), 100)
    sign = "-" if bps < 0 else ""
    return f"{sign}{whole}.{fraction:02d}".rstrip("0").rstrip(".") + "%"


class MarginAnalysisService:
    """Margin by dimension, and the leakage indicators that come out of the same lines."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FinanceRepository(db)

    # --- R11.5: one projection, four dimensions ---------------------------
    def by_dimension(
        self, dimension: str, *, date_from: date, date_to: date
    ) -> MarginReport:
        """Margin grouped by product, customer, category or business unit (R11.5).

        ONE implementation parameterised by `dimension`, not four near-copies: the only thing
        that differs between them is which key a line is filed under, so that is the only
        thing the code varies.
        """
        if dimension not in DIMENSION_LABELS:
            raise ValidationError(
                f"Unknown margin dimension '{dimension}'. "
                f"Choose one of: {', '.join(DIMENSION_LABELS)}"
            )

        from app.modules.pricing.service import MarginService

        margin = MarginService(self.db)
        buy_prices = self.repo.purchase_prices_by_product()
        categories = self.repo.category_names()
        business_units = self.repo.business_unit_names()

        # key -> [revenue, cost, gp, lines, unknown-cost lines, label, href]
        groups: dict[uuid.UUID | None, list] = {}
        totals = [0, 0, 0, 0, 0]  # revenue, cost, gp, lines, unknown

        for line, invoice, product_name, sku, category_id, customer_name in (
            self.repo.margin_lines_between(date_from, date_to)
        ):
            key, label, href = self._bucket(
                dimension,
                line=line,
                invoice=invoice,
                product_name=product_name,
                sku=sku,
                category_id=category_id,
                customer_name=customer_name,
                categories=categories,
                business_units=business_units,
            )
            slot = groups.setdefault(key, [0, 0, 0, 0, 0, label, href])
            slot[3] += 1
            totals[3] += 1

            gross = margin.gp_costed(line, buy_prices=buy_prices)
            if gross is None:
                # Cost genuinely unknown. Counted, reported, and kept OUT of the arithmetic
                # — `gp` would call it a 100% margin. The decision itself now lives in
                # `gp_costed` (R13.2), so the two other callers cannot diverge from it again.
                slot[4] += 1
                totals[4] += 1
                continue

            revenue = int(line.line_subtotal_minor)
            cost = revenue - gross
            slot[0] += revenue
            slot[1] += cost
            slot[2] += gross
            totals[0] += revenue
            totals[1] += cost
            totals[2] += gross

        rows = [
            MarginRow(
                key=key,
                label=slot[5],
                href=slot[6],
                revenue_minor=slot[0],
                cost_minor=slot[1],
                gp_minor=slot[2],
                margin_bps=_bps(slot[2], slot[0]),
                line_count=slot[3],
                unknown_cost_lines=slot[4],
            )
            for key, slot in groups.items()
        ]
        # Worst margin last is the wrong way round for a screen whose job is to show where the
        # money is: biggest gross profit first, then by name so ties are deterministic.
        rows.sort(key=lambda r: (-r.gp_minor, r.label))

        overall_bps = _bps(totals[2], totals[0])
        return MarginReport(
            dimension=dimension,
            dimension_label=DIMENSION_LABELS[dimension],
            date_from=date_from,
            date_to=date_to,
            rows=rows,
            revenue_minor=totals[0],
            cost_minor=totals[1],
            gp_minor=totals[2],
            margin_bps=overall_bps,
            line_count=totals[3],
            unknown_cost_lines=totals[4],
            explained=self._explain_margin(
                dimension=dimension,
                date_from=date_from,
                date_to=date_to,
                revenue=totals[0],
                cost=totals[1],
                gross=totals[2],
                bps=overall_bps,
                lines=totals[3],
                unknown=totals[4],
                rows=rows,
            ),
        )

    @staticmethod
    def _bucket(
        dimension: str,
        *,
        line,
        invoice,
        product_name: str,
        sku: str,
        category_id,
        customer_name: str | None,
        categories: dict,
        business_units: dict,
    ) -> tuple[uuid.UUID | None, str, str | None]:
        """Which group this line belongs to, for the chosen dimension. The ONLY difference
        between the four reports."""
        if dimension == "product":
            return line.product_id, f"{sku} · {product_name}", f"/products/{line.product_id}"
        if dimension == "customer":
            return (
                invoice.customer_id,
                customer_name or "—",
                f"/customers/{invoice.customer_id}",
            )
        if dimension == "category":
            # The product's OWN category, not rolled up to a parent. Categories nest
            # (`parent_category_id`), and a roll-up is a different report — saying which one
            # this is beats quietly picking one.
            return category_id, categories.get(category_id, "—"), None
        return (
            invoice.business_unit_id,
            business_units.get(invoice.business_unit_id, "—"),
            None,
        )

    @staticmethod
    def _explain_margin(
        *,
        dimension: str,
        date_from: date,
        date_to: date,
        revenue: int,
        cost: int,
        gross: int,
        bps: int | None,
        lines: int,
        unknown: int,
        rows: list[MarginRow],
    ) -> Explained:
        """G11 for the headline margin — including why it may be incomplete."""
        window = (
            f"{lines} invoice line(s) from {date_from.isoformat()} to {date_to.isoformat()}"
        )
        formula = (
            "gross profit ÷ revenue, where gross profit is MarginService.gp (selling − the "
            "purchase price, × quantity) and revenue is the tax-EXCLUSIVE line subtotal. GST "
            "is collected for the government, not earned, so it is not in the ratio."
        )
        if bps is None:
            return Explained.unknown(
                what=f"Gross margin by {DIMENSION_LABELS[dimension].lower()}",
                formula=formula,
                reason=(
                    "no line in this window has both revenue and a recorded purchase price, "
                    "so there is nothing to divide"
                ),
                window=window,
                inputs=(
                    Input(label="Priceable lines", value=str(lines - unknown)),
                    Input(
                        label="Lines with no purchase price",
                        value="",
                        missing_reason=f"{unknown} excluded — cost unknown",
                    ),
                ),
            )
        caveat = None
        if unknown:
            caveat = (
                f"{unknown} of {lines} lines are excluded because their product has no "
                f"recorded purchase price. Their cost is unknown, not zero — including them "
                f"would report those sales at a 100% margin."
            )
        return Explained(
            what=f"Gross margin by {DIMENSION_LABELS[dimension].lower()}",
            value=bps_text(bps),
            formula=formula,
            window=window,
            inputs=(
                Input(label="Revenue (ex-GST)", value=minor_to_text(revenue)),
                Input(label="Cost of those sales", value=minor_to_text(cost)),
                Input(label="Gross profit", value=minor_to_text(gross)),
                Input(label="Lines included", value=str(lines - unknown)),
            ),
            records=tuple(
                SourceRecord(label=f"{row.label} · {bps_text(row.margin_bps)}", href=row.href)
                for row in rows[:5]
            ),
            caveat=caveat,
        )

    # --- R11.7 / R11.8: leakage, with the offending records ---------------
    def leakage(self, *, date_from: date, date_to: date) -> LeakageReport:
        """The indicators that can be computed, each listing its offenders (R11.7, R11.8).

        Two of R11.7's three are computable and one is not; the missing one is reported as a
        stated gap rather than as an indicator showing zero. See `_FREIGHT_GAP`.
        """
        from app.modules.pricing.service import MarginService

        margin = MarginService(self.db)
        buy_prices = self.repo.purchase_prices_by_product()
        list_prices = self.repo.list_prices()

        below: list[LeakageRecord] = []
        creep: list[LeakageRecord] = []

        for line, invoice, product_name, _sku, _category_id, customer_name in (
            self.repo.margin_lines_between(date_from, date_to)
        ):
            # `gp_costed` is the ONE costable-line decision (R13.2). This block used to make
            # it inline — `buy is not None` — and then call `gp` twice; both are now one call
            # whose None answer means "we cannot know whether this line lost money".
            buy = buy_prices.get(line.product_id)
            gross = margin.gp_costed(line, buy_prices=buy_prices)
            if gross is not None and gross < 0:
                loss = -gross
                below.append(
                    LeakageRecord(
                        doc_no=invoice.invoice_no,
                        href=f"/invoices/{invoice.id}",
                        occurred_on=invoice.invoice_date,
                        product_name=product_name,
                        party_name=customer_name,
                        qty=line.qty,
                        unit_price_minor=int(line.unit_price_minor),
                        reference_minor=buy,
                        reference_label="Purchase price",
                        impact_minor=loss,
                        detail=(
                            f"Sold {qty_text(line.qty)} at "
                            f"{minor_to_text(line.unit_price_minor)} against a purchase price "
                            f"of {minor_to_text(buy)} — a loss of {minor_to_text(loss)}"
                        ),
                    )
                )

            listed = list_prices.get(line.product_id)
            if listed and int(line.unit_price_minor) < listed:
                discount_bps = _bps(listed - int(line.unit_price_minor), listed) or 0
                if discount_bps > DISCOUNT_CREEP_BPS:
                    given = int(
                        (
                            Decimal(listed - int(line.unit_price_minor)) * Decimal(line.qty)
                        ).quantize(Decimal("1"))
                    )
                    creep.append(
                        LeakageRecord(
                            doc_no=invoice.invoice_no,
                            href=f"/invoices/{invoice.id}",
                            occurred_on=invoice.invoice_date,
                            product_name=product_name,
                            party_name=customer_name,
                            qty=line.qty,
                            unit_price_minor=int(line.unit_price_minor),
                            reference_minor=listed,
                            reference_label="List price",
                            impact_minor=given,
                            detail=(
                                f"{bps_text(discount_bps)} below the list price of "
                                f"{minor_to_text(listed)} — {minor_to_text(given)} given away "
                                f"on {qty_text(line.qty)}"
                            ),
                        )
                    )

        window = f"{date_from.isoformat()} to {date_to.isoformat()}"
        return LeakageReport(
            date_from=date_from,
            date_to=date_to,
            indicators=[
                self._indicator(
                    key="sold_below_cost",
                    label="Sold below purchase price",
                    rule=(
                        "An invoice line whose gross profit is negative — the selling price "
                        "is below the product's current purchase price. Lines whose product "
                        "has no recorded purchase price are skipped, because their cost is "
                        "unknown rather than zero."
                    ),
                    records=below,
                    window=window,
                    what="Money lost by selling below what the stock cost",
                    unit="the loss on each line",
                ),
                self._indicator(
                    key="discount_creep",
                    label="Discount creep",
                    rule=(
                        f"An invoice line more than {bps_text(DISCOUNT_CREEP_BPS)} below the "
                        f"product's current list price — exactly "
                        f"{bps_text(DISCOUNT_CREEP_BPS)} is not an offender. There is no "
                        f"discount column in ApexOS, so the give-away is measured against the "
                        f"list price (the selling price with no customer and no segment). A "
                        f"product with no list price is skipped: its discount is unknown, not "
                        f"zero."
                    ),
                    records=creep,
                    window=window,
                    what="Money given away below list price",
                    unit="the difference against list, times quantity",
                ),
            ],
            not_measured=[_FREIGHT_GAP],
        )

    @staticmethod
    def _indicator(
        *,
        key: str,
        label: str,
        rule: str,
        records: list[LeakageRecord],
        window: str,
        what: str,
        unit: str,
    ) -> LeakageIndicator:
        records.sort(key=lambda r: (-r.impact_minor, r.doc_no, r.product_name))
        impact = sum(r.impact_minor for r in records)
        shown = records[:_RECORD_LIMIT]
        caveat = (
            f"{len(records) - _RECORD_LIMIT} further lines not listed; the total above "
            f"includes them."
            if len(records) > _RECORD_LIMIT
            else None
        )
        if not records:
            explained = Explained(
                what=what,
                value=minor_to_text(0),
                formula=rule,
                window=window,
                inputs=(Input(label="Offending lines", value="0"),),
                caveat="No offenders in this window — a clean result, not a missing check.",
            )
        else:
            explained = Explained(
                what=what,
                value=minor_to_text(impact),
                formula=f"{rule} The figure is the sum of {unit}.",
                window=window,
                inputs=(
                    Input(label="Offending lines", value=str(len(records))),
                    Input(label="Total impact", value=minor_to_text(impact)),
                    Input(label="Worst single line", value=minor_to_text(records[0].impact_minor)),
                ),
                records=tuple(
                    SourceRecord(
                        label=f"{r.doc_no} · {r.product_name} · {minor_to_text(r.impact_minor)}",
                        href=r.href,
                    )
                    for r in shown[:5]
                ),
                caveat=caveat,
            )
        return LeakageIndicator(
            key=key,
            label=label,
            rule=rule,
            records=shown,
            impact_minor=impact,
            explained=explained,
        )
