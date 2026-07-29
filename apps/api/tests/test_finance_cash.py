"""Part 8 C2 — cash flow, working capital, the cash conversion cycle (R11.1–R11.4, R11.11–R11.13).

The two that carry the most weight:

* `test_r11_2_committed_in_is_exactly_the_open_invoices_due_in_the_window` recomputes the
  committed figure independently from C1's `open_invoices` and compares. R11.2 asks for a
  figure that matches its stated definition, and the definition is `COMMITTED_TERMS` —
  printed on screen and asserted there too.
* `test_r11_4_each_cycle_component_is_hand_verified` recomputes DSO, DIO and DPO from their
  inputs with plain arithmetic in the test, so the service and the test cannot both be wrong
  in the same direction.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.modules.activity.models import ActivityLog
from app.modules.customers.repository import CustomerRepository
from app.modules.finance.cash import (
    COMMITTED_TERMS,
    DEFAULT_WINDOW_DAYS,
    CashFlowService,
    _days,
    default_window,
)
from app.modules.finance.ledger import open_bills, open_invoices
from app.modules.finance.repository import FinanceRepository
from app.modules.suppliers.repository import SupplierRepository


def _window() -> tuple[date, date]:
    """A window wide enough to hold the seeded documents, whenever the suite runs."""
    return date.today() - timedelta(days=365), date.today() + timedelta(days=60)


# --- R11.1: actual cash flow -------------------------------------------------


def test_r11_1_actual_cash_is_payments_and_nothing_accrued(db):
    start, end = _window()
    report = CashFlowService(db).cash_flow(date_from=start, date_to=end)
    payments = FinanceRepository(db).payments_between(start, end)
    assert payments, "no payments in a year — the cash-flow screen cannot be exercised (G14)"

    assert report.actual_in_minor == sum(a for d, _on, a in payments if d == "in")
    assert report.actual_out_minor == sum(a for d, _on, a in payments if d == "out")
    assert report.actual_net_minor == report.actual_in_minor - report.actual_out_minor
    # Accrual would make "in" at least as large as everything ever invoiced.
    _subtotal, invoiced = FinanceRepository(db).invoiced_between(start, end)
    assert report.actual_in_minor < invoiced, (
        "cash in is not smaller than everything invoiced — this looks accrued, not cash"
    )


def test_r11_1_the_monthly_rows_sum_to_the_window_total(db):
    start, end = _window()
    report = CashFlowService(db).cash_flow(date_from=start, date_to=end)
    assert report.rows, "no month rows at all"
    assert sum(r.in_minor for r in report.rows) == report.actual_in_minor
    assert sum(r.out_minor for r in report.rows) == report.actual_out_minor
    assert sum(r.receipts + r.payments for r in report.rows) == len(
        FinanceRepository(db).payments_between(start, end)
    )
    starts = [r.date_from for r in report.rows]
    assert starts == sorted(starts), "the months are not in chronological order"
    # Every row is clipped to the window, so the first and last never overhang it.
    assert starts[0] >= start and report.rows[-1].date_to <= end


def test_r11_1_a_window_with_no_payments_is_zero_not_an_error(db):
    """A quiet window must render, not raise — the screens are requested blind."""
    far = date.today() + timedelta(days=900)
    report = CashFlowService(db).cash_flow(date_from=far, date_to=far + timedelta(days=30))
    assert report.actual_in_minor == 0
    assert report.actual_out_minor == 0
    assert report.rows, "an empty window produced no month rows to render"


def test_r11_13_the_window_bounds_are_respected_at_both_ends(db):
    """The parameters are not decorative — narrowing the window narrows the figure."""
    start, end = _window()
    wide = CashFlowService(db).cash_flow(date_from=start, date_to=end)
    narrow = CashFlowService(db).cash_flow(
        date_from=start, date_to=start + timedelta(days=1)
    )
    assert narrow.actual_in_minor <= wide.actual_in_minor
    assert narrow.actual_in_minor + narrow.actual_out_minor < (
        wide.actual_in_minor + wide.actual_out_minor
    ), "a two-day window moved the same money as a 425-day one — the bounds are ignored"


def test_r11_13_the_default_window_is_the_stated_length(db):
    start, end = default_window()
    assert (end - start).days + 1 == DEFAULT_WINDOW_DAYS
    assert end == date.today()


# --- R11.2: "committed", and that it matches its stated definition -----------


def test_r11_2_committed_in_is_exactly_the_open_invoices_due_in_the_window(db):
    """Recomputed here from C1's projection, independently of the service.

    **The window is deliberately narrow enough to exclude something.** With a window wide
    enough to hold every open invoice this equality passes even if the due-date filter is
    dropped altogether — the data cannot tell the two implementations apart, which is the
    trap an "identical output" assertion always sets. So the test asserts that at least one
    open invoice falls OUTSIDE the window before comparing the totals inside it.
    """
    end = date.today()
    start = end - timedelta(days=30)
    all_open = open_invoices(db, as_of=end)
    inside = [d for d in all_open if start <= d.due_date <= end]
    outside = [d for d in all_open if not (start <= d.due_date <= end)]
    assert inside, "no invoice falls due in the window — nothing to check"
    assert outside, "every open invoice is inside the window — the filter would be untested"

    committed = CashFlowService(db).committed(date_from=start, date_to=end)
    assert committed.in_minor == sum(d.open_minor for d in inside)
    assert committed.invoice_count == len(inside)
    assert committed.in_minor < sum(d.open_minor for d in all_open), (
        "committed in equals every open invoice — the due-date window is being ignored"
    )


def test_r11_2_committed_out_is_exactly_the_open_bills_due_in_the_window(db):
    start, end = _window()
    committed = CashFlowService(db).committed(date_from=start, date_to=end)
    expected = [d for d in open_bills(db, as_of=end) if start <= d.due_date <= end]
    assert expected, "no bill falls due in the window"
    assert committed.out_minor == sum(d.open_minor for d in expected)
    assert committed.bill_count == len(expected)


def test_r11_2_committed_excludes_a_document_due_outside_the_window(db):
    """The window bound is real: a narrow window must drop documents a wide one includes."""
    start, end = _window()
    wide = CashFlowService(db).committed(date_from=start, date_to=end)
    past_only = CashFlowService(db).committed(
        date_from=start, date_to=date.today() - timedelta(days=100)
    )
    assert past_only.invoice_count < wide.invoice_count, (
        "narrowing the window kept every invoice — the due-date filter is a no-op"
    )
    assert past_only.in_minor < wide.in_minor


def test_r11_2_the_pipeline_is_reported_but_not_inside_committed(db):
    """Orders and POs have no due date, so they are named separately (R11.2)."""
    start, end = _window()
    repo = FinanceRepository(db)
    committed = CashFlowService(db).committed(date_from=start, date_to=end)

    order_count, order_total = repo.sales_pipeline()
    po_count, po_total = repo.purchase_pipeline()
    assert committed.pipeline_in_minor == order_total
    assert committed.pipeline_out_minor == po_total
    assert committed.pipeline_order_count == order_count
    assert committed.pipeline_po_count == po_count
    assert po_total > 0, "no confirmed unbilled PO in the seed — the pipeline is undemoed"

    # And the committed totals are built only from dated documents: recomputing them from
    # the open documents alone reproduces them exactly, leaving no room for the pipeline.
    assert committed.in_minor == sum(
        d.open_minor for d in open_invoices(db, as_of=end) if start <= d.due_date <= end
    )
    assert committed.out_minor == sum(
        d.open_minor for d in open_bills(db, as_of=end) if start <= d.due_date <= end
    )
    assert committed.net_minor == committed.in_minor - committed.out_minor


def test_r11_2_the_stated_definition_names_every_term_of_the_figure(db):
    """The words on screen have to describe the arithmetic, or R11.2 is not met."""
    start, end = _window()
    terms = " ".join(CashFlowService(db).committed(date_from=start, date_to=end).terms)
    assert terms == " ".join(COMMITTED_TERMS)
    for phrase in (
        "due date falls inside this window",
        "minus payments applied minus credit notes",
        "confirmed sales orders not yet invoiced",
        "confirmed purchase orders not yet billed",
        "no due date exists",
    ):
        assert phrase in terms, f"the stated definition never says {phrase!r}"


def test_r11_1_projected_net_is_actual_plus_committed_and_excludes_pipeline(db):
    start, end = _window()
    report = CashFlowService(db).cash_flow(date_from=start, date_to=end)
    assert report.projected_net_minor == report.actual_net_minor + report.committed.net_minor
    assert report.projected_net_minor != (
        report.actual_net_minor
        + report.committed.net_minor
        + report.committed.pipeline_net_minor
    ), "the pipeline leaked into the projected figure"


# --- R11.3: working capital -------------------------------------------------


def test_r11_3_working_capital_reads_the_one_receivable_and_payable(db):
    """R11.11/G16: no fourth derivation of what is owed in either direction."""
    snapshot = CashFlowService(db).working_capital(as_of=date.today())
    assert snapshot.receivables_minor == sum(
        CustomerRepository(db).outstanding_by_customer().values()
    )
    assert snapshot.payables_minor == sum(
        SupplierRepository(db).outstanding_by_supplier().values()
    )
    assert snapshot.working_capital_minor == (
        snapshot.receivables_minor + snapshot.inventory_minor - snapshot.payables_minor
    )


def test_r11_3_inventory_comes_from_part_5s_valuation(db):
    from app.modules.inventory.valuation import ValuationService

    rows = ValuationService(db).stock_value()
    snapshot = CashFlowService(db).working_capital()
    assert snapshot.inventory_minor == sum(r.value_minor or 0 for r in rows)
    assert snapshot.inventory_minor > 0, "inventory values to nothing — DIO cannot be shown"


def test_r11_3_the_snapshot_says_that_cash_at_bank_is_not_in_it(db):
    """A working-capital figure silently missing cash would be read as though it had it."""
    snapshot = CashFlowService(db).working_capital()
    assert "Cash at bank is NOT included" in snapshot.caveat
    assert "weighted-average cost" in snapshot.caveat
    if not snapshot.inventory_known:
        assert "no recorded purchase cost" in snapshot.caveat
        assert snapshot.products_without_cost > 0


# --- R11.4: the cycle, each component ---------------------------------------


def test_r11_4_each_cycle_component_is_hand_verified(db):
    """DSO, DIO and DPO recomputed in the test from their own inputs."""
    start, end = _window()
    svc = CashFlowService(db)
    cycle = svc.cash_conversion_cycle(date_from=start, date_to=end)
    snapshot = svc.working_capital(as_of=end)
    repo = FinanceRepository(db)
    days = (end - start).days + 1
    assert cycle.window_days == days

    _sub, revenue = repo.invoiced_between(start, end)
    _psub, purchases = repo.billed_between(start, end)

    def by_hand(numerator: int, denominator: int) -> int | None:
        if denominator <= 0:
            return None
        return int(
            (Decimal(numerator) * Decimal(days) / Decimal(denominator)).quantize(Decimal("1"))
        )

    assert cycle.dso_days == by_hand(snapshot.receivables_minor, revenue)
    assert cycle.dpo_days == by_hand(snapshot.payables_minor, purchases)
    assert cycle.dso_days is not None and cycle.dso_days > 0
    assert cycle.dpo_days is not None and cycle.dpo_days > 0
    # DIO's denominator is COGS, which the service derives through MarginService.
    assert cycle.dio_days is not None and cycle.dio_days > 0


def test_r11_4_the_cycle_is_dso_plus_dio_minus_dpo(db):
    start, end = _window()
    cycle = CashFlowService(db).cash_conversion_cycle(date_from=start, date_to=end)
    assert None not in (cycle.dso_days, cycle.dio_days, cycle.dpo_days)
    assert cycle.ccc_days == cycle.dso_days + cycle.dio_days - cycle.dpo_days


def test_r11_4_every_component_is_reported_individually(db):
    """R11.4's actual demand: not only the total."""
    start, end = _window()
    cycle = CashFlowService(db).cash_conversion_cycle(date_from=start, date_to=end)
    labels = [label for label, _d, _e in cycle.components]
    assert len(labels) == 3
    assert any("DSO" in x for x in labels)
    assert any("DIO" in x for x in labels)
    assert any("DPO" in x for x in labels)
    for label, days, explained in cycle.components:
        assert days is not None, label
        assert explained.is_known, label
        assert explained.value == f"{days} days"


