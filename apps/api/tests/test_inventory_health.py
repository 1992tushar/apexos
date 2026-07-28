"""Part 5 C3b — inventory health: ABC, dead stock, fast/slow, low stock, reorder.

R7.7–R7.11 and R7.13. The classification tests build their own product with a known sales
history rather than asserting against the seed's totals, so a later part adding a sale cannot
break an arithmetic test. The seed's own shape is asserted separately as R7.14's
"the demo data is non-trivial" check.

`as_of` is injectable throughout, so the boundary tests sit exactly on the edge instead of
depending on when the suite runs.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.inventory.health import InventoryHealthService, abc_class_for
from app.modules.inventory.schemas import (
    ABC_CLASSES,
    DEAD_STOCK_DAYS,
    MOVEMENT_WINDOW_DAYS,
    SLOW_MOVER_MAX_PER_MONTH,
)
from app.modules.inventory.service import InventoryService

NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


@pytest.fixture()
def warehouse(db):
    from app.modules.config.models import Warehouse

    return db.scalar(select(Warehouse).where(Warehouse.deleted_at.is_(None)))


@pytest.fixture()
def fresh_product(db):
    """A product with no movements, so this file's arithmetic starts from zero."""
    from app.modules.products.models import Product

    template = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    product = Product(
        sku_code=f"HLT-{uuid.uuid4().hex[:8].upper()}",
        name="Health test SKU",
        business_unit_id=template.business_unit_id,
        category_id=template.category_id,
        brand_id=template.brand_id,
        uom_id=template.uom_id,
        procurement_model_id=template.procurement_model_id,
        reorder_level=Decimal("0"),
        status=template.status,
    )
    db.add(product)
    db.flush()
    return product


def _buy(db, product, warehouse, qty: str, cost_minor: int = 10000, days_ago: int = 400):
    InventoryService(db).record_movement(
        product_id=product.id, warehouse_id=warehouse.id, qty_delta=Decimal(qty),
        reason="PURCHASE", unit_cost_minor=cost_minor,
        occurred_at=NOW - timedelta(days=days_ago),
    )


def _sell(db, product, warehouse, qty: str, *, days_ago: int):
    InventoryService(db).record_movement(
        product_id=product.id, warehouse_id=warehouse.id, qty_delta=-Decimal(qty),
        reason="SALE", occurred_at=NOW - timedelta(days=days_ago),
    )


# --- R7.7: ABC boundaries ----------------------------------------------------


def test_r7_7_abc_class_boundaries_are_inclusive_at_the_upper_bound(db):
    """R7.7 requires the class boundaries to be STATED. This is the definition."""
    assert abc_class_for(Decimal("0")) == "A"
    assert abc_class_for(Decimal("0.80")) == "A", "exactly 80% must be class A"
    assert abc_class_for(Decimal("0.8001")) == "B"
    assert abc_class_for(Decimal("0.95")) == "B", "exactly 95% must be class B"
    assert abc_class_for(Decimal("0.9501")) == "C"
    assert abc_class_for(Decimal("1")) == "C"
    # The last class must reach 1.0, or the tail of the ranking falls out of every class.
    assert ABC_CLASSES[-1][1] == Decimal("1.00")


def test_r7_7_abc_ranks_by_value_sold_not_by_quantity(db, warehouse):
    """A cheap high-volume line must not outrank an expensive low-volume one.

    That is the whole point of ABC: it is about where the money is, not the units.
    """
    from app.modules.products.models import Product

    template = db.scalar(select(Product).where(Product.deleted_at.is_(None)))

    def make(sku: str):
        p = Product(
            sku_code=sku, name=sku, business_unit_id=template.business_unit_id,
            category_id=template.category_id, brand_id=template.brand_id,
            uom_id=template.uom_id, procurement_model_id=template.procurement_model_id,
            reorder_level=Decimal("0"), status=template.status,
        )
        db.add(p)
        db.flush()
        return p

    cheap = make(f"ABC-CHEAP-{uuid.uuid4().hex[:4].upper()}")
    dear = make(f"ABC-DEAR-{uuid.uuid4().hex[:4].upper()}")
    # 100 units at 1.00 = 100.00 sold; 10 units at 500.00 = 5000.00 sold.
    _buy(db, cheap, warehouse, "200", cost_minor=100)
    _buy(db, dear, warehouse, "50", cost_minor=50000)
    _sell(db, cheap, warehouse, "100", days_ago=30)
    _sell(db, dear, warehouse, "10", days_ago=30)

    rows = {r.product_id: r for r in InventoryHealthService(db).abc(as_of=NOW)}
    assert rows[dear.id].value_minor > rows[cheap.id].value_minor
    # And the ranking puts the expensive one ahead despite selling a tenth of the units.
    ordered = [r.product_id for r in InventoryHealthService(db).abc(as_of=NOW)]
    assert ordered.index(dear.id) < ordered.index(cheap.id)


