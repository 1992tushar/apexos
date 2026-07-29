"""Part 9 C1 — the Founder Command Center (R12.1–R12.13, G15).

Two kinds of test here, and the split is deliberate.

**Equality against the owning service.** Every figure on this page is asserted equal to
the call that produced it, because R12.10's whole point is that the homepage is not a
second definition of anything. An equality assertion between two code paths only tests
what the current data distinguishes — that lesson has cost this build four sessions — so
each of those tests also asserts a **floor**: the figure is non-zero on the seed, which
is what makes the equality mean "it read the right thing" rather than "both are 0".

**Structure rather than text.** The R12.10 walk inspects the service module's actual
namespace instead of grepping its source, because a source walk cannot tell a call from a
mention and Part 8's C3 failed one on its own docstring.
"""
from __future__ import annotations

from datetime import date

import pytest
from markupsafe import escape
from pydantic import ValidationError
from sqlalchemy import event, func, select

from app.modules.activity.models import ActivityLog
from app.modules.activity.service import ActivityService
from app.modules.command_center.schemas import Alert, AlertRecord, Figure
from app.modules.command_center.service import (
    ACTIVITY_LIMIT,
    QUICK_ACTIONS,
    CommandCenterService,
)
from app.modules.finance.ageing import AgeingService
from app.modules.finance.cash import CashFlowService, default_window
from app.modules.finance.ledger import today as finance_today
from app.modules.finance.margin import MarginAnalysisService
from app.modules.inventory.health import InventoryHealthService

#: Measured at **81** on the seeded dataset (Part 9 C1) — thirteen grouped projections of
#: 1–14 queries each, none of which grows with the row count.
#:
#: The ceiling is not "81 + a little". What this test exists to catch is a **per-row** read
#: creeping in, and that failure mode is not subtle: the seed has 311 products, 273 stock
#: states, 86 low-stock rows and 4 overdue customers, so any of them read one at a time
#: lands in the hundreds. A ceiling tight enough to fail on one added figure would be
#: re-litigated every checkpoint and eventually raised without measuring, which is worse
#: than a loose one that still catches the thing it is for. `PROGRESS.md` carries the
#: measurement itself (R12.12); this holds the shape (R12.13).
QUERY_CEILING = 120


@pytest.fixture()
def page(db):
    return CommandCenterService(db).load()


def _figure(page, key: str) -> Figure:
    match = [f for f in page.happened + page.position + page.attention if f.key == key]
    assert match, f"no figure named {key!r} on the page"
    return match[0]


def _rendered(text: str, value: str) -> bool:
    """Is this piece of *content* on the page, as Jinja would have written it?

    Compared through Jinja's own escaper rather than by eye: an alert saying "purchase
    order's promised date" lands with `&#39;`, and asserting the raw string finds nothing
    while the failure reads like a missing feature.

    Only ever pass the value — never the surrounding markup. Jinja escapes what it
    interpolates, not the quotes the template author typed, so escaping `href="..."` as a
    whole turns those quotes into `&#34;` and matches nothing. That is what `_linked` is
    for.
    """
    return str(escape(value)) in text


def _linked(text: str, href: str) -> bool:
    """Is there an anchor to `href`? The URL is escaped; the attribute quotes are not.

    A window carries `&date_to=`, which Jinja writes as `&amp;date_to=` — correct HTML,
    and the reason this cannot be a plain `in` check either.
    """
    return f'href="{escape(href)}"' in text


def _count_queries(db, fn):
    statements: list[str] = []

    def record(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        result = fn()
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)
    return result, statements


# --- R12.1: the three questions, in order -----------------------------------


def test_r12_1_the_page_asks_the_three_questions_in_order(client):
    """The ordering IS the requirement, not a layout preference."""
    text = client.get("/").text
    positions = [
        text.index("What happened"),
        text.index("What needs attention"),
        text.index("What should I do now"),
    ]
    assert positions == sorted(positions), (
        "R12.1 fixes the order: what happened, then what needs attention, then what to do"
    )


# --- R12.2: what happened, today --------------------------------------------


