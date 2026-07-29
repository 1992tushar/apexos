"""Part 10 C1 — the R13.1 audit's findings, made permanent (R13.1, R13.2, R13.6, R13.13).

C1 built no screen. It found one thing computed three ways and unified it, and these tests are
what stop it re-diverging.

**The unification.** `MarginService.gp` reads a missing purchase price as zero, so a product
nothing has ever been bought for reports its whole selling value as gross profit — a 100%
margin. Three places derived gross profit from it and only `MarginAnalysisService` checked
first. The check is now `MarginService.gp_costed`, and all three read it.

**The two divergences were not equally bad, and the tests say which was which.**
`CustomerHealthService.profitability` really was wrong: an uncosted line scored a customer
toward a 100% margin, worth up to 30 of the score's 100 points. `CashFlowService._cogs` was
right by coincidence — an uncosted line's `gp` equals its own subtotal, so it contributed zero
to `subtotal − gross` either way, and COGS is measurably unchanged. Overclaiming the second
would be the same sin as the number it fixes, so the test that covers it is labelled as an
unchanged-behaviour assertion.

**Why these tests assert disagreement, not just agreement.** R13.13 asks for a test proving
two paths return identical output for the same input, and this build has been burned by that
exact test shape: an equality assertion between two code paths only tests what the current
data distinguishes, and a no-op filter once passed one because the seed could not tell the
difference. So each test below either (a) asserts the two paths agree AND that the data
contains a case where an unfixed path would have disagreed, or (b) constructs that case.
"""
from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.modules.customers.health import (
    TARGET_MARGIN_PCT,
    WEIGHT_PROFITABILITY,
    CustomerHealthService,
)
from app.modules.finance.cash import CashFlowService, default_window
from app.modules.finance.margin import MarginAnalysisService
from app.modules.finance.repository import FinanceRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.service import MarginService
from app.modules.products.models import Product

APP = Path(__file__).resolve().parents[1] / "app"

#: The SKU `app/seed/finance.py` creates with a selling price and NO purchase price. The whole
#: unification turns on lines like this one existing, so a test that cannot find it is not
#: proving what it claims.
NO_COST_SKU = "SKU-NOBUY-01"


@pytest.fixture()
def uncosted_product(db) -> Product:
    product = db.scalar(
        select(Product).where(Product.sku_code == NO_COST_SKU, Product.deleted_at.is_(None))
    )
    assert product is not None, (
        f"{NO_COST_SKU} is missing from the seed — every test here would pass vacuously"
    )
    assert product.id not in MarginService(db).purchase_price_map(), (
        f"{NO_COST_SKU} has acquired a purchase price; it exists to have none"
    )
    return product


# --- R13.2: one place decides whether a line is costable ---------------------


def test_r13_2_gp_and_gp_costed_disagree_on_an_uncosted_line(db, uncosted_product):
    """The disagreement IS the finding. Without it nothing below means anything.

    `gp` returns the line's whole selling value — a 100% margin on a product nobody has ever
    bought. `gp_costed` returns None, which means "we do not know what this cost", and that is
    a different fact.
    """
    from types import SimpleNamespace

    line = SimpleNamespace(
        product_id=uncosted_product.id, qty=Decimal("3"), unit_price_minor=50_000
    )
    margin = MarginService(db)

    assert margin.gp(line) == 150_000, "gp should read the missing cost as zero — that is the bug"
    assert margin.gp_costed(line) is None, "gp_costed must refuse to guess"


def test_r13_2_gp_costed_matches_gp_wherever_the_cost_is_known(db):
    """The unification must not have changed the answer where the answer was right.

    Asserted over every seeded invoice line with a recorded purchase price, and with a floor,
    so it cannot pass on an empty set.
    """
    margin = MarginService(db)
    buy_prices = margin.purchase_price_map()
    repo = FinanceRepository(db)
    window_from, window_to = default_window()

    checked = 0
    for line in repo.invoice_lines_between(window_from, window_to):
        if line.product_id not in buy_prices:
            continue
        assert margin.gp_costed(line, buy_prices=buy_prices) == margin.gp(line)
        checked += 1
    assert checked >= 3, f"only {checked} costed lines in the window — too few to prove anything"


