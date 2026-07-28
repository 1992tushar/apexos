"""Part 4 C2 — the procurement calendar and the recommendation engine (R5.7–R5.9).

The arithmetic tests build their own product, their own stock and their own orders,
so every number is hand-computable and a later part that seeds one more purchase
order cannot break a formula test. The seed's two reorder cases are asserted
separately, as R5.13's "the demo data is non-trivial" check.
"""
from __future__ import annotations

import inspect
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.modules.activity.models import ActivityLog
from app.modules.config.models import Warehouse
from app.modules.inventory.service import InventoryService
from app.modules.procurement.recommend import (
    OPEN_PO_STATUSES,
    ProcurementCalendarService,
    RecommendationService,
)
from app.modules.procurement.schemas import PurchaseOrderCreate, PurchaseOrderLineCreate
from app.modules.procurement.service import PurchaseOrderService
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.schemas import ProductSupplierUpsert
from app.modules.suppliers.service import ProductSupplierService

MEASURED = "SUPP-0001"  # has receipt history, so its lead time is known
EMPTY = "SUPP-0003"  # no confirmed receipt at all


def _supplier(db, code: str) -> Supplier:
    return db.scalar(select(Supplier).where(Supplier.code == code))


def _warehouse(db) -> Warehouse:
    return db.scalar(select(Warehouse).where(Warehouse.deleted_at.is_(None)).limit(1))


@pytest.fixture()
def sku(db):
    """A product with a known stock position, isolated to this test's transaction.

    Returns a helper that sets the reorder level and moves stock to an exact figure,
    so a shortfall is arithmetic rather than a guess about the seed.
    """
    product = db.scalar(
        select(Product).where(Product.sku_code == "AUR-TIS-002")
    )
    inventory = InventoryService(db)

    def setup(*, on_hand: Decimal | str, reorder_level: Decimal | str) -> Product:
        target = Decimal(str(on_hand))
        current = inventory.on_hand(product.id)
        if target != current:
            inventory.record_movement(
                product_id=product.id,
                warehouse_id=_warehouse(db).id,
                qty_delta=target - current,
                reason="test_fixture",
                actor_id=None,
            )
        product.reorder_level = Decimal(str(reorder_level))
        db.flush()
        assert inventory.on_hand(product.id) == target
        return product

    return setup


def _order(db, supplier_id, product, qty: str, *, confirm: bool = True):
    """A purchase order for `qty`, confirmed by default (so it counts as open)."""
    order = PurchaseOrderService(db).create(
        PurchaseOrderCreate(
            supplier_id=supplier_id,
            lines=[PurchaseOrderLineCreate(product_id=product.id, qty=Decimal(qty))],
        ),
        actor_id=None,
    )
    if confirm:
        PurchaseOrderService(db).confirm(
            order.id,
            actor_id=None,
            expected_date=datetime.now(UTC).date() + timedelta(days=7),
        )
    return order


def _only(db, product, **kwargs):
    """The recommendation for one product, or None."""
    rows = RecommendationService(db).recommend(product_id=product.id, **kwargs)
    return rows[0] if rows else None


# --- R5.8 the quantity arithmetic --------------------------------------------


def test_r5_8_quantity_is_reorder_level_minus_stock_minus_what_is_on_order(db, sku):
    """The whole formula, with every term non-zero."""
    product = sku(on_hand="12", reorder_level="50")
    _order(db, _supplier(db, MEASURED).id, product, "8")

    rec = _only(db, product)
    assert rec is not None
    assert rec.on_hand == Decimal("12")
    assert rec.reorder_level == Decimal("50")
    assert rec.on_order == Decimal("8")
    assert rec.shortfall == Decimal("30")
    assert rec.qty == Decimal("30")


def test_r5_8_an_open_purchase_order_is_not_double_ordered(db, sku):
    """The failure this requirement exists to prevent: ordering what is already coming.

    Same shortfall on the shelf, twice — once with nothing on order and once with
    half of it already confirmed. The second recommendation must be smaller by
    exactly the open quantity, not the same.
    """
    product = sku(on_hand="0", reorder_level="100")
    assert _only(db, product).qty == Decimal("100")

    _order(db, _supplier(db, MEASURED).id, product, "40")
    assert _only(db, product).qty == Decimal("60")