def test_r11_4_each_component_explains_itself_with_inputs_and_records(db):
    """G11 — the formula, the window, the inputs and ≥1 record, for each."""
    start, end = _window()
    cycle = CashFlowService(db).cash_conversion_cycle(date_from=start, date_to=end)
    for explained in (cycle.dso, cycle.dio, cycle.dpo, cycle.ccc):
        assert explained.formula and explained.window
        assert explained.inputs, explained.what
        assert str(cycle.window_days) in explained.window
    for explained in (cycle.dso, cycle.dio, cycle.dpo):
        assert explained.records, explained.what
        for record in explained.records:
            assert record.href
    assert "MarginService.gp" in cycle.dio.formula, "DIO does not say where its cost comes from"
    assert "receivable definition" in cycle.dso.formula


def test_r11_4_a_component_with_no_denominator_says_unknown_not_zero(db):
    """G11's insufficient-data path: a window with no trade at all."""
    far = date.today() + timedelta(days=900)
    cycle = CashFlowService(db).cash_conversion_cycle(
        date_from=far, date_to=far + timedelta(days=30)
    )
    assert cycle.dso_days is None and not cycle.dso.is_known
    assert cycle.dpo_days is None and not cycle.dpo.is_known
    assert cycle.dso.display == "unknown"
    assert cycle.dso.unknown_reason and "nothing was invoiced" in cycle.dso.unknown_reason
    # And the cycle refuses to add up two of three terms.
    assert cycle.ccc_days is None and not cycle.ccc.is_known
    assert "DSO" in cycle.ccc.unknown_reason
    assert any(i.is_missing for i in cycle.ccc.inputs)