def test_r13_2_the_purchase_price_map_has_one_implementation(db):
    """`FinanceRepository.purchase_prices_by_product` is now a bare delegation.

    Part 8 built the query on the finance repository; the audit found three consumers in three
    modules, so it moved to `pricing`, which owns `PurchasePrice`.
    """
    from_finance = FinanceRepository(db).purchase_prices_by_product()
    from_pricing = PricingRepository(db).purchase_prices_by_product()
    from_margin = MarginService(db).purchase_price_map()

    assert from_finance == from_pricing == from_margin
    assert len(from_pricing) > 10, "the seed prices hundreds of products; this map looks wrong"


def test_r13_2_no_new_caller_of_gp_bypasses_the_costed_check():
    """The guard that keeps the unification unified.

    Parsed with `ast`, not grepped: a text search cannot tell a call from a mention, and this
    codebase has already had a source-walk test fail on its own docstring. Only `MarginService`
    itself may call `gp` — everything else goes through `gp_costed`, which is the one place
    that knows the difference between a zero cost and an unknown one.

    If this fails because you added a legitimate `gp` caller, the question to answer first is
    what your caller does when the product has no purchase price. If the answer is "reports a
    100% margin", it is a G11 violation, not a new sanctioned caller.
    """
    # Posix-form, because `relative_to` yields backslashes on Windows and the comparison
    # would silently never match — a source walk that finds nothing looks like a pass.
    allowed = {"modules/pricing/service.py"}
    offenders: list[str] = []

    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "gp"
            ):
                rel = path.relative_to(APP).as_posix()
                if rel not in allowed:
                    offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "these call MarginService.gp directly instead of gp_costed, so an uncosted line "
        f"reports a 100% margin: {offenders}"
    )


# --- R13.13: the three consumers return identical decisions ------------------


def test_r13_13_all_three_consumers_agree_on_which_lines_are_costable(db):
    """The identical-output test — on the DECISION, not just on a total.

    A total can agree by luck; the set of lines each path excluded cannot. `_cogs` and
    `MarginAnalysisService` see the same invoice lines over the same window, so their
    uncosted counts must match exactly, and both must match a recount done here through
    `gp_costed`.

    The structure is asserted too (R13.13's lesson): the count is compared, AND it is
    asserted non-zero, because `0 == 0 == 0` would pass on a seed with no uncosted line and
    prove nothing.
    """
    window_from, window_to = default_window()
    margin = MarginService(db)
    buy_prices = margin.purchase_price_map()

    recounted = sum(
        1
        for line in FinanceRepository(db).invoice_lines_between(window_from, window_to)
        if margin.gp_costed(line, buy_prices=buy_prices) is None
    )
    _cogs, from_cash = CashFlowService(db)._cogs(window_from, window_to)
    report = MarginAnalysisService(db).by_dimension(
        "product", date_from=window_from, date_to=window_to
    )

    assert recounted > 0, (
        "no uncosted line in the window — this test cannot distinguish the fixed code from "
        "the broken code, which is exactly the failure mode R13.13 warns about"
    )
    assert from_cash == recounted, f"_cogs counted {from_cash}, a recount found {recounted}"
    assert report.unknown_cost_lines == recounted, (
        f"the margin report counted {report.unknown_cost_lines}, a recount found {recounted}"
    )


def test_r13_13_cogs_excludes_the_uncosted_line_from_both_of_its_terms(db):
    """`cost = subtotal − gross` only holds if a dropped line leaves both terms.

    **This change moves no number on today's data, and the record says so.** The old code left
    the line in `subtotal` and gave it `gross == subtotal`, contributing exactly zero to cost —
    which is what excluding it contributes too. What the change buys is that the answer no
    longer depends on `gp` and the stored subtotal agreeing, and that the count is available to
    put on screen. The equality below is therefore the *unchanged-behaviour* assertion, not
    evidence of a fix.
    """
    window_from, window_to = default_window()
    cogs, uncosted = CashFlowService(db)._cogs(window_from, window_to)

    assert uncosted > 0, "the window holds no uncosted line; this proves nothing"
    assert cogs > 0, "cost of goods came out at zero, so DIO would report unknown"

    report = MarginAnalysisService(db).by_dimension(
        "product", date_from=window_from, date_to=window_to
    )
    # Both derive cost the same way from the same lines, so they must land on the same figure.
    assert cogs == report.cost_minor, (
        f"_cogs says {cogs}, the margin report says {report.cost_minor} — two cost definitions"
    )