def test_r12_2_todays_revenue_and_gross_margin_are_the_margin_projections(db, page):
    """Both read off ONE `MarginReport` over a one-day window, so they cannot disagree.

    The floor matters as much as the equality: Part 9's seed adds an invoice dated today
    precisely so this is not `0 == 0`.
    """
    stamp = finance_today()
    report = MarginAnalysisService(db).by_dimension(
        "product", date_from=stamp, date_to=stamp
    )
    assert report.revenue_minor > 0, "the seed has no invoice dated today to measure"

    assert _figure(page, "revenue_today").value == report.revenue_minor
    assert _figure(page, "gross_margin_today").value == report.gp_minor
    assert report.margin_bps is not None, "today's margin should be known on the seed"


def test_r12_2_todays_margin_admits_the_lines_it_could_not_cost(page):
    """The seed's today-invoice carries one line with no purchase price on purpose.

    `MarginService.gp` reads a missing purchase price as zero and would report that line
    at a 100% margin, so the projection excludes and counts it — and the page says so
    rather than quietly reporting a margin over fewer lines than it implies.
    """
    assert page.happened_caveat, "the excluded-line caveat never reached the page"
    assert "no purchase price" in page.happened_caveat


def test_g11_a_day_with_no_costed_line_reports_unknown_not_zero(db):
    """The branch the seed cannot reach, driven directly.

    On the seeded data today's margin IS known, so the insufficient-data path would ship
    untested — and it is the one G11 cares most about: an unpriced product reports a 100%
    margin through `MarginService.gp`, so "0" and "unknown" are very different claims. The
    stub carries exactly the attributes the section reads.
    """
    from types import SimpleNamespace

    from app.db.explain import Explained

    unknown = Explained.unknown(
        what="Gross margin today",
        formula="selling − purchase price on the line",
        reason="no line today has a purchase price recorded",
    )
    margin = SimpleNamespace(
        revenue_minor=0,
        gp_minor=0,
        margin_bps=None,
        line_count=0,
        unknown_cost_lines=2,
        explained=unknown,
    )
    cash = SimpleNamespace(actual_in_minor=0, rows=[])

    figures, caveat = CommandCenterService(db)._what_happened(margin, cash, date.today())
    gm = next(f for f in figures if f.key == "gross_margin_today")

    assert gm.value == "unknown", f"an uncostable margin rendered as {gm.value!r}"
    assert gm.kind == "text", "an unknown margin must not be formatted as money"
    assert gm.value != 0, "G11: never a misleading default"
    assert caveat and "no purchase price" in caveat


def test_r12_2_collections_today_is_the_cash_actually_received_today(db, page):
    stamp = finance_today()
    cash = CashFlowService(db).cash_flow(date_from=stamp, date_to=stamp)
    assert cash.actual_in_minor > 0, "no receipt is dated today on the seed"
    assert _figure(page, "collections_today").value == cash.actual_in_minor


# --- R12.3: what needs attention --------------------------------------------


def test_r12_3_every_figure_the_requirement_names_is_on_the_page(page):
    """R12.3 lists ten things. Six are figures; the other four are the alert families."""
    keys = {f.key for f in page.attention}
    assert keys == {
        "receivables",
        "payables",
        "inventory_value",
        "purchase_orders_pending",
        "sales_orders_pending",
        "deliveries_due",
    }, f"R12.3's figures do not match what the page shows: {sorted(keys)}"


def test_r12_3_all_four_alert_families_fire_on_the_seeded_data(page):
    """Customer, vendor, low-stock and margin — G14 asks the demo to exercise each.

    A family that never fires on the seed is a family nobody has seen work, which is how
    an alert ships with its threshold the wrong way round.
    """
    keys = {a.key for a in page.alerts}
    assert "customers_overdue" in keys, "no customer alert — the collections list is empty"
    assert "arrivals_overdue" in keys, "no vendor alert — no purchase order is late"
    assert "low_stock" in keys, "no low-stock alert"
    assert any(k.startswith("margin_") for k in keys), "no margin alert from leakage"


def test_r12_3_the_receivable_and_payable_tiles_are_part_8s_ageing_totals(db, page):
    """Not a fourth definition of the receivable. Part 8 removed three of those."""
    ageing = AgeingService(db)
    ar = ageing.ar_ageing()
    ap = ageing.ap_ageing()
    assert ar.total_minor > 0 and ap.total_minor > 0, "nothing outstanding to compare"
    assert _figure(page, "receivables").value == ar.total_minor
    assert _figure(page, "payables").value == ap.total_minor