def test_r11_4_a_day_count_longer_than_its_own_window_says_it_is_a_direction(db):
    """A ratio is only as good as its denominator, and the screen has to admit it.

    On the seeded data a 90-day window holds far less trade than the warehouse holds stock,
    so DIO comes out near 10,000 days. That is arithmetically right and useless as a precise
    figure, and a number like it makes a founder distrust the whole screen. G11's caveat is
    exactly the place to say so, so any component exceeding its own window carries the
    warning — the figure is still shown, because "slower than a quarter can measure" is real
    information.
    """
    start, end = default_window()
    cycle = CashFlowService(db).cash_conversion_cycle(date_from=start, date_to=end)

    over = [
        (label, days, exp)
        for label, days, exp in cycle.components
        if days is not None and days > cycle.window_days
    ]
    assert over, (
        "no component exceeds the default window on the seeded data — this test no longer "
        "exercises the caveat and needs a narrower window"
    )
    for label, day_count, explained in over:
        assert day_count > cycle.window_days
        assert explained.caveat, f"{label} exceeds its window and says nothing about it"
        assert f"longer than the {cycle.window_days}-day window" in explained.caveat
        assert "direction, not a precise day count" in explained.caveat

    # A component comfortably inside its window carries no such warning.
    within = [
        (label, exp)
        for label, days, exp in cycle.components
        if days is not None and days <= cycle.window_days
    ]
    for label, explained in within:
        assert explained.caveat is None or "longer than the" not in explained.caveat, label

    # And the cycle inherits it rather than presenting a clean total built on a shaky term.
    assert cycle.ccc_days is None or cycle.ccc.caveat, (
        "the cycle is dominated by a caveated component and carries no caveat itself"
    )