def test_r13_10_the_dio_panel_names_the_lines_it_could_not_cost(db):
    """Excluding lines is defensible; not saying so is not (G11, R13.10)."""
    window_from, window_to = default_window()
    report = CashFlowService(db).cash_conversion_cycle(
        date_from=window_from, date_to=window_to
    )
    labels = [i.label for i in report.dio.inputs]
    assert "Invoice lines excluded (no purchase price)" in labels, (
        f"DIO does not disclose its excluded lines: {labels}"
    )


# --- R13.2 / R13.11: the customer health score no longer flatters ------------


def _order_on(db, customer, product, *, qty: str, unit_price_minor: int):
    """One confirmed sales order line, dated now, on a given product.

    Written through the ORM rather than the sell loop for the reason `app/seed/finance.py`
    sets out at length: the loop needs stock, reservations and a credit policy, and would
    leave an OPEN order behind on a customer other tests assert is quiet.
    """
    from app.modules.sales.models import SalesOrder, SalesOrderLine

    subtotal = int(Decimal(qty) * Decimal(unit_price_minor))
    order = SalesOrder(
        customer_id=customer.id,
        order_no=f"SO-R13-{uuid.uuid4().hex[:8]}",
        order_date=datetime.now(UTC).date(),
        status="confirmed",
        subtotal_minor=subtotal,
        tax_minor=0,
        total_minor=subtotal,
        business_unit_id=customer.business_unit_id,
    )
    order.lines.append(
        SalesOrderLine(
            product_id=product.id,
            qty=Decimal(qty),
            unit_price_minor=unit_price_minor,
            tax_rate_bps=0,
            line_subtotal_minor=subtotal,
            line_tax_minor=0,
            line_total_minor=subtotal,
            line_no=1,
        )
    )
    db.add(order)
    db.flush()
    return order


@pytest.fixture()
def lonely_customer(db):
    """A customer created HERE, so this test's orders are the only orders they have.

    Deliberately not a seeded customer. The first draft of this fixture took the last customer
    in code order on the theory that nothing else touched them — and it passed alone and failed
    in the full suite, because `client.post` COMMITS and some earlier test had left sales
    orders on them. A fixture whose isolation depends on what other tests happen to do is not
    isolated. Created through `CustomerService` and rolled back with the `db` fixture, so this
    one owes nothing to run order.
    """
    from app.modules.config.models import CustomerType
    from app.modules.customers.models import Customer
    from app.modules.customers.schemas import CustomerCreate
    from app.modules.customers.service import CustomerService

    ctype = db.scalar(select(CustomerType).where(CustomerType.deleted_at.is_(None)))
    created = CustomerService(db).create(
        CustomerCreate(
            name=f"Intel Co {uuid.uuid4().hex[:6]}",
            customer_type_id=ctype.id,
            city="Pune",
        ),
        actor_id=None,
    )
    # `create` returns the read schema; `_order_on` needs the ORM row for its business unit.
    customer = db.get(Customer, created.id)
    assert customer is not None and customer.business_unit_id is not None
    return customer


def test_r13_2_an_uncosted_line_no_longer_scores_a_customer_at_a_100_percent_margin(
    db, lonely_customer, uncosted_product
):
    """The behaviour change, asserted directly. This is what the unification bought.

    Before: `gp` returned the line's whole selling value, the margin came out at 100%, and the
    customer collected all 30 of `WEIGHT_PROFITABILITY`'s points for a number nobody measured.
    After: the line is excluded and counted, so with nothing else to go on the profitability
    input is MISSING and says why (R13.11) — never 0, never a flattering default.

    The seed cannot produce this case: `SKU-NOBUY-01` appears on invoices, and profitability
    reads sales-order lines. So the case is constructed.
    """
    svc = CustomerHealthService(db)
    before = svc.profitability(lonely_customer.id, as_of=datetime.now(UTC))
    assert before == (None, 0, 0, 0), (
        f"the fixture customer is not new — they already have order lines: {before}"
    )

    _order_on(db, lonely_customer, uncosted_product, qty="4", unit_price_minor=50_000)

    pct, revenue, gp, uncosted = svc.profitability(lonely_customer.id, as_of=datetime.now(UTC))
    assert uncosted == 1, "the uncosted line was not excluded"
    assert revenue == 0 and gp == 0, "an uncosted line contributed to revenue or profit"
    assert pct is None, f"margin came out at {pct}% on a line whose cost is unknown"


