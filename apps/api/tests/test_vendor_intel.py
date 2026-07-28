"""Part 4 — vendor intelligence (R5.1–R5.6, R5.10–R5.14).

Tests are named after the requirement they prove, so `pytest -q -k r5_3` is the
evidence for R5.3 and the part's closeout cites node ids rather than prose.

The arithmetic tests build their **own** supplier and their own confirm→receipt
history, so the numbers are hand-computable and a later part that adds one more
purchase order cannot break a formula test. R5.13 (the demo data is non-trivial) is
asserted separately against the seed.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.modules.activity.models import ActivityLog
from app.modules.procurement.models import PurchaseOrder
from app.modules.procurement.schemas import (
    GoodsReceiptCreate,
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from app.modules.procurement.service import GoodsReceiptService, PurchaseOrderService
from app.modules.products.models import Product
from app.modules.suppliers.models import ProductSupplier, Supplier
from app.modules.suppliers.schemas import (
    ProductSupplierUpsert,
    SupplierCreate,
    SupplierEvaluationCreate,
)
from app.modules.suppliers.service import (
    ProductSupplierService,
    SupplierService,
    VendorEvaluationService,
)
from app.modules.suppliers.vendor import VendorIntelService


def _product(db, sku: str = "AUR-TIS-002") -> Product:
    return db.scalar(select(Product).where(Product.sku_code == sku))


def _make_supplier(db, name: str) -> Supplier:
    """A supplier of our own, with no history at all."""
    type_id = db.scalar(select(Supplier.supplier_type_id).limit(1))
    return SupplierService(db).create(
        SupplierCreate(name=name, supplier_type_id=type_id, city="Pune"),
        actor_id=None,
    )


def _history(db, supplier_id, product, pairs: list[tuple[int, int, int | None]]) -> None:
    """Give a supplier a confirm→receipt history.

    Each pair is (confirm days ago, receive days ago, promised days ago); a promised
    value of None means nobody committed to a date for that order.
    """
    po_service = PurchaseOrderService(db)
    grn = GoodsReceiptService(db)
    today = datetime.now(UTC).date()
    for confirm_ago, receive_ago, promised_ago in pairs:
        order = po_service.create(
            PurchaseOrderCreate(
                supplier_id=supplier_id,
                lines=[PurchaseOrderLineCreate(product_id=product.id, qty=Decimal("5"))],
            ),
            actor_id=None,
        )
        po_service.confirm(
            order.id,
            actor_id=None,
            confirmed_at=datetime.now(UTC) - timedelta(days=confirm_ago),
            expected_date=(
                today - timedelta(days=promised_ago) if promised_ago is not None else None
            ),
        )
        grn.receive(
            order.id,
            GoodsReceiptCreate(received_at=datetime.now(UTC) - timedelta(days=receive_ago)),
            actor_id=None,
        )


# --- R5.3 lead time is MEASURED ---------------------------------------------


def test_r5_3_lead_time_is_measured_from_confirm_to_receipt(db):
    """Mean of (receipt − confirm) over the history. 4, 6 and 8 days → 6."""
    supplier = _make_supplier(db, "Lead Time Test Co")
    _history(db, supplier.id, _product(db), [(30, 26, None), (20, 14, None), (10, 2, None)])
    lead = VendorIntelService(db).lead_time(supplier.id)
    assert lead.is_known
    assert lead.value == "6 days"  # (4 + 6 + 8) / 3
    assert "÷ 3" in lead.formula
    assert "3 receipts" in lead.window


def test_r5_3_lead_time_rounds_half_up_without_float(db):
    """5 and 8 days → 6.5 → 7. Integer arithmetic, no float in the result."""
    supplier = _make_supplier(db, "Rounding Test Co")
    _history(db, supplier.id, _product(db), [(30, 25, None), (20, 12, None)])
    assert VendorIntelService(db).lead_time(supplier.id).value == "7 days"


def test_r5_3_there_is_no_editable_lead_time_field(db):
    """R5.3 forbids a typed lead time: the write schema must not offer one."""
    fields = set(ProductSupplierUpsert.model_fields)
    assert not {f for f in fields if "lead" in f.lower()}
    # And the mapping table itself carries no such column.
    assert not [c for c in ProductSupplier.__table__.columns if "lead" in c.name.lower()]


# --- R5.4 the on-time boundary ----------------------------------------------


def test_r5_4_received_exactly_on_the_promised_date_counts_as_on_time(db):
    """The boundary R5.4 makes explicit: `received <= promised` is on time."""
    supplier = _make_supplier(db, "Boundary Test Co")
    # Confirmed 20 days ago, promised for day-10, arrived exactly on day-10.
    _history(db, supplier.id, _product(db), [(20, 10, 10)])
    rate = VendorIntelService(db).on_time_rate(supplier.id)
    assert rate.is_known
    assert rate.value == "100%"


def test_r5_4_a_day_late_is_not_on_time(db):
    supplier = _make_supplier(db, "Late Test Co")
    # Promised day-11, arrived day-10 — i.e. one day after the promise.
    _history(db, supplier.id, _product(db), [(20, 10, 11)])
    assert VendorIntelService(db).on_time_rate(supplier.id).value == "0%"


def test_r5_4_on_time_rate_excludes_receipts_with_no_promised_date(db):
    """A receipt nobody promised a date for is excluded, never counted as met."""
    supplier = _make_supplier(db, "Unpromised Test Co")
    _history(
        db,
        supplier.id,
        _product(db),
        [(30, 20, 20), (25, 15, None), (20, 10, None)],  # 1 judged, 2 unpromised
    )
    rate = VendorIntelService(db).on_time_rate(supplier.id)
    assert rate.value == "100%"  # 1 of 1 judged, not 1 of 3
    assert "1 receipt" in rate.window
    assert rate.caveat is not None and "excluded" in rate.caveat


# --- R5.2 the vendor score --------------------------------------------------


def test_r5_2_score_weights_the_scorecard_and_on_time_rate(db):
    """Hand-computed: scorecard 4/5 → 80, on-time 100% → 80×60% + 100×40% = 88."""
    supplier = _make_supplier(db, "Score Test Co")
    _history(db, supplier.id, _product(db), [(20, 10, 10)])  # on time → 100%
    VendorEvaluationService(db).score(
        SupplierEvaluationCreate(
            supplier_id=supplier.id, quality_score=4, price_score=4, reliability_score=4
        ),
        actor_id=None,
    )
    score = VendorIntelService(db).score(supplier.id)
    assert score.is_known
    assert score.value == "88"
    # G11: the arithmetic is on screen, not just the answer.
    assert "80" in score.formula and "100" in score.formula
    labels = {i.label for i in score.inputs}
    assert labels == {"Scorecard", "On-time delivery"}


def test_r5_2_score_renormalises_when_only_one_input_exists(db):
    """No scorecard: the on-time input carries the whole score, and says so."""
    supplier = _make_supplier(db, "One Input Test Co")
    _history(db, supplier.id, _product(db), [(20, 10, 10), (30, 20, 25)])  # 1 of 2 → 50%
    score = VendorIntelService(db).score(supplier.id)
    assert score.value == "50"
    assert score.caveat is not None and "whole score" in score.caveat
    missing = [i for i in score.inputs if i.is_missing]
    assert [i.label for i in missing] == ["Scorecard"]


# --- R5.11 insufficient history says "unknown" ------------------------------


def test_r5_11_lead_time_is_unknown_with_no_receipts(db):
    supplier = _make_supplier(db, "No History Co")
    lead = VendorIntelService(db).lead_time(supplier.id)
    assert not lead.is_known
    assert lead.display == "unknown"
    assert lead.value is None  # never 0
    assert lead.unknown_reason and "received" in lead.unknown_reason
    # Still tells the founder what it would need.
    assert lead.formula


def test_r5_11_score_is_unknown_with_neither_input(db):
    supplier = _make_supplier(db, "Nothing Known Co")
    score = VendorIntelService(db).score(supplier.id)
    assert score.display == "unknown"
    assert score.value is None  # never 50
    assert all(i.is_missing for i in score.inputs)


def test_r5_11_on_time_is_unknown_when_nothing_was_promised(db):
    supplier = _make_supplier(db, "Never Promised Co")
    _history(db, supplier.id, _product(db), [(20, 10, None)])
    rate = VendorIntelService(db).on_time_rate(supplier.id)
    assert rate.display == "unknown"
    assert "promised" in rate.unknown_reason


# --- R5.1 mapping, R5.5 MOQ -------------------------------------------------


def test_r5_1_preferred_supplier_is_exclusive_per_product(db):
    product = _product(db, "AUR-TIS-004")
    a = _make_supplier(db, "Preferred A Co")
    b = _make_supplier(db, "Preferred B Co")
    links = ProductSupplierService(db)
    links.upsert(
        ProductSupplierUpsert(product_id=product.id, supplier_id=a.id, is_preferred=True),
        actor_id=None,
    )
    links.upsert(
        ProductSupplierUpsert(product_id=product.id, supplier_id=b.id, is_preferred=True),
        actor_id=None,
    )
    rows = links.list_for_product(product.id)
    preferred = [r for r in rows if r.is_preferred]
    assert len(preferred) == 1
    assert preferred[0].supplier_id == b.id
    # R5.1: the preferred one sorts first, alternates follow.
    assert rows[0].is_preferred is True


def test_r5_5_moq_is_recorded_per_product_and_supplier(db):
    product = _product(db, "AUR-TIS-005")
    supplier = _make_supplier(db, "MOQ Test Co")
    links = ProductSupplierService(db)
    links.upsert(
        ProductSupplierUpsert(
            product_id=product.id, supplier_id=supplier.id, moq=Decimal("250")
        ),
        actor_id=None,
    )
    assert links.moq(product.id, supplier.id) == Decimal("250")
    # Amending the link updates the MOQ rather than adding a second row.
    links.upsert(
        ProductSupplierUpsert(
            product_id=product.id, supplier_id=supplier.id, moq=Decimal("400")
        ),
        actor_id=None,
    )
    assert links.moq(product.id, supplier.id) == Decimal("400")
    assert len(links.links_for_product(product.id)) == 1


def test_r5_1_mapping_row_carries_rendered_intelligence_never_a_fake_number(db):
    """A supplier with no history shows "unknown" in the comparison, not 0."""
    product = _product(db, "AUR-TIS-006")
    supplier = _make_supplier(db, "Unknown Intel Co")
    links = ProductSupplierService(db)
    links.upsert(
        ProductSupplierUpsert(product_id=product.id, supplier_id=supplier.id),
        actor_id=None,
    )
    row = links.list_for_product(product.id)[0]
    assert row.score == "unknown"
    assert row.lead_time == "unknown"
    assert row.on_time_rate == "unknown"


# --- R5.6 price history -----------------------------------------------------


def test_r5_6_price_history_is_a_timeline_with_per_supplier_deltas(db):
    """The seeded product has several purchase prices; the timeline shows movement."""
    product = _product(db, "AUR-TIS-001")
    history = VendorIntelService(db).price_history(product.id)
    assert len(history) >= 2
    # Oldest first, so a timeline reads top to bottom.
    assert history == sorted(history, key=lambda r: r.valid_from)
    # At least one row is a change against the same supplier's previous price.
    assert any(r.delta_minor is not None for r in history)
    # Money stays integer minor units (G1).
    assert all(isinstance(r.price_minor, int) for r in history)
    assert any(r.is_current for r in history)


# --- R5.10 nothing derived is stored ---------------------------------------


def test_r5_10_the_mapping_stores_no_derived_number(db):
    """Score, lead time and on-time rate are computed, never columns (G7, R5.10)."""
    columns = {c.name for c in ProductSupplier.__table__.columns}
    assert not {c for c in columns if "score" in c or "lead" in c or "on_time" in c}
    # What it legitimately does hold (R5.10 names these two).
    assert {"is_preferred", "moq"} <= columns


# --- G11 / G15 / G5 --------------------------------------------------------


@pytest.mark.parametrize("output", ["lead_time", "on_time_rate", "score"])
def test_g11_every_output_states_what_formula_and_window(db, output):
    supplier = _make_supplier(db, f"G11 {output} Co")
    _history(db, supplier.id, _product(db), [(20, 10, 10)])
    explained = getattr(VendorIntelService(db), output)(supplier.id)
    assert explained.what and len(explained.what) > 20
    assert explained.formula
    assert explained.window


def test_g11_a_known_output_links_the_records_it_reasoned_from(db):
    supplier = _make_supplier(db, "G11 Records Co")
    _history(db, supplier.id, _product(db), [(20, 10, 10), (30, 20, 20)])
    lead = VendorIntelService(db).lead_time(supplier.id)
    assert lead.records
    assert all(r.label for r in lead.records)
    assert any(r.href and "/purchase-orders/" in r.href for r in lead.records)


def test_g15_reading_vendor_intelligence_writes_no_activity_rows(db):
    supplier = _make_supplier(db, "G15 Read Only Co")
    _history(db, supplier.id, _product(db), [(20, 10, 10)])
    db.flush()
    before = db.scalar(select(func.count()).select_from(ActivityLog))
    intel = VendorIntelService(db)
    intel.lead_time(supplier.id)
    intel.on_time_rate(supplier.id)
    intel.score(supplier.id)
    intel.price_history(_product(db).id)
    db.flush()
    assert db.scalar(select(func.count()).select_from(ActivityLog)) == before


def test_g5_linking_a_supplier_writes_exactly_one_activity_row(db):
    product = _product(db, "AUR-TIS-007")
    supplier = _make_supplier(db, "G5 Activity Co")
    db.flush()
    before = db.scalar(select(func.count()).select_from(ActivityLog))
    link = ProductSupplierService(db).upsert(
        ProductSupplierUpsert(
            product_id=product.id, supplier_id=supplier.id, is_preferred=True
        ),
        actor_id=None,
    )
    db.flush()
    after = db.scalar(select(func.count()).select_from(ActivityLog))
    # Exactly one, even though the verb also demoted any previous preferred row.
    assert after - before == 1
    row = db.scalar(
        select(ActivityLog)
        .where(ActivityLog.entity_id == link.id)
        .order_by(ActivityLog.created_at.desc())
    )
    assert row.entity_type == "product_supplier"
    assert row.verb == "linked"


# --- R5.13 the seeded demo data is non-trivial ------------------------------


def test_r5_13_seed_gives_two_suppliers_measurable_history(db):
    """The demo DB must make lead time and on-time rate real, not 0 (R5.13)."""
    intel = VendorIntelService(db)
    measured = []
    for code in ("SUPP-0001", "SUPP-0002"):
        supplier = db.scalar(select(Supplier).where(Supplier.code == code))
        lead = intel.lead_time(supplier.id)
        rate = intel.on_time_rate(supplier.id)
        assert lead.is_known, f"{code} has no measurable lead time"
        assert rate.is_known, f"{code} has no measurable on-time rate"
        # Non-trivial: an all-same-day seed would make this 0 days.
        measured.append(int(lead.value.split()[0]))
    assert any(days > 0 for days in measured)
    # The two suppliers must not look identical, or no comparison is being exercised.
    assert len({*measured}) > 1


def test_r5_13_seed_has_a_supplier_with_no_history_for_the_unknown_path(db):
    supplier = db.scalar(select(Supplier).where(Supplier.code == "SUPP-0003"))
    assert VendorIntelService(db).score(supplier.id).display == "unknown"


def test_r5_13_seed_has_one_product_below_reorder_with_an_open_po_and_one_without(db):
    """Both reorder cases exist, so the C2 engine has something to recommend."""
    from app.modules.inventory.service import InventoryService

    inventory = InventoryService(db)
    with_po = db.scalar(select(Product).where(Product.sku_code == "APX-GB-003"))
    without_po = db.scalar(select(Product).where(Product.sku_code == "APX-GB-004"))
    for product in (with_po, without_po):
        assert inventory.on_hand(product.id) < product.reorder_level

    def open_qty_for(product_id: uuid.UUID) -> Decimal:
        total = Decimal("0")
        orders = db.scalars(
            select(PurchaseOrder).where(
                PurchaseOrder.status.in_(("confirmed", "partially_received")),
                PurchaseOrder.deleted_at.is_(None),
            )
        )
        for order in orders:
            for line in order.lines:
                if line.product_id == product_id:
                    total += PurchaseOrderService.open_qty(line)
        return total

    assert open_qty_for(with_po.id) > 0
    assert open_qty_for(without_po.id) == 0