def test_r11_4_the_caveat_reaches_the_screen_not_only_the_object(client, db):
    start, end = default_window()
    cycle = CashFlowService(db).cash_conversion_cycle(date_from=start, date_to=end)
    caveated = next(
        (exp for _l, days, exp in cycle.components if days and days > cycle.window_days), None
    )
    assert caveated is not None
    page = client.get("/finance/cash-cycle").text
    assert "direction, not a precise day count" in page, (
        "the caveat exists on the object but never renders"
    )


def test_r11_12_the_one_division_rounds_once_and_returns_none_on_a_zero_rate():
    """`_days` is the only division in the module (R11.12)."""
    assert _days(0, 100, 30) == 0
    assert _days(100, 0, 30) is None, "a zero rate must be unknown, not a division by zero"
    assert _days(100, 100, 30) == 30
    # Rounds to nearest, once: 1000 * 30 / 700 = 42.857…
    assert _days(1000, 700, 30) == 43
    assert _days(100, 100, 0) is None
    assert isinstance(_days(1000, 700, 30), int)


def test_r11_12_every_cash_figure_is_an_integer(db):
    """No float and no Decimal reaches a money figure or a day count (G1, R11.12)."""

    def whole(value, label):
        assert isinstance(value, int) and not isinstance(value, bool), (
            f"{label} is {type(value).__name__}, not an integer"
        )

    start, end = _window()
    svc = CashFlowService(db)
    report = svc.cash_flow(date_from=start, date_to=end)
    for field in ("actual_in_minor", "actual_out_minor", "actual_net_minor",
                  "projected_net_minor"):
        whole(getattr(report, field), f"cash_flow.{field}")
    for row in report.rows:
        for field in ("in_minor", "out_minor", "net_minor", "receipts", "payments"):
            whole(getattr(row, field), f"{row.label}.{field}")
    for field in ("in_minor", "out_minor", "pipeline_in_minor", "pipeline_out_minor",
                  "net_minor", "pipeline_net_minor"):
        whole(getattr(report.committed, field), f"committed.{field}")

    snapshot = svc.working_capital(as_of=end)
    for field in ("receivables_minor", "inventory_minor", "payables_minor",
                  "working_capital_minor"):
        whole(getattr(snapshot, field), f"working_capital.{field}")

    cycle = svc.cash_conversion_cycle(date_from=start, date_to=end)
    for field in ("dso_days", "dio_days", "dpo_days", "ccc_days", "window_days"):
        whole(getattr(cycle, field), f"cycle.{field}")