def test_r13_11_a_customer_with_only_uncosted_lines_says_why_rather_than_scoring_zero(
    db, lonely_customer, uncosted_product
):
    """G11/R13.11: the reason names the uncosted lines, and the input is missing, not zero.

    "Nothing invoiced yet" and "everything they bought has no purchase price recorded" are
    different facts, and only the second is something the founder can fix.
    """
    _order_on(db, lonely_customer, uncosted_product, qty="2", unit_price_minor=50_000)

    score = CustomerHealthService(db).score(lonely_customer.id, as_of=datetime.now(UTC))
    profitability = next(i for i in score.inputs if i.label == "Profitability")

    assert profitability.is_missing, "an unmeasurable margin was scored instead of skipped"
    assert "purchase price" in (profitability.missing_reason or ""), (
        f"the reason does not name the real cause: {profitability.missing_reason!r}"
    )
    assert "0" not in (profitability.value or "no measurable margin"), (
        "a zero leaked into the rendered value"
    )
    # The score itself must still be computable from the inputs that DO exist — the weights
    # renormalise, which is Part 7's behaviour and not something this change may break.
    assert score.is_known, "excluding one input must not make the whole score unknown"


def test_r13_2_a_costed_line_still_scores_the_customer_normally(
    db, lonely_customer
):
    """The other direction: the fix must not have broken the path that was working.

    Uses a product priced on BOTH sides, so a well-priced customer still earns their points.
    """
    margin = MarginService(db)
    buy_prices = margin.purchase_price_map()
    priced = db.scalars(
        select(Product).where(Product.deleted_at.is_(None), Product.id.in_(buy_prices.keys()))
    ).first()
    assert priced is not None, "no product has a purchase price; the seed is wrong"

    buy = buy_prices[priced.id]
    _order_on(db, lonely_customer, priced, qty="5", unit_price_minor=buy * 3)

    pct, revenue, gp, uncosted = CustomerHealthService(db).profitability(
        lonely_customer.id, as_of=datetime.now(UTC)
    )
    assert uncosted == 0
    assert revenue > 0 and gp > 0
    assert pct is not None and pct > TARGET_MARGIN_PCT, (
        f"a line sold at 3× its buy price scored {pct}%"
    )


def test_r13_2_a_mixed_customer_reports_the_margin_it_could_measure_and_names_the_rest(
    db, lonely_customer, uncosted_product
):
    """The interesting middle case: some lines costable, some not.

    The margin is real — computed over the costed lines — and the screen says how many it left
    out. Averaging over fewer lines than the customer bought is defensible; not saying so is
    not.
    """
    margin = MarginService(db)
    buy_prices = margin.purchase_price_map()
    priced = db.scalars(
        select(Product).where(Product.deleted_at.is_(None), Product.id.in_(buy_prices.keys()))
    ).first()
    buy = buy_prices[priced.id]

    _order_on(db, lonely_customer, priced, qty="5", unit_price_minor=buy * 3)
    _order_on(db, lonely_customer, uncosted_product, qty="9", unit_price_minor=50_000)

    svc = CustomerHealthService(db)
    pct, revenue, gp, uncosted = svc.profitability(lonely_customer.id, as_of=datetime.now(UTC))
    assert uncosted == 1
    assert pct is not None and revenue > 0

    # The excluded line is nine units at ₹500 — far bigger than the costed one. If it had
    # leaked into the arithmetic the margin would be dragged toward 100%.
    assert pct < Decimal("100"), f"the uncosted line reached the average: {pct}%"

    score = svc.score(lonely_customer.id, as_of=datetime.now(UTC))
    profitability = next(i for i in score.inputs if i.label == "Profitability")
    assert not profitability.is_missing
    assert "1 line with no purchase price" in profitability.value, (
        f"the exclusion is not disclosed: {profitability.value!r}"
    )
    assert str(WEIGHT_PROFITABILITY) in score.formula