def test_r12_7_the_ageing_tiles_drill_to_their_own_side(page):
    """The one pair of links that can be swapped without anything else noticing.

    A wrong `side=` still renders and still returns 200, so the general drill-through test
    passes either way — this is the failure mode that "an equality assertion only tests
    what the data distinguishes" describes, in href form.
    """
    assert _figure(page, "receivables").href == "/finance/ageing?side=receivable"
    assert _figure(page, "payables").href == "/finance/ageing?side=payable"


def test_r12_3_the_inventory_tile_is_the_working_capital_snapshots_inventory(db, page):
    """One inventory-at-cost figure, so the tile and the position cannot disagree."""
    capital = CashFlowService(db).working_capital()
    assert capital.inventory_minor > 0
    assert _figure(page, "inventory_value").value == capital.inventory_minor


def test_r12_3_deliveries_due_excludes_orders_nobody_promised_a_date_for(db, page):
    """R5.7's rule, not re-decided here: an unpromised order is not due.

    Treating "we do not know" as "arriving now" is how a calendar starts lying, and the
    seed has such an order — so this is a real exclusion, not a hypothetical one.
    """
    from app.modules.procurement.recommend import ProcurementCalendarService

    arrivals = ProcurementCalendarService(db).arrivals()
    unpromised = [a for a in arrivals if a.bucket == "unpromised"]
    due = [a for a in arrivals if a.bucket in ("overdue", "today", "this_week")]
    assert _figure(page, "deliveries_due").value == len(due)
    assert _figure(page, "deliveries_due").value < len(arrivals) or not unpromised


# --- R12.4: position ---------------------------------------------------------


def test_r12_4_position_is_the_cash_flow_and_working_capital_snapshots(db, page):
    window_from, window_to = default_window()
    cash = CashFlowService(db).cash_flow(date_from=window_from, date_to=window_to)
    capital = CashFlowService(db).working_capital()

    assert _figure(page, "cash_net").value == cash.actual_net_minor
    assert _figure(page, "working_capital").value == capital.working_capital_minor
    assert cash.actual_net_minor != 0, "no cash moved in the window"


def test_r12_4_committed_cash_looks_forward_not_backward(db, page):
    """The tile says "next 90 days" and must mean it.

    `cash_flow`'s own `.committed` covers the same trailing window as its actuals, which is
    correct on a cash-flow report and wrong on a homepage — money whose due date has
    already passed is not what "committed, next 90 days" claims. Driving the real app is
    what caught the tile carrying the trailing figure under the forward label, so both
    halves are asserted: it equals the forward window, and it **differs** from the
    trailing one, which is what makes the first assertion mean anything.
    """
    from datetime import timedelta

    from app.modules.command_center.service import AHEAD_DAYS

    window_from, window_to = default_window()
    ahead_to = window_to + timedelta(days=AHEAD_DAYS)
    svc = CashFlowService(db)
    ahead = svc.committed(date_from=window_to, date_to=ahead_to)
    behind = svc.cash_flow(date_from=window_from, date_to=window_to).committed

    assert _figure(page, "cash_committed").value == ahead.net_minor
    assert ahead.net_minor != behind.net_minor, (
        "the forward and trailing committed figures are identical on this data, so this "
        "test cannot tell them apart — pick a window the seed distinguishes"
    )
    assert _figure(page, "cash_committed").href.endswith(ahead_to.isoformat()), (
        "the committed tile drills through to the trailing window"
    )


def test_r12_4_working_capital_still_says_it_excludes_cash_at_bank(page):
    """Part 8's caveat, carried to the homepage verbatim rather than re-worded.

    A "working capital" figure that silently omits cash reads as though it included it,
    and the homepage is where that would mislead most.
    """
    assert page.position_caveat
    assert "cash at bank" in page.position_caveat.lower()


# --- R12.5: recent activity -------------------------------------------------


def test_r12_5_recent_activity_is_the_activity_log_in_order(db, page):
    rows = ActivityService(db).recent(ACTIVITY_LIMIT)
    assert rows, "the seed wrote no activity"
    assert [e.summary for e in page.activity] == [r.summary for r in rows]
    assert [e.verb for e in page.activity] == [r.verb for r in rows]


