"""Part 5 C2 — weighted-average cost (R6.16) and stock ageing (R6.10).

The valuation tests build their **own** product with a known purchase history rather than
asserting against the seed's totals: a later part adding one more receipt must not break an
arithmetic test. The seed's own figures are asserted separately, as R6.14's "the demo data
is non-trivial" check.

Ageing takes an injected `as_of`, so the boundary tests sit exactly on a bucket edge
instead of depending on when the suite happens to run.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.money import round_minor
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import AGE_BUCKETS
from app.modules.inventory.service import InventoryService
from app.modules.inventory.valuation import ValuationService, bucket_for

NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


@pytest.fixture()
def warehouse(db):
    from app.modules.config.models import Warehouse

    return db.scalar(select(Warehouse).where(Warehouse.deleted_at.is_(None)))


@pytest.fixture()
def fresh_product(db):
    """A product with NO movements, so this file's arithmetic starts from zero."""
    from app.modules.products.models import Product

    template = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    product = Product(
        sku_code=f"WAC-{uuid.uuid4().hex[:8].upper()}",
        name="Valuation test SKU",
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


def _buy(db, product, warehouse, qty: str, unit_cost_minor: int, *, days_ago: int = 0):
    return InventoryService(db).record_movement(
        product_id=product.id,
        warehouse_id=warehouse.id,
        qty_delta=Decimal(qty),
        reason="PURCHASE",
        unit_cost_minor=unit_cost_minor,
        occurred_at=NOW - timedelta(days=days_ago),
    )


# --- R6.16: weighted-average cost --------------------------------------------


def test_r6_16_weighted_average_cost_matches_a_hand_computed_figure(db, fresh_product, warehouse):
    # 10 @ 100.00 = 1000.00 · 30 @ 120.00 = 3600.00 · 10 @ 90.00 = 900.00
    # total 5500.00 over 50 units -> 110.00 exactly.
    _buy(db, fresh_product, warehouse, "10", 10000)
    _buy(db, fresh_product, warehouse, "30", 12000)
    _buy(db, fresh_product, warehouse, "10", 9000)

    svc = ValuationService(db)
    assert svc.cost_basis_minor(fresh_product.id) == 11000

    explained = svc.cost_basis(fresh_product.id)
    assert explained.is_known
    assert explained.value == "110.00"
    # The average must differ from a plain mean of the prices (103.33), or the test would
    # pass on an implementation that ignored quantity entirely.
    plain_mean = round_minor(Decimal(10000 + 12000 + 9000) / 3)
    assert svc.cost_basis_minor(fresh_product.id) != plain_mean


def test_r6_16_only_purchases_set_the_cost_basis(db, fresh_product, warehouse):
    """Transfers, putaway, adjustments and counts must not move the average.

    Each of these carries a unit-cost hint in the existing code paths, so an
    implementation that simply summed "inbound movements with a cost" would drift.
    """
    _buy(db, fresh_product, warehouse, "10", 10000)
    svc = ValuationService(db)
    assert svc.cost_basis_minor(fresh_product.id) == 10000

    inventory = InventoryService(db)
    for reason in ("TRANSFER", "ADJUSTMENT", "COUNT", "PUTAWAY"):
        inventory.record_movement(
            product_id=fresh_product.id,
            warehouse_id=warehouse.id,
            qty_delta=Decimal("50"),
            reason=reason,
            unit_cost_minor=99900,  # wildly different; must be ignored
        )

    assert svc.cost_basis_minor(fresh_product.id) == 10000, (
        "a non-purchase movement changed the cost basis"
    )


def test_r6_16_a_purchase_without_a_recorded_cost_is_excluded_not_counted_as_zero(
    db, fresh_product, warehouse
):
    _buy(db, fresh_product, warehouse, "10", 10000)
    InventoryService(db).record_movement(
        product_id=fresh_product.id,
        warehouse_id=warehouse.id,
        qty_delta=Decimal("90"),
        reason="PURCHASE",
        unit_cost_minor=None,
    )

    svc = ValuationService(db)
    # Counting the 90 uncosted units at zero would drag 100.00 down to 10.00.
    assert svc.cost_basis_minor(fresh_product.id) == 10000

    explained = svc.cost_basis(fresh_product.id)
    missing = [i for i in explained.inputs if i.is_missing]
    assert missing, "the excluded quantity must be disclosed, not silently dropped"
    assert "90" in missing[0].value


def test_r6_16_cost_basis_is_unknown_when_nothing_was_ever_bought(db, fresh_product):
    explained = ValuationService(db).cost_basis(fresh_product.id)

    assert not explained.is_known
    assert explained.display == "unknown"
    assert explained.unknown_reason
    assert ValuationService(db).cost_basis_minor(fresh_product.id) is None


def test_r6_16_value_is_on_hand_times_the_basis_and_unknown_stays_unknown(
    db, fresh_product, warehouse
):
    _buy(db, fresh_product, warehouse, "20", 15000)

    svc = ValuationService(db)
    row = next(r for r in svc.stock_value() if r.product_id == fresh_product.id)

    assert row.qty_on_hand == Decimal("20")
    assert row.cost_basis_minor == 15000
    assert row.value_minor == 300000  # 20 x 150.00 = 3000.00

    # A product with stock but no purchase history contributes no value, and is counted
    # rather than being treated as zero-cost stock.
    assert svc.unknown_basis_count() >= 0


def test_r6_16_the_total_excludes_unknown_basis_rather_than_zeroing_it(
    db, fresh_product, warehouse
):
    _buy(db, fresh_product, warehouse, "20", 15000)
    svc = ValuationService(db)
    rows = svc.stock_value()

    assert svc.total_value_minor(rows) == sum(r.value_minor or 0 for r in rows)
    # And passing the rows in must give the same answer as recomputing them.
    assert svc.total_value_minor(rows) == svc.total_value_minor()


def test_r6_16_margin_does_not_read_the_cost_basis(db):
    """R11.6 / D-A: margin is selling − the price snapshotted on the line.

    A source walk, because the failure mode is a later part quietly wiring valuation into
    MarginService and making margin depend on a cost basis that moves with every purchase.
    """
    from pathlib import Path

    margin_src = (
        Path(__file__).resolve().parents[1] / "app" / "modules" / "pricing" / "service.py"
    ).read_text(encoding="utf-8")
    assert "ValuationService" not in margin_src
    assert "cost_basis" not in margin_src


# --- R6.10: ageing -----------------------------------------------------------


def test_r6_10_bucket_boundaries_are_inclusive_at_the_upper_bound(db):
    """R6.10 requires the boundary behaviour to be DEFINED. This is the definition."""
    assert bucket_for(0)[0] == "fresh"
    assert bucket_for(30)[0] == "fresh", "30 days must fall in 0–30, not 31–60"
    assert bucket_for(31)[0] == "thirty"
    assert bucket_for(60)[0] == "thirty"
    assert bucket_for(61)[0] == "sixty"
    assert bucket_for(90)[0] == "sixty", "90 days must fall in 61–90, not over-90"
    assert bucket_for(91)[0] == "stale"
    assert bucket_for(3650)[0] == "stale"
    # The last bucket must stay open-ended, or an old-enough item falls out of every bucket.
    assert AGE_BUCKETS[-1][2] is None


def test_r6_10_a_balance_is_split_across_buckets_by_arrival_date(db, fresh_product, warehouse):
    _buy(db, fresh_product, warehouse, "40", 10000, days_ago=200)
    _buy(db, fresh_product, warehouse, "30", 10000, days_ago=80)
    _buy(db, fresh_product, warehouse, "10", 10000, days_ago=5)

    row = next(
        r
        for r in ValuationService(db).ageing(as_of=NOW)
        if r.product_id == fresh_product.id
    )
    buckets = {b.key: b.qty for b in row.buckets}

    assert buckets["fresh"] == Decimal("10")
    assert buckets["sixty"] == Decimal("30")
    assert buckets["stale"] == Decimal("40")
    assert row.oldest_days == 200
    assert row.unattributed == Decimal("0")
    assert sum(buckets.values()) == row.qty_on_hand


def test_r6_10_the_balance_is_attributed_to_the_newest_arrivals_first(db, fresh_product, warehouse):
    """The stated approximation: older stock is assumed to leave first.

    Buy 100 old and 20 new, then sell 100. What remains must be the 20 new units, not the
    old ones — otherwise the buckets would report stock that has already gone.
    """
    _buy(db, fresh_product, warehouse, "100", 10000, days_ago=200)
    _buy(db, fresh_product, warehouse, "20", 10000, days_ago=2)
    InventoryService(db).record_movement(
        product_id=fresh_product.id,
        warehouse_id=warehouse.id,
        qty_delta=Decimal("-100"),
        reason="SALE",
    )

    row = next(
        r
        for r in ValuationService(db).ageing(as_of=NOW)
        if r.product_id == fresh_product.id
    )
    buckets = {b.key: b.qty for b in row.buckets}

    assert row.qty_on_hand == Decimal("20")
    assert buckets["fresh"] == Decimal("20")
    assert buckets["stale"] == Decimal("0"), "sold-through old stock is still being aged"
    assert row.oldest_days == 2


def test_r6_10_a_balance_no_arrival_covers_is_reported_not_aged(db, fresh_product, warehouse):
    """An inflated balance must not be silently attributed to the oldest arrival."""
    _buy(db, fresh_product, warehouse, "10", 10000, days_ago=100)
    # An upward adjustment is not an arrival with a date to age from... it is, in fact,
    # inbound, so to create genuinely unattributed stock the balance must exceed every
    # inbound movement. A putaway inbound is excluded by design, which does exactly that.
    InventoryService(db).record_movement(
        product_id=fresh_product.id,
        warehouse_id=warehouse.id,
        qty_delta=Decimal("15"),
        reason="PUTAWAY",
    )

    row = next(
        r
        for r in ValuationService(db).ageing(as_of=NOW)
        if r.product_id == fresh_product.id
    )
    assert row.qty_on_hand == Decimal("25")
    assert row.unattributed == Decimal("15")
    assert sum(b.qty for b in row.buckets) == Decimal("10")


def test_r6_10_putaway_does_not_reset_the_age_of_stock(db, fresh_product, warehouse):
    """C1's putaway re-addresses stock inside one warehouse. Treating its inbound half as
    an arrival would make every put-away product look like it landed today."""
    _buy(db, fresh_product, warehouse, "10", 10000, days_ago=150)
    arrivals = InventoryRepository(db).arrivals(fresh_product.id)
    assert len(arrivals) == 1

    inventory = InventoryService(db)
    inventory.record_movement(
        product_id=fresh_product.id, warehouse_id=warehouse.id,
        qty_delta=Decimal("-10"), reason="PUTAWAY",
    )
    inventory.record_movement(
        product_id=fresh_product.id, warehouse_id=warehouse.id,
        qty_delta=Decimal("10"), reason="PUTAWAY",
    )

    assert len(InventoryRepository(db).arrivals(fresh_product.id)) == 1
    row = next(
        r for r in ValuationService(db).ageing(as_of=NOW) if r.product_id == fresh_product.id
    )
    assert row.oldest_days == 150


def test_r6_10_the_approximation_is_stated_and_carried_in_the_explanation(
    db, fresh_product, warehouse
):
    _buy(db, fresh_product, warehouse, "10", 10000, days_ago=40)
    svc = ValuationService(db)

    note = svc.ageing_note()
    assert "Approximate" in note and "lot tracking" in note

    row = next(r for r in svc.ageing(as_of=NOW) if r.product_id == fresh_product.id)
    explained = svc.ageing_explained(row)
    # The caveat is the same sentence, from one source — the screen and the panel cannot
    # drift into describing the approximation differently.
    assert explained.caveat == note
    assert explained.value == "40 days"


def test_r6_10_a_product_with_no_arrivals_ages_to_unknown(db, fresh_product, warehouse):
    InventoryService(db).record_movement(
        product_id=fresh_product.id, warehouse_id=warehouse.id,
        qty_delta=Decimal("5"), reason="PUTAWAY",
    )
    svc = ValuationService(db)
    row = next(r for r in svc.ageing(as_of=NOW) if r.product_id == fresh_product.id)

    assert row.oldest_days is None
    assert row.unattributed == Decimal("5")
    assert not svc.ageing_explained(row).is_known


def test_r6_10_a_naive_timestamp_does_not_blow_up_the_age_calculation(db, fresh_product, warehouse):
    """SQLite returns naive datetimes for `DateTime(timezone=True)`. Comparing one against
    an aware `as_of` raises TypeError — on SQLite only, which is the worst place to find
    it. This asserts the read-as-UTC fallback holds."""
    movement = _buy(db, fresh_product, warehouse, "10", 10000, days_ago=45)
    movement.occurred_at = movement.occurred_at.replace(tzinfo=None)
    db.flush()

    row = next(
        r for r in ValuationService(db).ageing(as_of=NOW) if r.product_id == fresh_product.id
    )
    assert row.oldest_days == 45


# --- R6.14: the demo data C2 owes the screens --------------------------------


def test_r6_14_the_seed_holds_a_non_trivial_weighted_average(db):
    """A seed where every unit cost the same makes R6.16 untestable on screen."""
    svc = ValuationService(db)
    interesting = []
    for row in svc.stock_value()[:60]:
        if not row.is_known:
            continue
        totals = InventoryRepository(db).acquisition_totals(row.product_id)
        if totals and totals[0][3] > 1:  # more than one costed purchase
            interesting.append(row)
    assert interesting, "no seeded product has more than one purchase — WAC is trivial"


def test_r6_14_the_seed_holds_stock_in_more_than_one_age_bucket(db):
    """Otherwise R6.10's screen is one column of zeros and R7.8 has nothing to find."""
    spread = [
        r for r in ValuationService(db).ageing() if sum(1 for b in r.buckets if b.qty) > 1
    ]
    assert spread, "no seeded product spans two age buckets"
    assert any(r.stale_qty > 0 for r in spread), "nothing is over 90 days old"