# --- R13.6 / R13.1: what the audit found ALREADY unified ---------------------


def test_r13_6_there_is_still_exactly_one_recommendation_engine():
    """R13.6 was already satisfied before Part 10; the audit records it rather than rebuilds it.

    `InventoryHealthService.reorder_suggestions` is a bare delegation to
    `RecommendationService.recommend`. Asserted with `ast` so a second engine cannot appear
    under a docstring's cover.
    """
    definitions = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "recommend":
                definitions.append(f"{path.relative_to(APP).as_posix()}:{node.lineno}")

    assert len(definitions) == 1, f"more than one recommendation engine exists: {definitions}"
    assert definitions[0].startswith("modules/procurement/recommend.py"), definitions


def test_r13_6_reorder_suggestions_returns_part_4s_engine_output_unchanged(db):
    """The identical-output half of R13.6/R13.13, with the structure asserted too.

    Part 5 already has `test_r7_13_...`; this one additionally checks the SHAPE, because an
    equality of two lists can hold while the objects inside differ in a field neither list
    happens to compare.
    """
    from app.modules.inventory.health import InventoryHealthService
    from app.modules.procurement.recommend import RecommendationService

    direct = RecommendationService(db).recommend(limit=5)
    through_health = InventoryHealthService(db).reorder_suggestions(limit=5)

    assert direct, "no recommendations on the seed — this test proves nothing"
    assert len(direct) == len(through_health)
    for a, b in zip(direct, through_health, strict=True):
        assert a.product_id == b.product_id
        assert a.qty == b.qty
        assert a.sentence == b.sentence
        assert type(a) is type(b), "the delegation is re-wrapping the result"


def test_r13_1_g11_has_exactly_one_explained_implementation():
    """The audit's other "already done": G11 is `Explained`, defined once in `app/db/explain.py`.

    R13.1 had this unification scheduled for Part 10. It was built in Part 4 and adopted by
    Parts 5–9, so the deliverable here is recording it — and a guard, because a second
    explanation shape is the most likely way this part would regress.
    """
    definitions = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in ("Explained", "Input"):
                definitions.append(f"{path.relative_to(APP).as_posix()}:{node.name}")

    assert sorted(definitions) == ["db/explain.py:Explained", "db/explain.py:Input"], (
        f"a second explained-number shape exists: {definitions}"
    )


def test_r13_2_the_lead_time_in_recommendations_is_vendor_intels_own(db):
    """`recommend.py:_lead_time` is a memoising delegation, not a second measurement.

    Recorded because it LOOKS like a duplication — two `-> Explained` lead-time methods — and
    the audit's job is to tell those apart from the real thing.
    """
    from app.modules.procurement.recommend import RecommendationService
    from app.modules.suppliers.vendor import VendorIntelService

    supplier_id = None
    svc = RecommendationService(db)
    for rec in svc.recommend(limit=10):
        if rec.supplier_id is not None and rec.lead_time is not None:
            supplier_id = rec.supplier_id
            from_recommendation = rec.lead_time
            break
    assert supplier_id is not None, "no recommendation names a supplier with a lead time"

    direct = VendorIntelService(db).lead_time(supplier_id)
    assert from_recommendation.value == direct.value
    assert from_recommendation.formula == direct.formula
    assert from_recommendation.window == direct.window


# --- what the audit found and deliberately did NOT unify --------------------