def test_r7_7_only_sales_count_as_consumption(db, fresh_product, warehouse):
    """A transfer, putaway, adjustment or count must not make a product look like it sells."""
    _buy(db, fresh_product, warehouse, "100")
    inventory = InventoryService(db)
    for reason in ("TRANSFER", "PUTAWAY", "ADJUSTMENT", "COUNT"):
        inventory.record_movement(
            product_id=fresh_product.id, warehouse_id=warehouse.id,
            qty_delta=-Decimal("10"), reason=reason, occurred_at=NOW - timedelta(days=10),
        )

    row = next(
        r for r in InventoryHealthService(db).abc(as_of=NOW)
        if r.product_id == fresh_product.id
    )
    assert row.qty_consumed == Decimal(0), "a non-sale was counted as demand"
    assert row.value_minor == 0
    assert row.abc_class == "C"


def test_r7_7_a_product_that_sold_nothing_is_classified_c_not_dropped(db, fresh_product, warehouse):
    _buy(db, fresh_product, warehouse, "50")
    rows = InventoryHealthService(db).abc(as_of=NOW)
    row = next((r for r in rows if r.product_id == fresh_product.id), None)
    assert row is not None, "a product with no sales fell off the ABC report entirely"
    assert row.abc_class == "C"


def test_r7_7_the_abc_explanation_states_its_boundaries(db):
    svc = InventoryHealthService(db)
    rows = svc.abc(as_of=NOW)
    total = sum(r.value_minor for r in rows)
    explained = svc.abc_explained(rows[0], total_minor=total)

    assert explained.is_known
    assert "80%" in explained.formula and "95%" in explained.formula
    assert "inclusive" in explained.formula
    assert str(MOVEMENT_WINDOW_DAYS) in explained.window


# --- R7.8: dead stock --------------------------------------------------------


def test_r7_8_the_dead_stock_boundary_is_strictly_outside_the_window(db, fresh_product, warehouse):
    """Exactly `DEAD_STOCK_DAYS` since the last sale is NOT yet dead; one day more is."""
    _buy(db, fresh_product, warehouse, "100")
    _sell(db, fresh_product, warehouse, "10", days_ago=DEAD_STOCK_DAYS)

    svc = InventoryHealthService(db)
    on_the_edge = {r.product_id for r in svc.dead_stock(as_of=NOW)}
    assert fresh_product.id not in on_the_edge, (
        f"a sale exactly {DEAD_STOCK_DAYS} days ago must not count as dead"
    )

    # One day past the edge.
    just_over = NOW + timedelta(days=1)
    assert fresh_product.id in {r.product_id for r in svc.dead_stock(as_of=just_over)}


def test_r7_8_dead_stock_measures_the_last_sale_not_the_last_movement(db, fresh_product, warehouse):
    """A cycle count last week must not make year-old stock look alive.

    This is the failure the radar exists to catch, and the reason it reads
    `last_consumption_at` rather than `last_movement_at`.
    """
    _buy(db, fresh_product, warehouse, "100")
    _sell(db, fresh_product, warehouse, "5", days_ago=DEAD_STOCK_DAYS + 200)
    # Something moved yesterday — but it was not a sale.
    InventoryService(db).record_movement(
        product_id=fresh_product.id, warehouse_id=warehouse.id,
        qty_delta=Decimal("1"), reason="COUNT", occurred_at=NOW - timedelta(days=1),
    )

    dead = {r.product_id for r in InventoryHealthService(db).dead_stock(as_of=NOW)}
    assert fresh_product.id in dead, "a recent count made dead stock look alive"


def test_r7_8_a_product_that_never_sold_is_the_deadest_case(db, fresh_product, warehouse):
    _buy(db, fresh_product, warehouse, "40")
    row = next(
        r for r in InventoryHealthService(db).dead_stock(as_of=NOW)
        if r.product_id == fresh_product.id
    )
    assert row.never_sold
    assert row.days_since_sale is None
    assert row.qty_on_hand == Decimal("40")


def test_r7_8_a_product_with_no_stock_is_not_dead_stock(db, fresh_product, warehouse):
    """Nothing on hand is not dead capital — it is just discontinued."""
    _buy(db, fresh_product, warehouse, "10")
    _sell(db, fresh_product, warehouse, "10", days_ago=DEAD_STOCK_DAYS + 100)

    dead = {r.product_id for r in InventoryHealthService(db).dead_stock(as_of=NOW)}
    assert fresh_product.id not in dead