# --- R12.6: quick actions ---------------------------------------------------


def test_r12_6_the_four_quick_actions_are_reachable_and_rendered(client):
    """Four, and every one of them actually resolves.

    Part 8's C1 shipped an href that was built and never rendered, and only driving the
    real app found it — so both halves are asserted here: the link is on the page, and
    the page it points at answers.
    """
    assert len(QUICK_ACTIONS) == 4, "R12.6 names four tasks, not more"
    text = client.get("/").text
    for action in QUICK_ACTIONS:
        assert _linked(text, action.href), f"{action.label} is not on the page"
        assert client.get(action.href).status_code == 200, f"{action.href} does not load"


# --- R12.7: every number drills through -------------------------------------


def test_r12_7_every_figure_is_rendered_as_a_link_that_loads(client, page):
    """Click every tile. Built AND rendered AND resolving — all three.

    The hrefs carry query strings the screens parse, so a 200 here also proves the
    receiving screen accepts what this page sends it.
    """
    text = client.get("/").text
    figures = page.happened + page.position + page.attention
    assert len(figures) >= 12, "too few figures for this to prove anything"
    for f in figures:
        assert _linked(text, f.href), f"{f.key} is not rendered as a link"
        assert client.get(f.href).status_code == 200, f"{f.key} links to {f.href}, which 404s"


def test_r12_7_a_figure_cannot_be_built_without_somewhere_to_go():
    """Enforced by the schema, so a tile added later cannot forget."""
    with pytest.raises(ValidationError, match="drill through"):
        Figure(key="x", label="X", kind="money", value=1, href="")


# --- R12.8: honest alerts ---------------------------------------------------


def test_r12_8_every_alert_states_trigger_threshold_and_linked_records(client, page):
    text = client.get("/").text
    assert page.alerts, "no alert to check"
    for alert in page.alerts:
        assert alert.trigger and alert.threshold, f"{alert.key} is missing its statement"
        assert alert.records, f"{alert.key} has nothing to click"
        assert _rendered(text, alert.trigger), f"{alert.key}'s trigger is not on screen"
        assert _rendered(text, alert.threshold), f"{alert.key}'s threshold is not on screen"
        for record in alert.records:
            assert record.href.startswith("/"), f"{alert.key} record has no link"
            assert _linked(text, record.href), f"{record.href} not rendered"


def test_r12_8_an_alert_with_nothing_to_click_cannot_be_constructed():
    """R12.8's "MUST be removed", enforced at the constructor rather than on review."""
    with pytest.raises(ValidationError, match="nothing to click"):
        Alert(
            key="empty",
            label="Empty",
            trigger="t",
            threshold="th",
            count=0,
            records=[],
            href="/finance",
        )


def test_r12_8_an_alert_may_not_understate_how_many_records_it_found(page):
    """A capped list says how many it is hiding; it never reports fewer than it found."""
    with pytest.raises(ValidationError, match="must not understate"):
        Alert(
            key="undercount",
            label="Undercount",
            trigger="t",
            threshold="th",
            count=1,
            records=[AlertRecord(label="a", href="/a"), AlertRecord(label="b", href="/b")],
            href="/finance",
        )
    capped = [a for a in page.alerts if a.hidden_count]
    assert capped, "the seed's 86 low-stock rows should exercise the cap"


def test_r12_8_the_margin_alerts_are_never_summed_into_one_figure(page):
    """C3 removed a tile that added a loss to a give-away. Do not put it back.

    Each leakage indicator arrives as its own alert with its own rule, because the two
    measure different quantities about overlapping lines.
    """
    margin_alerts = [a for a in page.alerts if a.key.startswith("margin_")]
    assert len(margin_alerts) >= 2, "the seed seeds two leakage offenders"
    assert len({a.threshold for a in margin_alerts}) == len(margin_alerts), (
        "two margin alerts share a rule — they have been merged"
    )


# --- R12.9: nothing decorative ----------------------------------------------


def test_r12_9_the_page_carries_no_decorative_chart(client):
    text = client.get("/").text
    for marker in ("<svg", "<canvas", "chart.js", "Chart("):
        assert marker not in text, f"the Command Center carries {marker!r}"


# --- R12.10 / G15 / G16: a projection that owns nothing ---------------------