def test_r13_1_low_stock_and_reorder_suggestions_measure_different_things(db):
    """Recorded as a deliberate difference, NOT unified — and the reason is asserted.

    `InventoryHealthService.low_stock` fires on **available** — on hand minus reserved —
    because stock already committed to an order cannot cover a new one (R7.10).
    `RecommendationService` computes a shortfall against **on hand plus on order**, because a
    purchase order already placed must not be placed twice (R5.9).

    So they can legitimately disagree about whether a product is "short", and R13.2 does not
    apply: two things computed differently are not the same thing computed twice. The audit's
    job is to tell those apart, and this test exists so a later session reads the reasoning
    before "fixing" the discrepancy.

    Asserted on the SHAPES rather than on the seed's row counts: each carries the term the
    other does not, which is the claim, and it holds whatever the data happens to contain.
    """
    from app.modules.inventory.health import InventoryHealthService
    from app.modules.procurement.recommend import RecommendationService

    low = InventoryHealthService(db).low_stock()
    recs = RecommendationService(db).recommend()
    assert low, "no low-stock rows on the seed"
    assert recs, "no recommendations on the seed"

    low_fields = set(low[0].model_fields_set) | set(type(low[0]).model_fields)
    assert {"available", "reserved"} <= low_fields, (
        f"low_stock no longer carries the reserved/available basis R7.10 fixed it on: {low_fields}"
    )
    assert "on_order" not in low_fields, "low_stock has acquired an on-order term"

    rec_fields = set(recs[0].__dataclass_fields__)
    assert "on_order" in rec_fields, (
        f"the recommendation no longer subtracts what is already on order: {rec_fields}"
    )
    assert "reserved" not in rec_fields, "the recommendation has acquired a reserved term"


# --- the fan-out the audit measured (recorded for Part 11) ------------------


def test_r13_2_gp_costed_does_not_query_per_line_when_given_the_map(db):
    """Passing `purchase_price_map()` is what makes the unification cheap.

    `gp` itself still resolves a purchase price per call, so a caller that loops without the
    map pays one query per line. Recorded here as a measurement rather than fixed: Part 11
    owns performance, and Part 9's `low_stock` finding is the precedent for how this is
    counted rather than grepped.
    """
    from sqlalchemy import event

    window_from, window_to = default_window()
    lines = FinanceRepository(db).invoice_lines_between(window_from, window_to)
    assert len(lines) >= 5, "too few lines to tell a per-line read from a fixed cost"

    margin = MarginService(db)
    buy_prices = margin.purchase_price_map()

    statements: list[str] = []

    def record(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        for line in lines:
            margin.gp_costed(line, buy_prices=buy_prices)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)

    # One query per COSTED line (inside `gp`), and none for the uncosted ones, which return
    # before touching the database. The map itself was fetched outside the listener.
    costed = sum(1 for line in lines if line.product_id in buy_prices)
    assert len(statements) <= costed, (
        f"{len(statements)} queries for {len(lines)} lines, {costed} of them costed — "
        "gp_costed is querying more than gp does"
    )


def test_r13_12_no_ml_or_llm_dependency_reaches_these_numbers():
    """G12/R13.12, asserted on the dependency list rather than by eye."""
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    for banned in (
        "scikit-learn", "sklearn", "tensorflow", "torch", "xgboost", "lightgbm",
        "openai", "anthropic", "transformers", "langchain",
    ):
        assert banned not in pyproject, f"{banned} is a dependency; G12 forbids it"


def test_r13_1_the_unified_decision_is_reachable_from_every_consumer(db):
    """A belt-and-braces check that the three consumers really do share one code path.

    Monkeypatching `gp_costed` to refuse everything must make all three report zero costable
    lines. If one of them still finds costed lines, it is not going through the unification.
    """
    window_from, window_to = default_window()
    original = MarginService.gp_costed
    MarginService.gp_costed = lambda self, line, *, buy_prices=None: None
    try:
        cogs, uncosted = CashFlowService(db)._cogs(window_from, window_to)
        report = MarginAnalysisService(db).by_dimension(
            "product", date_from=window_from, date_to=window_to
        )
        leakage = MarginAnalysisService(db).leakage(date_from=window_from, date_to=window_to)
    finally:
        MarginService.gp_costed = original

    assert cogs == 0, "cost of goods survived a gp_costed that refuses every line"
    assert uncosted > 0
    assert report.revenue_minor == 0 and report.gp_minor == 0, (
        "the margin report still found costable lines"
    )
    below = next((i for i in leakage.indicators if i.key == "sold_below_cost"), None)
    assert below is not None and not below.records, (
        "the below-cost indicator still fired, so it is not using gp_costed"
    )