def test_r7_8_the_dead_stock_explanation_states_its_window(db, fresh_product, warehouse):
    _buy(db, fresh_product, warehouse, "40")
    svc = InventoryHealthService(db)
    row = next(
        r for r in svc.dead_stock(as_of=NOW) if r.product_id == fresh_product.id
    )
    explained = svc.dead_stock_explained(row)

    assert str(DEAD_STOCK_DAYS) in explained.formula
    assert str(DEAD_STOCK_DAYS) in explained.window
    assert "last SALE" in explained.caveat


# --- R7.9: fast and slow -----------------------------------------------------


def test_r7_9_the_fast_slow_threshold_is_stated_and_boundary_correct(db, fresh_product, warehouse):
    """At the threshold is SLOW; above it is fast."""
    _buy(db, fresh_product, warehouse, "500")
    # Sell exactly SLOW_MOVER_MAX_PER_MONTH per month across the window.
    months = MOVEMENT_WINDOW_DAYS // 30
    for month in range(months):
        _sell(db, fresh_product, warehouse, str(SLOW_MOVER_MAX_PER_MONTH),
              days_ago=30 * month + 1)

    row = next(
        r for r in InventoryHealthService(db).movement_rates(as_of=NOW)
        if r.product_id == fresh_product.id
    )
    assert row.per_month <= Decimal(SLOW_MOVER_MAX_PER_MONTH) + Decimal("0.2")
    assert not row.is_fast, "at the threshold must be slow, not fast"
    assert row.label == "slow"
    # The numbers behind the rate are on the row, so the screen can show them (R7.9).
    assert row.movements == months
    assert row.window_days == MOVEMENT_WINDOW_DAYS


def test_r7_9_a_high_volume_product_is_classified_fast(db, fresh_product, warehouse):
    _buy(db, fresh_product, warehouse, "1000")
    for month in range(12):
        _sell(db, fresh_product, warehouse, "40", days_ago=30 * month + 1)

    row = next(
        r for r in InventoryHealthService(db).movement_rates(as_of=NOW)
        if r.product_id == fresh_product.id
    )
    assert row.is_fast
    assert row.per_month > Decimal(SLOW_MOVER_MAX_PER_MONTH)


# --- R7.10: low stock --------------------------------------------------------


def test_r7_10_low_stock_triggers_on_available_not_on_hand(db, fresh_product, warehouse):
    """Stock already committed cannot cover a new order, so it must not count."""
    from app.modules.inventory.schemas import ReservationCreate
    from app.modules.inventory.service import ReservationService

    _buy(db, fresh_product, warehouse, "100")
    fresh_product.reorder_level = Decimal("50")
    db.flush()

    svc = InventoryHealthService(db)
    assert fresh_product.id not in {r.product_id for r in svc.low_stock()}

    # Commit 60, leaving 40 available against a level of 50.
    ReservationService(db).reserve(
        ReservationCreate(
            product_id=fresh_product.id, warehouse_id=warehouse.id, qty=Decimal("60")
        ),
        actor_id=None,
    )
    row = next(r for r in svc.low_stock() if r.product_id == fresh_product.id)
    assert row.on_hand == Decimal("100"), "on hand did not change — only availability did"
    assert row.available == Decimal("40")
    assert row.shortfall == Decimal("10")


def test_r7_10_the_low_stock_explanation_names_the_trigger_and_links_the_record(
    db, fresh_product, warehouse
):
    _buy(db, fresh_product, warehouse, "10")
    fresh_product.reorder_level = Decimal("50")
    db.flush()

    svc = InventoryHealthService(db)
    row = next(r for r in svc.low_stock() if r.product_id == fresh_product.id)
    explained = svc.low_stock_explained(row)

    assert "reorder level" in explained.formula
    labels = {i.label for i in explained.inputs}
    assert {"On hand", "Reserved", "Available"} <= labels
    assert any("trigger" in i.label for i in explained.inputs)
    # R7.10 requires the affected records to be LINKED, not just named.
    assert explained.records
    assert explained.records[0].href == f"/products/{fresh_product.id}"


# --- R7.11 / R7.13: one recommendation engine --------------------------------


def test_r7_13_the_reorder_suggestion_is_identical_to_part_4s_engine(db):
    """R7.13 — the same question must get the same answer on both screens.

    Not "similar": identical. A filter or a re-sort here is how two screens start
    disagreeing about what to buy, which is what R5.9 exists to prevent.
    """
    from app.modules.procurement.recommend import RecommendationService

    engine = RecommendationService(db).recommend(limit=10)
    health = InventoryHealthService(db).reorder_suggestions(limit=10)

    assert health == engine, "the health screen reshaped the engine's answer"
    assert [r.product_id for r in health] == [r.product_id for r in engine]
    assert [r.qty for r in health] == [r.qty for r in engine]
    assert [r.sentence for r in health] == [r.sentence for r in engine]


