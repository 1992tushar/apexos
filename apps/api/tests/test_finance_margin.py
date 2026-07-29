"""Part 8 C3 — margin across four dimensions, leakage, GST (R11.5–R11.10, R11.12, R11.14).

The two that carry the most weight:

* `test_r11_6_a_line_with_no_purchase_price_is_unknown_not_a_100_percent_margin` — this is the
  wrong number this checkpoint was most likely to ship. `MarginService.gp` reads a missing
  purchase price as zero, so an unpriced line looks like pure profit; the projection has to
  exclude and count it instead.
* `test_r11_8_each_indicator_fires_on_its_offender_and_stays_silent_otherwise` — R11.8's actual
  acceptance criterion, and the reason `app/seed/finance.py` seeds one deliberate offender per
  indicator plus one line that must NOT trip the other.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.core.errors import ValidationError
from app.modules.activity.models import ActivityLog
from app.modules.finance.gst import GstService
from app.modules.finance.margin import (
    DIMENSION_LABELS,
    MarginAnalysisService,
    _bps,
    bps_text,
)
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import DISCOUNT_CREEP_BPS, MARGIN_DIMENSIONS


def _window() -> tuple[date, date]:
    """Wide enough to hold every seeded document, whenever the suite runs."""
    return date.today() - timedelta(days=365), date.today() + timedelta(days=60)


# --- R11.12: the one ratio ---------------------------------------------------


def test_r11_12_the_margin_ratio_rounds_once_and_is_unknown_on_no_revenue():
    assert _bps(0, 100) == 0
    assert _bps(50, 100) == 5000
    assert _bps(100, 100) == 10000
    assert _bps(-25, 100) == -2500, "a negative margin must survive the ratio"
    assert _bps(1, 3) == 3333, "rounds once, to the nearest basis point"
    assert _bps(10, 0) is None, "a margin on no revenue is undefined, not 0%"
    assert isinstance(_bps(1, 3), int)


def test_r11_12_basis_points_render_without_a_float():
    assert bps_text(1850) == "18.5%"
    assert bps_text(10000) == "100%"
    assert bps_text(0) == "0%"
    assert bps_text(-2500) == "-25%"
    assert bps_text(None) == "unknown"


# --- R11.5: four dimensions, one projection ---------------------------------


def test_r11_5_margin_is_reported_across_all_four_dimensions(db):
    """R11.5 names product, customer, category and business unit."""
    assert [key for key, _label in MARGIN_DIMENSIONS] == [
        "product",
        "customer",
        "category",
        "business_unit",
    ]
    start, end = _window()
    svc = MarginAnalysisService(db)
    for dimension in DIMENSION_LABELS:
        report = svc.by_dimension(dimension, date_from=start, date_to=end)
        assert report.dimension == dimension
        assert report.rows, f"{dimension} produced no rows"
        assert report.margin_bps is not None, dimension


def test_r11_5_every_dimension_sums_to_the_same_revenue_and_profit(db):
    """The dimensions are four groupings of ONE set of lines, so their totals must agree.

    This is what proves `by_dimension` is one projection parameterised by key rather than four
    queries that can drift — and it would catch a group-by pointing at the wrong column.
    """
    start, end = _window()
    svc = MarginAnalysisService(db)
    reports = {d: svc.by_dimension(d, date_from=start, date_to=end) for d in DIMENSION_LABELS}

    revenues = {d: r.revenue_minor for d, r in reports.items()}
    profits = {d: r.gp_minor for d, r in reports.items()}
    lines = {d: r.line_count for d, r in reports.items()}
    assert len(set(revenues.values())) == 1, f"dimensions disagree on revenue: {revenues}"
    assert len(set(profits.values())) == 1, f"dimensions disagree on gross profit: {profits}"
    assert len(set(lines.values())) == 1, f"dimensions disagree on line count: {lines}"

    for dimension, report in reports.items():
        assert sum(r.revenue_minor for r in report.rows) == report.revenue_minor, dimension
        assert sum(r.gp_minor for r in report.rows) == report.gp_minor, dimension
        assert sum(r.line_count for r in report.rows) == report.line_count, dimension


def test_r11_5_each_dimension_has_exactly_one_row_per_distinct_member(db):
    """The assertion that makes all four groupings honest.

    Totals reconciling across dimensions is NOT enough: grouping the category report by
    product id keeps every total identical and merely produces duplicate category rows. So the
    row count is checked against the distinct count of the attribute itself, computed here from
    the lines, and labels are asserted unique. Swapping any dimension's key for another's fails
    this — verified by mutation.
    """
    start, end = _window()
    repo = FinanceRepository(db)
    lines = repo.margin_lines_between(start, end)
    assert lines

    expected = {
        "product": {line.product_id for line, *_rest in lines},
        "customer": {inv.customer_id for _line, inv, *_rest in lines},
        "category": {row[4] for row in lines},
        "business_unit": {inv.business_unit_id for _line, inv, *_rest in lines},
    }
    # The data has to be able to tell the dimensions apart, or this proves nothing.
    assert len(expected["category"]) != len(expected["product"]), (
        "as many categories as products — the category grouping cannot be distinguished"
    )

    svc = MarginAnalysisService(db)
    for dimension, members in expected.items():
        report = svc.by_dimension(dimension, date_from=start, date_to=end)
        assert len(report.rows) == len(members), (
            f"{dimension} produced {len(report.rows)} rows for {len(members)} distinct members"
        )
        assert {row.key for row in report.rows} == members, f"{dimension} grouped by the wrong key"
        labels = [row.label for row in report.rows]
        assert len(set(labels)) == len(labels), f"{dimension} has duplicate labels: {labels}"


def test_r11_5_an_unknown_dimension_is_refused(db):
    with pytest.raises(ValidationError, match="Unknown margin dimension"):
        MarginAnalysisService(db).by_dimension(
            "supplier", date_from=date.today(), date_to=date.today()
        )


def test_r11_5_the_business_unit_dimension_works_on_one_business_unit(db):
    """The seed has exactly one business unit, so this dimension has one row.

    Recorded rather than papered over: the grouping is exercised and the total reconciles, but
    the dimension cannot demonstrate a split until a second business unit exists.
    """
    start, end = _window()
    report = MarginAnalysisService(db).by_dimension(
        "business_unit", date_from=start, date_to=end
    )
    assert len(report.rows) == 1
    assert report.rows[0].revenue_minor == report.revenue_minor
    assert report.rows[0].label not in ("", "—"), "the business unit has no readable name"


# --- R11.6: cost is MarginService.gp, and unknown is unknown ----------------


def test_r11_6_revenue_is_tax_exclusive_and_cost_comes_from_marginservice(db):
    """Recomputed in the test through `gp`, line by line."""
    from app.modules.pricing.service import MarginService

    start, end = _window()
    repo = FinanceRepository(db)
    margin = MarginService(db)
    buy_prices = repo.purchase_prices_by_product()

    revenue = cost = gross = 0
    for line, _inv, _pn, _sku, _cat, _cust in repo.margin_lines_between(start, end):
        if line.product_id not in buy_prices:
            continue
        line_revenue = int(line.line_subtotal_minor)
        line_gp = margin.gp(line)
        revenue += line_revenue
        gross += line_gp
        cost += line_revenue - line_gp

    report = MarginAnalysisService(db).by_dimension("product", date_from=start, date_to=end)
    assert report.revenue_minor == revenue
    assert report.gp_minor == gross
    assert report.cost_minor == cost
    assert report.margin_bps == _bps(gross, revenue)

    # Tax-exclusive: the subtotal, never the total.
    _sub, total_with_tax = repo.invoiced_between(start, end)
    assert report.revenue_minor < total_with_tax, "revenue looks like it includes GST"


def test_r11_6_a_line_with_no_purchase_price_is_unknown_not_a_100_percent_margin(db):
    """The most misleading number this checkpoint could have produced.

    `MarginService.gp` reads a missing purchase price as zero, so an unpriced line returns the
    full selling price as profit. The seed contains exactly one such product (listed, never
    bought), so the projection has to exclude and count it.
    """
    from app.modules.pricing.service import MarginService

    start, end = _window()
    repo = FinanceRepository(db)
    buy_prices = repo.purchase_prices_by_product()
    unpriced = [
        (line, inv)
        for line, inv, _pn, _sku, _cat, _cust in repo.margin_lines_between(start, end)
        if line.product_id not in buy_prices
    ]
    assert unpriced, "the seed has no unpriced line — this path is undemoed (G14)"

    # Confirm gp really would call it pure profit, so the exclusion is not theoretical.
    line, _inv = unpriced[0]
    assert MarginService(db).gp(line) == int(line.line_subtotal_minor), (
        "gp no longer reports an unpriced line as 100% margin — re-check this guard"
    )

    report = MarginAnalysisService(db).by_dimension("product", date_from=start, date_to=end)
    assert report.unknown_cost_lines == len(unpriced)
    assert report.margin_bps != 10000, "the unpriced line leaked into the margin"
    # The excluded line contributes no revenue, so the total excludes its subtotal too.
    assert report.revenue_minor + sum(
        int(ln.line_subtotal_minor) for ln, _i in unpriced
    ) == sum(
        int(ln.line_subtotal_minor)
        for ln, _i, _pn, _sku, _cat, _cu in repo.margin_lines_between(start, end)
    )


def test_r11_6_the_unknown_cost_lines_are_stated_in_the_explanation(db):
    """G11: a figure that excludes data has to say so."""
    start, end = _window()
    report = MarginAnalysisService(db).by_dimension("product", date_from=start, date_to=end)
    assert report.unknown_cost_lines > 0
    assert report.explained.caveat, "lines were excluded and the explanation is silent"
    assert "no recorded purchase price" in report.explained.caveat
    assert "100% margin" in report.explained.caveat
    assert report.explained.is_known
    assert report.explained.records, "G11 wants the records it reasoned from"
    assert "MarginService.gp" in report.explained.formula
    assert "tax-EXCLUSIVE" in report.explained.formula


def test_r11_6_a_window_with_no_sales_says_unknown_rather_than_zero_percent(db):
    far = date.today() + timedelta(days=900)
    report = MarginAnalysisService(db).by_dimension(
        "product", date_from=far, date_to=far + timedelta(days=30)
    )
    assert report.rows == []
    assert report.margin_bps is None
    assert not report.explained.is_known
    assert report.explained.display == "unknown"
    assert "nothing to divide" in report.explained.unknown_reason


# --- R11.7 / R11.8: leakage ------------------------------------------------


def test_r11_8_each_indicator_fires_on_its_offender_and_stays_silent_otherwise(db):
    """R11.8's acceptance criterion, both halves.

    The seed carries one below-cost line and one line 20% below list that is deliberately
    still ABOVE cost — so "fires" and "stays silent" are demonstrated by different lines of
    the same invoice rather than by the absence of data.
    """
    start, end = _window()
    report = MarginAnalysisService(db).leakage(date_from=start, date_to=end)
    by_key = {i.key: i for i in report.indicators}
    assert set(by_key) == {"sold_below_cost", "discount_creep"}

    below = by_key["sold_below_cost"]
    creep = by_key["discount_creep"]
    assert below.fired, "the seeded below-cost line did not trip the indicator"
    assert creep.fired, "the seeded discount did not trip the indicator"

    below_docs = {(r.doc_no, r.product_name) for r in below.records}
    creep_docs = {(r.doc_no, r.product_name) for r in creep.records}
    assert creep_docs - below_docs, (
        "every discount-creep offender is also below cost — the two indicators cannot be "
        "told apart on this data, so 'stays silent otherwise' is untested"
    )

    for indicator in report.indicators:
        assert indicator.impact_minor == sum(r.impact_minor for r in indicator.records)
        assert indicator.impact_minor > 0

    # The indicators overlap — the below-cost line is also a deep discount — so the distinct
    # line count is smaller than the sum of the two record lists. The screen reports the
    # distinct count rather than a single summed "total leakage", which would be two different
    # quantities added together and read as a loss nobody made.
    total_records = sum(len(i.records) for i in report.indicators)
    assert report.flagged_line_count < total_records, (
        "the indicators do not overlap on this data, so the distinct-count guard is untested"
    )


def test_r11_8_every_record_is_clickable_and_names_its_reference(db):
    """An indicator with nothing to click must not exist — so every record has a target."""
    start, end = _window()
    report = MarginAnalysisService(db).leakage(date_from=start, date_to=end)
    seen = 0
    for indicator in report.indicators:
        for record in indicator.records:
            assert record.href.startswith("/invoices/"), record.doc_no
            assert record.doc_no and record.product_name
            assert record.impact_minor > 0
            assert record.reference_minor > 0
            assert record.reference_label in ("Purchase price", "List price")
            assert record.detail.strip()
            seen += 1
    assert seen >= 2, f"only {seen} offending records — too few to prove R11.8"


def test_r11_7_the_below_cost_indicator_matches_a_negative_gross_profit(db):
    from app.modules.pricing.service import MarginService

    start, end = _window()
    repo = FinanceRepository(db)
    margin = MarginService(db)
    buy_prices = repo.purchase_prices_by_product()
    expected = [
        (inv.invoice_no, -margin.gp(line))
        for line, inv, _pn, _sku, _cat, _cust in repo.margin_lines_between(start, end)
        if line.product_id in buy_prices and margin.gp(line) < 0
    ]
    assert expected, "no below-cost line in the window"

    indicator = next(
        i
        for i in MarginAnalysisService(db).leakage(date_from=start, date_to=end).indicators
        if i.key == "sold_below_cost"
    )
    assert sorted(expected) == sorted((r.doc_no, r.impact_minor) for r in indicator.records)


def test_r11_7_discount_creep_uses_the_stated_threshold_at_both_edges(db):
    """The boundary is stated on screen and pinned here: exactly at the threshold is clean."""
    start, end = _window()
    repo = FinanceRepository(db)
    list_prices = repo.list_prices()
    indicator = next(
        i
        for i in MarginAnalysisService(db).leakage(date_from=start, date_to=end).indicators
        if i.key == "discount_creep"
    )
    assert f"{DISCOUNT_CREEP_BPS // 100}%" in indicator.rule
    assert "is not an offender" in indicator.rule

    # Every reported record is STRICTLY past the threshold...
    for record in indicator.records:
        listed = record.reference_minor
        discount_bps = _bps(listed - record.unit_price_minor, listed)
        assert discount_bps > DISCOUNT_CREEP_BPS, f"{record.doc_no} is not past the threshold"

    # ...and no line at or under the threshold was reported.
    reported = {(r.doc_no, r.product_name) for r in indicator.records}
    for line, inv, product_name, _sku, _cat, _cust in repo.margin_lines_between(start, end):
        listed = list_prices.get(line.product_id)
        if not listed or int(line.unit_price_minor) >= listed:
            continue
        discount_bps = _bps(listed - int(line.unit_price_minor), listed) or 0
        if discount_bps <= DISCOUNT_CREEP_BPS:
            assert (inv.invoice_no, product_name) not in reported


def test_r11_7_freight_is_reported_as_not_measured_not_as_an_empty_indicator(db):
    """R11.8: an indicator that can never produce a record must not exist.

    There is no freight, shipping, carriage or delivery-charge field anywhere in the schema, so
    the honest move is to name the gap. It must NOT appear among the indicators, because an
    indicator showing zero would claim freight had been checked and found clean.
    """
    start, end = _window()
    report = MarginAnalysisService(db).leakage(date_from=start, date_to=end)
    assert "freight_not_recovered" not in {i.key for i in report.indicators}
    gaps = {g["key"]: g for g in report.not_measured}
    assert "freight_not_recovered" in gaps
    reason = gaps["freight_not_recovered"]["reason"]
    assert "no freight" in reason
    assert "product decision" in reason


def test_r11_8_a_quiet_window_reports_no_offenders_without_removing_the_indicator(db):
    """"Found nothing this window" and "cannot ever find anything" are different claims."""
    far = date.today() + timedelta(days=900)
    report = MarginAnalysisService(db).leakage(
        date_from=far, date_to=far + timedelta(days=30)
    )
    assert len(report.indicators) == 2, "an indicator vanished when it found nothing"
    for indicator in report.indicators:
        assert not indicator.fired
        assert indicator.impact_minor == 0
        assert indicator.explained.is_known
        assert "clean result" in indicator.explained.caveat
    assert report.total_impact_minor == 0


# --- R11.9 / R11.10: GST ---------------------------------------------------


def test_r11_9_gst_is_reported_by_period_with_a_net_position(db):
    start, end = _window()
    summary = GstService(db).summary(date_from=start, date_to=end)
    assert len(summary.rows) > 1, "a single row is not 'by period' (R11.9)"
    assert [r.period_from for r in summary.rows] == sorted(r.period_from for r in summary.rows)
    for row in summary.rows:
        assert row.net_tax_minor == row.output_tax_minor - row.input_tax_minor
    assert summary.net_tax_minor == summary.output_tax_minor - summary.input_tax_minor
    assert summary.output_tax_minor > 0, "no output GST — the screen cannot be exercised"


def test_r11_9_the_periods_sum_to_the_documents_in_the_window(db):
    start, end = _window()
    repo = FinanceRepository(db)
    summary = GstService(db).summary(date_from=start, date_to=end)

    inv_rows = repo.invoice_tax_rows_between(start, end)
    bill_rows = repo.bill_tax_rows_between(start, end)
    assert summary.output_tax_minor == sum(tax for _d, _s, tax in inv_rows)
    assert summary.input_tax_minor == sum(tax for _d, _s, tax in bill_rows)
    assert summary.output_taxable_minor == sum(sub for _d, sub, _t in inv_rows)
    assert summary.input_taxable_minor == sum(sub for _d, sub, _t in bill_rows)
    assert sum(r.output_tax_minor for r in summary.rows) == summary.output_tax_minor


def test_r11_9_a_month_with_no_trade_still_appears(db):
    """A gap in the sequence would read as a missing month rather than a quiet one."""
    start, end = _window()
    summary = GstService(db).summary(date_from=start, date_to=end)
    quiet = [r for r in summary.rows if r.output_tax_minor == 0 and r.input_tax_minor == 0]
    assert quiet, "every month traded — the empty-month path is untested"


def test_r11_9_the_net_position_is_described_in_words_not_only_by_its_sign():
    assert "payable" in GstService.position_text(100)
    assert "credit" in GstService.position_text(-100)
    assert GstService.position_text(0) == "nothing to pay or reclaim"


def test_r11_10_the_gst_report_delegates_to_the_one_definition(db):
    """`ReportService._gst_summary` had its own arithmetic and was not by period (G16)."""
    from app.modules.reports.service import ReportService

    start, end = _window()
    result = ReportService(db).run("gst-summary", date_from=start, date_to=end)
    summary = GstService(db).summary(date_from=start, date_to=end)

    assert "period" in result.columns, "the report is still not reporting by period"
    assert "kind" not in result.columns, "the old three-row shape survives"
    # One row per period plus a total row.
    assert len(result.rows) == len(summary.rows) + 1
    assert result.rows[-1]["period"] == "Total"
    assert result.rows[-1]["net_tax_minor"] == summary.net_tax_minor
    for row, expected in zip(result.rows[:-1], summary.rows, strict=True):
        assert row["period"] == expected.label
        assert row["output_tax_minor"] == expected.output_tax_minor


def test_r11_10_nothing_in_the_gst_module_files_a_return(db):
    """R11.10 — a report only. No submission, no portal, no filing workflow.

    Asserted STRUCTURALLY, on the module's imports and its public surface, rather than by
    grepping its source. A text search cannot tell a call from a comment: the first version of
    this test searched for "portal" and failed on the docstring promising there isn't one —
    which is the exact trap already recorded twice in this build.
    """
    from types import ModuleType

    import app.modules.finance.gst as gst_module

    imported = {
        value.__name__
        for value in vars(gst_module).values()
        if isinstance(value, ModuleType)
    }
    for network in ("requests", "httpx", "urllib", "http", "socket", "aiohttp"):
        assert not any(name.split(".")[0] == network for name in imported), (
            f"the GST module imports {network} — a report does not talk to anything"
        )

    public = {name for name in dir(GstService) if not name.startswith("_")}
    assert public == {"summary", "default_summary", "position_text"}, (
        f"GstService grew a verb beyond reporting: {sorted(public)}"
    )


# --- R11.10 (G15) and R11.14 ----------------------------------------------


def test_r11_5_the_margin_projections_write_no_activity_row(db):
    before = db.scalar(select(func.count()).select_from(ActivityLog)) or 0
    start, end = _window()
    svc = MarginAnalysisService(db)
    for dimension in DIMENSION_LABELS:
        svc.by_dimension(dimension, date_from=start, date_to=end)
    svc.leakage(date_from=start, date_to=end)
    GstService(db).summary(date_from=start, date_to=end)
    assert (db.scalar(select(func.count()).select_from(ActivityLog)) or 0) == before


def test_r11_12_every_margin_and_gst_figure_is_an_integer(db):
    def whole(value, label):
        assert isinstance(value, int) and not isinstance(value, bool), (
            f"{label} is {type(value).__name__}, not an integer"
        )

    start, end = _window()
    svc = MarginAnalysisService(db)
    for dimension in DIMENSION_LABELS:
        report = svc.by_dimension(dimension, date_from=start, date_to=end)
        for field in ("revenue_minor", "cost_minor", "gp_minor", "line_count",
                      "unknown_cost_lines"):
            whole(getattr(report, field), f"{dimension}.{field}")
        if report.margin_bps is not None:
            whole(report.margin_bps, f"{dimension}.margin_bps")
        for row in report.rows:
            for field in ("revenue_minor", "cost_minor", "gp_minor", "line_count"):
                whole(getattr(row, field), f"{dimension}.{row.label}.{field}")

    for indicator in svc.leakage(date_from=start, date_to=end).indicators:
        whole(indicator.impact_minor, f"{indicator.key}.impact")
        for record in indicator.records:
            whole(record.impact_minor, f"{indicator.key}.record.impact")
            whole(record.unit_price_minor, f"{indicator.key}.record.unit_price")

    summary = GstService(db).summary(date_from=start, date_to=end)
    for field in ("output_tax_minor", "input_tax_minor", "net_tax_minor"):
        whole(getattr(summary, field), f"gst.{field}")
    for row in summary.rows:
        whole(row.net_tax_minor, f"gst.{row.label}.net")


def _rows(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body.lstrip("﻿"))))


def test_r11_14_the_margin_export_respects_the_dimension_on_screen(client, db):
    start, end = _window()
    base = f"date_from={start}&date_to={end}"
    for dimension in DIMENSION_LABELS:
        response = client.get(f"/finance/margin?dimension={dimension}&{base}&export=csv")
        assert response.status_code == 200
        rows = _rows(response.text)
        assert rows[0][0] == "Name"
        expected = MarginAnalysisService(db).by_dimension(
            dimension, date_from=start, date_to=end
        )
        assert len(rows) - 1 == len(expected.rows), dimension


def test_r11_14_the_leakage_export_carries_one_row_per_offending_record(client, db):
    start, end = _window()
    rows = _rows(client.get(f"/finance/leakage?date_from={start}&date_to={end}&export=csv").text)
    assert rows[0][0] == "Indicator"
    report = MarginAnalysisService(db).leakage(date_from=start, date_to=end)
    assert len(rows) - 1 == sum(len(i.records) for i in report.indicators)
    assert all(row[0].strip() for row in rows[1:]), "a record exported with no indicator name"


def test_r11_14_the_gst_export_carries_every_period(client, db):
    start, end = _window()
    rows = _rows(client.get(f"/finance/gst?date_from={start}&date_to={end}&export=csv").text)
    assert rows[0] == [
        "Period", "Sales ex-GST", "Output GST", "Purchases ex-GST", "Input GST", "Net GST",
    ]
    assert len(rows) - 1 == len(GstService(db).summary(date_from=start, date_to=end).rows)


def test_r11_14_the_screens_render_and_state_their_rules(client):
    margin = client.get("/finance/margin")
    assert "not an inventory valuation" in margin.text
    assert "collected for the government rather than earned" in margin.text

    leakage = client.get("/finance/leakage")
    assert "Sold below purchase price" in leakage.text
    assert "Discount creep" in leakage.text
    assert "Not measured" in leakage.text
    assert "no freight, shipping, carriage or delivery charge" in leakage.text
    assert "They are not added together" in leakage.text, (
        "the screen does not warn that the indicators measure different quantities"
    )

    gst = client.get("/finance/gst")
    assert "Output GST (sales)" in gst.text
    assert "does not file returns" in gst.text


def test_r11_5_the_margin_screen_offers_every_dimension(client):
    text = client.get("/finance/margin").text
    for _key, label in MARGIN_DIMENSIONS:
        assert f">{label}</option>" in text, f"{label} is not offered on the margin screen"


def test_r11_14_no_decorative_chart_was_added(client):
    """R11.14: if a chart does not change a decision, it is a table."""
    for path in ("/finance/margin", "/finance/leakage", "/finance/gst"):
        text = client.get(path).text
        for marker in ("<svg", "<canvas", "chart.js", "Chart("):
            assert marker not in text, f"{path} carries {marker!r}"


def test_the_finance_index_links_to_the_c3_screens(client):
    text = client.get("/finance").text
    for href in ("/finance/margin", "/finance/leakage", "/finance/gst"):
        assert f'href="{href}"' in text, f"{href} is not reachable from /finance"


def test_r11_13_a_bad_window_renders_the_c3_screens(client):
    for path in ("/finance/margin", "/finance/leakage", "/finance/gst"):
        assert client.get(f"{path}?date_from=nonsense&date_to=bad").status_code == 200
    assert client.get("/finance/margin?dimension=not-a-dimension").status_code == 200