def test_r13_2_customer_health_also_routes_through_the_one_decision(db, lonely_customer):
    """The same monkeypatch aimed at the fourth consumer, which reads sales-order lines."""
    margin_map = MarginService(db).purchase_price_map()
    priced = db.scalars(
        select(Product).where(Product.deleted_at.is_(None), Product.id.in_(margin_map.keys()))
    ).first()
    _order_on(db, lonely_customer, priced, qty="5", unit_price_minor=margin_map[priced.id] * 2)

    svc = CustomerHealthService(db)
    assert svc.profitability(lonely_customer.id, as_of=datetime.now(UTC))[0] is not None

    original = MarginService.gp_costed
    MarginService.gp_costed = lambda self, line, *, buy_prices=None: None
    try:
        pct, revenue, gp, uncosted = svc.profitability(
            lonely_customer.id, as_of=datetime.now(UTC)
        )
    finally:
        MarginService.gp_costed = original

    assert pct is None and revenue == 0 and gp == 0, (
        "profitability found a margin without gp_costed, so it has its own cost path"
    )
    assert uncosted >= 1


def test_r13_1_the_window_helpers_are_shared_not_reimplemented():
    """`default_window` and `month_starts` have one definition each (R13.2, spot-check)."""
    names = {"default_window": [], "month_starts": []}
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in names:
                names[node.name].append(path.relative_to(APP).as_posix())

    for name, where in names.items():
        assert len(where) == 1, f"{name} is defined {len(where)} times: {where}"
        assert where[0] == "modules/finance/cash.py", f"{name} moved to {where}"


#: The ONE table allowed to hold score columns, and the reason.
#:
#: `supplier_evaluation` is the founder's own periodic scorecard — quality, price and
#: reliability, entered by hand on a 1–5 scale. That is **recorded input**, not a derived
#: quantity, and G7 is about derived quantities. `VendorIntelService.score` consumes it at 60%
#: weight alongside the measured on-time rate; storing what somebody typed is the only way it
#: can be an input at all.
#:
#: Every other score in the product — customer health, vendor reliability, inventory health —
#: is recomputed per read and must stay that way.
_RECORDED_SCORE_TABLE = "supplier_evaluation"


def test_r13_1_no_derived_score_is_stored_in_any_table():
    """G7/G15 across all three scores: derived at read time, no column, no cache table.

    Part 10 consolidates scores, and the way that goes wrong is a `score` column added "for
    performance" — after which two screens can disagree about a customer's health depending on
    when each was last written. Asserted against the mapped columns of every table, so a new
    model cannot introduce one quietly.

    The distinction this encodes is worth stating: a score somebody **typed** is data, and a
    score the system **worked out** is not. Only the first may be stored.
    """
    from app.db.metadata import Base, import_all_models

    import_all_models()

    offenders = []
    for table in Base.metadata.tables.values():
        if table.name == _RECORDED_SCORE_TABLE:
            continue
        for column in table.columns:
            lowered = column.name.lower()
            if lowered.endswith("_score") or lowered in ("score", "health_score", "rating"):
                offenders.append(f"{table.name}.{column.name}")
    assert not offenders, (
        "a DERIVED score has been stored, so two screens can now disagree about it: "
        f"{offenders}"
    )


def test_r13_1_the_one_stored_scorecard_is_still_the_hand_entered_one(db):
    """The exemption above must not become a loophole.

    If `supplier_evaluation` ever stops being a hand-entered scorecard, the exemption is
    wrong. Its columns are asserted here so that change cannot pass unnoticed.
    """
    from app.modules.suppliers.models import SupplierEvaluation

    columns = {c.name for c in SupplierEvaluation.__table__.columns}
    assert {"quality_score", "price_score", "reliability_score", "overall_score"} <= columns
    assert "evaluated_on" in columns, (
        "the scorecard has lost its evaluation date, which is what makes it a recorded "
        "judgement rather than a cached computation"
    )


def test_r13_1_the_audit_list_is_recorded_in_progress_md():
    """R13.1 says the list is a deliverable in `PROGRESS.md`. This checks it is there.

    Not a proxy for the list being GOOD — a human reads it for that — but it does stop the
    deliverable being quietly dropped when the block is next rewritten.
    """
    progress = (Path(__file__).resolve().parents[3] / "PROGRESS.md").read_text(encoding="utf-8")
    assert "R13.1" in progress, "the audit is not referenced in PROGRESS.md"
    for expected in ("VendorIntelService", "CustomerHealthService", "InventoryHealthService"):
        assert expected in progress, f"the audit list does not mention {expected}"