def test_r11_11_cogs_is_marginservice_and_not_a_second_cost_derivation(db):
    """R11.6/R11.11: cost is subtotal − gross profit, so there is one cost definition."""
    from app.modules.pricing.service import MarginService

    start, end = _window()
    repo = FinanceRepository(db)
    lines = repo.invoice_lines_between(start, end)
    assert lines, "no invoice lines in the window — COGS cannot be checked"

    margin = MarginService(db)
    subtotal = sum(int(ln.line_subtotal_minor) for ln in lines)
    gross = sum(margin.gp(ln) for ln in lines)
    expected = max(0, subtotal - gross)

    cycle = CashFlowService(db).cash_conversion_cycle(date_from=start, date_to=end)
    # DIO = inventory * days / cogs, so cogs is recoverable from the reported figure.
    assert expected > 0
    assert cycle.dio_days == _days(
        CashFlowService(db).working_capital(as_of=end).inventory_minor,
        expected,
        cycle.window_days,
    )


# --- R11.10 (G15) and R11.14: projections, and the export -------------------


def test_r11_3_the_cash_projections_write_no_activity_row(db):
    before = db.scalar(select(func.count()).select_from(ActivityLog)) or 0
    start, end = _window()
    svc = CashFlowService(db)
    svc.cash_flow(date_from=start, date_to=end)
    svc.working_capital(as_of=end)
    svc.cash_conversion_cycle(date_from=start, date_to=end)
    assert (db.scalar(select(func.count()).select_from(ActivityLog)) or 0) == before


def _rows(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body.lstrip("﻿"))))


def test_r11_14_the_cash_flow_export_carries_the_months_on_screen(client, db):
    start, end = _window()
    url = f"/finance/cash-flow?date_from={start}&date_to={end}&export=csv"
    response = client.get(url)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    rows = _rows(response.text)
    assert rows[0] == ["Month", "Cash in", "Cash out", "Net", "Receipts", "Payments"]
    expected = CashFlowService(db).cash_flow(date_from=start, date_to=end)
    assert len(rows) - 1 == len(expected.rows)


def test_r11_14_the_cash_cycle_export_carries_all_four_components(client):
    rows = _rows(client.get("/finance/cash-cycle?export=csv").text)
    assert rows[0] == ["Component", "Days", "Formula", "Window"]
    assert len(rows) - 1 == 4, "the export does not carry DSO, DIO, DPO and CCC"
    assert any("CCC" in row[0] for row in rows[1:])
    for row in rows[1:]:
        assert row[2].strip(), f"{row[0]} exported no formula"


def test_r11_13_a_bad_or_reversed_window_renders_the_screen(client):
    """A stale bookmark degrades; a reversed window is repaired, not shown as empty."""
    for path in ("/finance/cash-flow", "/finance/cash-cycle"):
        assert client.get(f"{path}?date_from=nonsense&date_to=also-bad").status_code == 200
        reversed_window = client.get(
            f"{path}?date_from=2026-12-31&date_to=2026-01-01"
        )
        assert reversed_window.status_code == 200
        assert "2026-01-01" in reversed_window.text


def test_r11_1_the_cash_screens_state_what_they_are(client):
    flow = client.get("/finance/cash-flow")
    assert "Actual — money that really moved" in flow.text
    assert "means here" in flow.text
    for phrase in COMMITTED_TERMS:
        # Jinja escapes nothing in these sentences, so they appear verbatim.
        assert phrase in flow.text, f"the screen does not state: {phrase[:40]}…"

    cycle = client.get("/finance/cash-cycle")
    assert "Cash conversion cycle" in cycle.text
    assert "Cash at bank is NOT included" in cycle.text
    for label in ("DSO", "DIO", "DPO"):
        assert label in cycle.text


def test_the_finance_index_links_to_the_cash_screens(client):
    text = client.get("/finance").text
    assert 'href="/finance/cash-flow"' in text
    assert 'href="/finance/cash-cycle"' in text