def test_r5_8_a_receipt_against_an_open_order_reduces_what_is_still_on_order(db, sku):
    """`open_qty` is ordered − received (R4.9), and this reads that, not `qty`."""
    from app.modules.procurement.schemas import GoodsReceiptCreate, GoodsReceiptLineInput
    from app.modules.procurement.service import GoodsReceiptService

    product = sku(on_hand="0", reorder_level="100")
    order = _order(db, _supplier(db, MEASURED).id, product, "40")
    GoodsReceiptService(db).receive(
        order.id,
        GoodsReceiptCreate(
            lines=[GoodsReceiptLineInput(product_id=product.id, qty=Decimal("25"))]
        ),
        actor_id=None,
    )

    rec = _only(db, product)
    # 25 arrived (so stock is 25) and 15 is still outstanding: 100 − 25 − 15 = 60.
    assert rec.on_hand == Decimal("25")
    assert rec.on_order == Decimal("15")
    assert rec.qty == Decimal("60")


def test_r5_8_a_draft_purchase_order_does_not_count_as_on_order(db, sku):
    """A draft is not a commitment to anyone, so it must not suppress the advice."""
    product = sku(on_hand="0", reorder_level="100")
    _order(db, _supplier(db, MEASURED).id, product, "40", confirm=False)

    rec = _only(db, product)
    assert rec.on_order == Decimal("0")
    assert rec.qty == Decimal("100")
    assert "draft" not in OPEN_PO_STATUSES


def test_r5_8_a_product_at_or_above_its_reorder_level_is_not_recommended(db, sku):
    product = sku(on_hand="50", reorder_level="50")
    assert _only(db, product) is None

    sku(on_hand="80", reorder_level="50")
    assert _only(db, product) is None


def test_r5_8_a_product_fully_covered_by_open_orders_is_not_recommended(db, sku):
    """Short on the shelf but the gap is already on the way — nothing to do."""
    product = sku(on_hand="10", reorder_level="50")
    _order(db, _supplier(db, MEASURED).id, product, "40")
    assert _only(db, product) is None


def test_r5_5_a_supplier_minimum_raises_the_quantity_and_shows_the_step(db, sku):
    """Ordering 30 from a supplier whose minimum is 250 is a rejected order."""
    product = sku(on_hand="20", reorder_level="50")
    supplier = _supplier(db, MEASURED)
    ProductSupplierService(db).upsert(
        ProductSupplierUpsert(
            product_id=product.id,
            supplier_id=supplier.id,
            is_preferred=True,
            moq=Decimal("250"),
        ),
        actor_id=None,
    )

    rec = _only(db, product)
    assert rec.shortfall == Decimal("30")
    assert rec.qty == Decimal("250")
    assert rec.moq == Decimal("250")
    # The raise is a visible term, not a silent adjustment (G11).
    assert "250" in rec.explained.formula
    assert "will not take less" in rec.explained.formula
    assert "30 short" in rec.explained.formula


def test_r5_5_a_minimum_below_the_shortfall_changes_nothing(db, sku):
    product = sku(on_hand="0", reorder_level="500")
    supplier = _supplier(db, MEASURED)
    ProductSupplierService(db).upsert(
        ProductSupplierUpsert(
            product_id=product.id, supplier_id=supplier.id, is_preferred=True,
            moq=Decimal("100"),
        ),
        actor_id=None,
    )
    assert _only(db, product).qty == Decimal("500")


# --- R5.8 / G11 the explanation ----------------------------------------------


def test_r5_8_every_recommendation_carries_an_explanation_and_a_linked_record(db):
    """G11's P0 requirement, over every row the engine produces."""
    rows = RecommendationService(db).recommend()
    assert len(rows) > 20, "the seed must leave plenty below reorder level"
    for rec in rows:
        explained = rec.explained
        assert explained.what and explained.formula and explained.window
        assert explained.value == rec.explained.display != "unknown"
        assert explained.inputs, "the terms of the formula must be listed"
        assert explained.records, "G11: at least one record it reasoned from"
        assert any(r.href for r in explained.records)


def test_r5_8_the_explanation_names_the_open_order_it_subtracted(db, sku):
    product = sku(on_hand="0", reorder_level="100")
    order = _order(db, _supplier(db, MEASURED).id, product, "40")

    rec = _only(db, product)
    labels = [r.label for r in rec.explained.records]
    assert any(order.po_no in label for label in labels), labels
    hrefs = [r.href for r in rec.explained.records]
    assert f"/purchase-orders/{order.id}" in hrefs