def test_r12_10_the_projection_module_holds_no_query_and_no_model(page):
    """A namespace walk, not a text search.

    A source walk cannot tell a call from a mention — C3's failed on its own docstring —
    so this reads what the module actually imported. Nothing from SQLAlchemy's expression
    language and no ORM model may be in scope, which is the structural form of "this file
    computes nothing".
    """
    import app.modules.command_center.service as module

    for name, value in vars(module).items():
        if name.startswith("__"):
            continue
        origin = getattr(value, "__module__", "") or ""
        assert not origin.startswith("sqlalchemy.sql"), (
            f"{name} comes from SQLAlchemy's expression language — "
            "the Command Center must not build a query"
        )
        assert not origin.endswith(".models"), (
            f"{name} is an ORM model; the Command Center reads services, not tables"
        )


def test_g15_loading_the_page_writes_no_activity_row(client):
    """A read-only projection owns no entities and logs nothing (G15, R12.10).

    Counted over a real HTTP request, because `client.get` commits: a projection that
    logged would leave the row behind and this would catch it.
    """
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        before = session.scalar(select(func.count()).select_from(ActivityLog))
    assert client.get("/").status_code == 200
    with SessionLocal() as session:
        after = session.scalar(select(func.count()).select_from(ActivityLog))
    assert after == before, f"loading the homepage wrote {after - before} activity rows"


# --- R12.11 (the half C1 owns): the placeholder page is gone -----------------


def test_r12_11_the_placeholder_dashboard_page_and_template_are_deleted():
    """Two dashboards must not remain. The web half goes with C1 because it owned `/`.

    `app/modules/dashboard/` and its unused JSON route are C2's to remove; this asserts
    only what C1 replaced, so it cannot pass by describing work nobody did.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    assert not (root / "web" / "pages" / "dashboard.py").exists()
    assert not (root / "web" / "templates" / "dashboard").exists()
    assert (root / "web" / "pages" / "command_center.py").exists()


# --- R12.13: the fan-out cannot come back -----------------------------------


def test_r12_13_one_page_load_stays_inside_its_query_budget(db):
    """Counted, not grepped. The measurement itself is in `PROGRESS.md` (R12.12).

    What this does NOT cover: it is one count on one seeded dataset, so it proves the page
    does not read per row — it does not prove any individual query is fast.
    """
    _, statements = _count_queries(db, lambda: CommandCenterService(db).load())
    assert len(statements) <= QUERY_CEILING, (
        f"{len(statements)} queries for one page load, ceiling {QUERY_CEILING} — "
        "something on the homepage now reads per row"
    )


def test_r7_10_low_stock_reads_the_reorder_levels_once(db):
    """Part 5's method, guarded here because Part 9 is what measured it.

    `low_stock` called `stock()` — a grouped read of the whole catalogue — inside its loop
    over `states()`, so it cost 274 queries and 979 ms of a 344-query homepage. The levels
    are now read once. This counts statements rather than trusting the shape of the code.
    """
    rows, statements = _count_queries(db, lambda: InventoryHealthService(db).low_stock())
    assert len(rows) > 20, "too few low-stock rows for this to prove anything"
    assert len(statements) < 10, (
        f"{len(statements)} queries for {len(rows)} low-stock rows — this is per-row again"
    )


# --- the seed section (G14) --------------------------------------------------


def test_g14_the_seed_has_an_invoice_dated_today_settled_today(db):
    """Part 9's seed section, and the reason R12.2's tiles are not three zeros.

    Settled in full on purpose: it must not appear on an ageing screen, must not join the
    collections list, and must leave the receivable exactly as it was.
    """
    from app.modules.finance.models import Invoice

    stamp = date.today()
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.invoice_date == stamp,
            Invoice.sales_order_id.is_(None),
            Invoice.deleted_at.is_(None),
        )
    )
    assert invoice is not None, "no invoice dated today — R12.2's figures cannot be tested"
    assert invoice.status == "paid", "today's seeded invoice should be settled in full"
    assert len(invoice.lines) == 2, "the cost-unknown second line is missing"

    overdue_parties = {e.customer_id for e in AgeingService(db).collections()}
    assert invoice.customer_id not in overdue_parties, (
        "a settled invoice put its customer on the chase list"
    )