def test_r7_13_the_passthrough_holds_for_a_single_product_too(db):
    from app.modules.procurement.recommend import RecommendationService

    engine_all = RecommendationService(db).recommend()
    assert engine_all, "nothing to reorder — the seed's reorder cases regressed"
    product_id = engine_all[0].product_id

    assert InventoryHealthService(db).reorder_suggestions(
        product_id=product_id
    ) == RecommendationService(db).recommend(product_id=product_id)


def test_r7_11_health_does_not_define_its_own_recommendation(db):
    """Part 4's own source walk already forbids a second `def recommend` anywhere in app/.
    This asserts the narrower thing: health DELEGATES rather than computing."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "app" / "modules" / "inventory" / "health.py"
    ).read_text(encoding="utf-8")

    assert "RecommendationService" in src, "health must read Part 4's engine"
    # No reorder arithmetic of its own: the engine owns reorder_level/on_order/MOQ.
    for forbidden in ("reorder_level -", "on_order", "moq"):
        assert forbidden not in src, f"health appears to recompute reorder logic: {forbidden}"


def test_r7_11_the_delegation_is_structurally_a_passthrough(db):
    """R7.13's equality check can pass VACUOUSLY, and a mutation proved it does.

    Inserting `[r for r in rows if r.qty > 0]` into the delegation changed nothing on the
    seeded data — every recommendation currently has a positive qty — so comparing outputs
    could not see it. A filter that is a no-op today is still a divergence waiting to
    happen the first time the data changes. This inspects the shape of the delegation
    instead: one statement, returning the engine's call directly.
    """
    import inspect

    from app.modules.inventory.health import InventoryHealthService

    source = inspect.getsource(InventoryHealthService.reorder_suggestions)
    body = [
        line.strip()
        for line in source.splitlines()
        if line.strip()
        and not line.strip().startswith(("#", '"""', "'''", "def ", "from ", "import "))
    ]
    # Strip the docstring block.
    body = [ln for ln in body if not ln.startswith(("*", "`", "R7.13", "moment", "deliberately"))]
    returns = [ln for ln in body if ln.startswith("return")]

    assert len(returns) == 1, f"expected one return, found {returns}"
    assert returns[0].startswith("return RecommendationService(self.db).recommend("), (
        f"the delegation is not a direct passthrough: {returns[0]}"
    )
    assert not any(ln.startswith(("if ", "for ", "while ")) for ln in body), (
        "the delegation filters or reshapes the engine's answer"
    )


# --- R7.14: the demo data the health screens need ----------------------------


def test_r7_14_the_seed_produces_more_than_one_abc_class(db):
    """A seed where every product lands in C makes R7.7's screen meaningless."""
    rows = InventoryHealthService(db).abc()
    classes = {r.abc_class for r in rows}
    assert len(classes) >= 3, f"ABC collapsed to {classes} — the demand seed regressed"
    assert sum(1 for r in rows if r.abc_class == "A") >= 2


def test_r7_14_the_seed_has_a_fast_mover_and_dead_stock(db):
    svc = InventoryHealthService(db)
    assert any(r.is_fast for r in svc.movement_rates()), "no fast mover in the seed"
    assert svc.dead_stock(), "no dead stock in the seed"


def test_r7_14_the_seeded_demand_never_drove_a_balance_negative(db):
    """A seed bug every downstream figure would inherit."""
    negatives = [r for r in InventoryService(db).stock() if r.qty_on_hand < 0]
    assert not negatives, f"negative balances: {[r.sku_code for r in negatives]}"


# --- the screens -------------------------------------------------------------


def test_r7_7_r7_8_r7_9_r7_10_the_inventory_page_shows_every_health_view(client):
    html = client.get("/inventory").text

    for heading in ("Needs attention", "ABC analysis", "Dead stock", "Fast and slow movers"):
        assert heading in html, f"/inventory is missing the {heading!r} section"

    # R7.7's boundaries, R7.8's window and R7.9's threshold must all be ON SCREEN.
    assert "80%" in html and "95%" in html
    assert "Upper bounds are inclusive" in html
    assert f"no sale in the last {DEAD_STOCK_DAYS} days" in html
    assert f"Over {SLOW_MOVER_MAX_PER_MONTH} a month is fast" in html
    # R7.10's trigger, and the "available not on hand" distinction.
    assert "on available, not on hand" in html


def test_r7_11_the_page_says_the_reorder_answer_comes_from_one_engine(client):
    html = client.get("/inventory").text
    assert "What to buy" in html
    # Asserted on a phrase that does not straddle a template line break.
    assert "not one per screen" in html