def test_r5_8_the_sentence_reads_like_the_requirements_own_example(db, sku):
    """R5.8 asks for "reorder 40 of X — stock 12, reorder level 50, 0 on open PO,
    lead time 9 days measured over 6 receipts". This is that sentence."""
    product = sku(on_hand="12", reorder_level="50")
    supplier = _supplier(db, MEASURED)
    ProductSupplierService(db).upsert(
        ProductSupplierUpsert(
            product_id=product.id, supplier_id=supplier.id, is_preferred=True
        ),
        actor_id=None,
    )

    sentence = _only(db, product).sentence
    assert sentence.startswith("reorder 38 of ")
    assert "stock 12" in sentence
    assert "reorder level 50" in sentence
    assert "0 on open PO" in sentence
    assert "lead time" in sentence and "receipts" in sentence
    # Quantities read as a person writes them, not as Numeric(18,4) stores them.
    assert ".0000" not in sentence


def test_r5_11_a_recommendation_without_a_measured_lead_time_says_so(db, sku):
    """R5.11: unknown is stated, and the advice still stands.

    Being short of stock is a fact about the ledger; how fast the supplier is, is a
    separate fact. Withholding the recommendation because one input is missing would
    be worse than giving it with the gap named.
    """
    product = sku(on_hand="0", reorder_level="40")
    supplier = _supplier(db, EMPTY)
    ProductSupplierService(db).upsert(
        ProductSupplierUpsert(
            product_id=product.id, supplier_id=supplier.id, is_preferred=True
        ),
        actor_id=None,
    )

    rec = _only(db, product)
    assert rec.qty == Decimal("40"), "the shortfall is still measured"
    assert rec.lead_time is not None and not rec.lead_time.is_known
    assert "lead time unknown" in rec.sentence
    assert "never been measured" in rec.explained.caveat
    missing = [i for i in rec.explained.inputs if i.is_missing]
    assert missing and missing[0].missing_reason


def test_r5_11_a_recommendation_with_no_preferred_supplier_names_that_gap(db, sku):
    product = sku(on_hand="0", reorder_level="40")
    rec = _only(db, product)
    assert rec.supplier_id is None
    assert "no preferred supplier set" in rec.sentence
    assert "No preferred supplier" in rec.explained.caveat
    # Still a real recommendation, with the product itself as its source record.
    assert rec.qty == Decimal("40")
    assert rec.explained.records


# --- R5.9 ONE entry point -----------------------------------------------------


def test_r5_9_the_recommendation_engine_has_one_entry_point_with_a_clear_signature():
    """Parts 5 and 10 call this signature; R7.11/R13.6 check for a second engine."""
    sig = inspect.signature(RecommendationService.recommend)
    assert list(sig.parameters) == ["self", "product_id", "limit"]
    for name in ("product_id", "limit"):
        param = sig.parameters[name]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        assert param.default is None


def test_r5_9_no_second_implementation_of_what_to_buy_exists_in_the_app():
    """A source walk, because the duplicate this forbids would be in another module.

    Asserts a floor on what it inspected: a walk that silently finds no files would
    otherwise pass by examining nothing.
    """
    app_dir = Path(__file__).resolve().parents[1] / "app"
    modules = list(app_dir.rglob("*.py"))
    assert len(modules) > 40, f"only walked {len(modules)} modules"

    pattern = re.compile(r"^\s*def (recommend|recommendations|suggest_reorder)\b", re.M)
    definers = [m for m in modules if pattern.search(m.read_text(encoding="utf-8"))]
    assert [m.name for m in definers] == ["recommend.py"], [str(m) for m in definers]


def test_r5_9_the_engine_writes_nothing(db):
    """G15/R5.10: a recommendation is a read. It logs nothing and stores nothing."""
    before = db.scalar(select(func.count()).select_from(ActivityLog))
    rows = RecommendationService(db).recommend(limit=5)
    assert rows
    assert db.scalar(select(func.count()).select_from(ActivityLog)) == before


def test_r5_9_recommendations_are_ordered_worst_shortfall_first(db):
    rows = RecommendationService(db).recommend()
    shortfalls = [r.shortfall for r in rows]
    assert shortfalls == sorted(shortfalls, reverse=True)


def test_r5_9_a_limit_bounds_the_list_without_changing_its_head(db):
    everything = RecommendationService(db).recommend()
    limited = RecommendationService(db).recommend(limit=3)
    assert len(limited) == 3
    assert [r.sku_code for r in limited] == [r.sku_code for r in everything[:3]]


# --- R5.7 the calendar --------------------------------------------------------


def test_r5_7_due_to_arrive_lists_open_orders_by_promised_date(db):
    arrivals = ProcurementCalendarService(db).arrivals()
    assert arrivals, "the seed must leave orders outstanding"
    for arrival in arrivals:
        assert arrival.status in OPEN_PO_STATUSES
        assert arrival.open_qty > 0
    # Promised dates ascending, and every unpromised order after every promised one.
    promised = [a.expected_date for a in arrivals if a.expected_date is not None]
    assert promised == sorted(promised)
    first_unpromised = next(
        (i for i, a in enumerate(arrivals) if a.expected_date is None), len(arrivals)
    )
    assert all(a.expected_date is None for a in arrivals[first_unpromised:])


def test_r5_7_an_order_with_no_promised_date_is_never_bucketed_under_today(db):
    arrivals = ProcurementCalendarService(db).arrivals()
    unpromised = [a for a in arrivals if a.expected_date is None]
    assert unpromised, "the seed must include an order nobody promised a date for"
    for arrival in unpromised:
        assert arrival.bucket == "unpromised"
        assert arrival.days_away is None


def test_r5_7_an_order_past_its_promised_date_is_bucketed_overdue(db):
    calendar = ProcurementCalendarService(db).calendar()
    overdue = calendar.arrivals_in("overdue")
    assert overdue, "the seed must include one late arrival (R5.7)"
    for arrival in overdue:
        assert arrival.expected_date < calendar.as_of
        assert arrival.days_away < 0


def test_r5_7_a_fully_received_order_leaves_the_calendar(db, sku):
    """Nothing outstanding means nothing due to arrive, whatever the status says."""
    from app.modules.procurement.service import GoodsReceiptService

    product = sku(on_hand="0", reorder_level="10")
    order = _order(db, _supplier(db, MEASURED).id, product, "40")
    service = ProcurementCalendarService(db)
    assert any(a.purchase_order_id == order.id for a in service.arrivals())

    GoodsReceiptService(db).receive(order.id, None, actor_id=None)
    assert not any(a.purchase_order_id == order.id for a in service.arrivals())


def test_r5_7_the_calendar_reports_the_total_it_truncated(db):
    """A silently capped list reads as "that is everything"."""
    calendar = ProcurementCalendarService(db).calendar(limit=2)
    assert len(calendar.recommendations) == 2
    assert calendar.recommendation_total > 2


# --- R5.7 / R5.8 on the screen ------------------------------------------------


def test_r5_7_the_procurement_page_shows_both_halves_of_the_calendar(db, client):
    calendar = ProcurementCalendarService(db).calendar()
    html = client.get("/procurement").text

    assert "Due to arrive" in html and "Due to order" in html
    for label in ("Overdue", "Due today", "Within 7 days", "Later", "No date promised"):
        assert label in html
    for arrival in calendar.arrivals:
        assert arrival.po_no in html
        assert f"/purchase-orders/{arrival.purchase_order_id}" in html
    assert "no date promised" in html


def test_r5_8_the_procurement_page_explains_every_recommendation_it_shows(db, client):
    calendar = ProcurementCalendarService(db).calendar()
    html = client.get("/procurement").text

    assert calendar.recommendations
    for rec in calendar.recommendations:
        assert rec.sku_code in html
        assert rec.sentence in html
        assert rec.explained.formula in html
        assert f"/products/{rec.product_id}" in html
    # The count is honest about what was left out.
    assert f"of {calendar.recommendation_total}" in html


def test_r5_13_the_seed_puts_both_reorder_cases_at_the_top_of_the_list(db):
    """The demo data exercises the screen, including its edge case (G14).

    APX-GB-003 is below reorder WITH an open PO and APX-GB-004 WITHOUT one, and both
    are visible without paging — a recommendation list where the interesting rows sit
    on page four demonstrates nothing.
    """
    rows = ProcurementCalendarService(db).calendar().recommendations
    by_sku = {r.sku_code: r for r in rows}
    assert "APX-GB-003" in by_sku and "APX-GB-004" in by_sku

    with_po = by_sku["APX-GB-003"]
    assert with_po.on_order > 0
    assert with_po.qty == with_po.reorder_level - with_po.on_hand - with_po.on_order
    assert "already on order" in with_po.explained.formula

    without_po = by_sku["APX-GB-004"]
    assert without_po.on_order == Decimal("0")
    # Its supplier's minimum is above the shortfall, so the MOQ step is on screen.
    assert without_po.qty > without_po.shortfall


def test_r5_13_the_seeded_recommendations_name_a_supplier_and_its_lead_time(db):
    rows = ProcurementCalendarService(db).calendar().recommendations
    named = [r for r in rows if r.supplier_id is not None]
    assert named, "the seed must map a supplier to at least one short product"
    for rec in named:
        assert rec.lead_time is not None
        assert isinstance(rec.supplier_id, uuid.UUID)
    # And at least one of them has a MEASURED lead time, so R5.8's full sentence is
    # demonstrable on the demo data rather than only in a unit test.
    assert any(r.lead_time.is_known for r in named)
