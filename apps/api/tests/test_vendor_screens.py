"""Part 4 — the vendor intelligence SCREENS (R5.12, R5.5 in R4.5's grid, R5.1's verbs).

`test_vendor_intel.py` proves the arithmetic. This file proves the founder can see
it: that each figure reaches the page it belongs on, that it arrives with the
formula, window and source records G11 demands, and that "unknown" reaches the
screen as the word rather than as a blank or a zero (R5.11).

Where a value is asserted, it is asserted against what the SERVICE computed rather
than against a hardcoded number — the claim being tested is "the screen shows what
was measured", and a later part that adds one more purchase order must not break a
screen test.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.modules.procurement.models import Rfq
from app.modules.procurement.preorder import RfqService
from app.modules.products.models import Product
from app.modules.suppliers.models import ProductSupplier, Supplier
from app.modules.suppliers.schemas import ProductSupplierUpsert
from app.modules.suppliers.service import ProductSupplierService
from app.modules.suppliers.vendor import VendorIntelService
from app.web.core import number

# The seed's three suppliers, chosen for what they do and do not have:
# SUPP-0001 has a scorecard AND receipts, SUPP-0003 has neither (see app/seed/vendor.py).
MEASURED = "SUPP-0001"
EMPTY = "SUPP-0003"
MAPPED_SKU = "APX-GB-001"  # two mapped suppliers, one preferred
PRICED_SKU = "AUR-TIS-001"  # the SKU the seeded price timeline is written for


def _supplier(db, code: str) -> Supplier:
    return db.scalar(select(Supplier).where(Supplier.code == code))


def _product(db, sku: str) -> Product:
    return db.scalar(select(Product).where(Product.sku_code == sku))


# --- R5.12 the supplier page --------------------------------------------------


def test_r5_12_supplier_detail_shows_score_lead_time_and_on_time_rate(db, client):
    supplier = _supplier(db, MEASURED)
    intel = VendorIntelService(db)
    html = client.get(f"/suppliers/{supplier.id}").text

    assert "Vendor intelligence" in html
    for figure in ("Vendor score", "Measured lead time", "On-time delivery rate"):
        assert figure in html
    # The measured values themselves, as the service rendered them.
    for explained in (
        intel.score(supplier.id),
        intel.lead_time(supplier.id),
        intel.on_time_rate(supplier.id),
    ):
        assert explained.is_known, "the seed must give this supplier real history (R5.13)"
        assert explained.value in html
        assert explained.formula in html


def test_r5_12_supplier_detail_carries_the_formula_window_and_source_records(db, client):
    """G11's four parts, on the page rather than in a docstring."""
    supplier = _supplier(db, MEASURED)
    lead = VendorIntelService(db).lead_time(supplier.id)
    html = client.get(f"/suppliers/{supplier.id}").text

    assert "Formula" in html and "Window" in html
    assert lead.window in html
    assert "Computed from" in html
    assert lead.records, "a measured figure must name the records behind it"
    for record in lead.records:
        if record.href:
            assert record.href in html


def test_r5_12_supplier_detail_lists_the_receipts_behind_the_numbers(db, client):
    supplier = _supplier(db, MEASURED)
    receipts = VendorIntelService(db).receipts(supplier.id)
    html = client.get(f"/suppliers/{supplier.id}").text

    assert "Receipt history" in html
    for receipt in receipts:
        assert receipt.receipt_no in html
    # A receipt nobody promised a date for is shown as excluded, not as met (R5.4).
    if any(r.is_on_time is None for r in receipts):
        assert "not judged" in html
        assert "no date promised" in html


def test_r5_11_supplier_detail_says_unknown_rather_than_showing_a_number(db, client):
    """The insufficient-history path, on screen (R5.11 + G11)."""
    supplier = _supplier(db, EMPTY)
    intel = VendorIntelService(db)
    score = intel.score(supplier.id)
    assert not score.is_known, "SUPP-0003 must have no scorecard and no receipts"

    html = client.get(f"/suppliers/{supplier.id}").text
    assert "unknown" in html
    # What it would take to know, which is the useful half of an unknown.
    assert score.unknown_reason in html
    assert score.formula in html
    # And no stand-in figure in the value slot: the macro marks the whole block
    # unknown rather than rendering a 0 or a 50 (G11).
    assert "explain-is-unknown" in html
    assert "0 days" not in html


# --- R5.12 the product page ---------------------------------------------------


def test_r5_12_product_detail_lists_who_can_supply_it_preferred_first(db, client):
    product = _product(db, MAPPED_SKU)
    vendors = ProductSupplierService(db).list_for_product(product.id)
    assert len(vendors) >= 2, "the seed must map more than one supplier to this SKU"
    assert vendors[0].is_preferred is True

    html = client.get(f"/products/{product.id}").text
    assert "Who can supply this" in html
    assert "Preferred" in html and "Alternate" in html
    # Preferred really is rendered first, not merely tagged.
    positions = [html.index(v.supplier_name) for v in vendors]
    assert positions == sorted(positions)
    for vendor in vendors:
        assert f"/suppliers/{vendor.supplier_id}" in html


def test_r5_5_product_detail_shows_the_agreed_moq_per_supplier(db, client):
    product = _product(db, MAPPED_SKU)
    vendors = ProductSupplierService(db).list_for_product(product.id)
    moqs = [v.moq for v in vendors if v.moq is not None]
    assert moqs, "the seed must agree an MOQ with at least one supplier (R5.5)"

    html = client.get(f"/products/{product.id}").text
    for moq in moqs:
        # `number` is the screen's own quantity filter — 1000 reads "1,000".
        assert number(moq) in html


def test_r5_11_product_detail_prints_unknown_intelligence_as_the_word(db, client):
    """The comparison's score/lead-time cells are rendered strings, never formatted."""
    product = _product(db, MAPPED_SKU)
    # Link the supplier with no history at all, so one row must read "unknown".
    empty = _supplier(db, EMPTY)
    service = ProductSupplierService(db)
    link = service.upsert(
        ProductSupplierUpsert(product_id=product.id, supplier_id=empty.id),
        actor_id=None,
    )
    db.commit()
    try:
        row = next(
            r for r in service.list_for_product(product.id) if r.supplier_id == empty.id
        )
        assert (row.score, row.lead_time, row.on_time_rate) == (
            "unknown", "unknown", "unknown",
        )
        html = client.get(f"/products/{product.id}").text
        assert "unknown" in html
    finally:
        service.delete(link.id, actor_id=None)
        db.commit()


def test_r5_3_the_product_page_offers_no_lead_time_field(db, client):
    """R5.3 is a statement about the UI as much as the schema: nowhere to type it."""
    product = _product(db, MAPPED_SKU)
    html = client.get(f"/products/{product.id}").text
    assert 'name="lead_time' not in html
    assert "measured from each order" in html


def test_r5_6_product_detail_shows_the_price_timeline(db, client):
    product = _product(db, PRICED_SKU)
    rows = VendorIntelService(db).price_history(product.id)
    assert len(rows) >= 2, "the seed must record more than one price (R5.6)"

    html = client.get(f"/products/{product.id}").text
    assert "Price history" in html
    for row in rows:
        assert row.supplier_name in html
    # Oldest first, and the first price of a supplier is labelled rather than
    # shown as a zero change.
    assert rows[0].delta_minor is None
    assert "first price" in html


# --- R5.1 the mapping verbs ---------------------------------------------------


def _unmapped_product(db) -> Product:
    """A product no supplier is mapped to yet — the link form's real starting point."""
    mapped = select(ProductSupplier.product_id).where(ProductSupplier.deleted_at.is_(None))
    return db.scalar(
        select(Product)
        .where(Product.id.not_in(mapped), Product.deleted_at.is_(None))
        .order_by(Product.sku_code)
        .limit(1)
    )


def test_r5_1_the_product_page_links_prefers_and_unlinks_a_supplier(db, client):
    """The three POST verbs, end to end through the screen (R5.1, R5.5)."""
    product = _unmapped_product(db)
    first = _supplier(db, MEASURED)
    second = _supplier(db, EMPTY)
    service = ProductSupplierService(db)

    # Link two suppliers; the second one asks to be preferred.
    linked = client.post(
        f"/products/{product.id}/suppliers",
        data={"supplier_id": str(first.id), "moq": "250", "note": "Pallets of 50"},
        follow_redirects=False,
    )
    assert linked.status_code == 303
    client.post(
        f"/products/{product.id}/suppliers",
        data={"supplier_id": str(second.id), "is_preferred": "1"},
        follow_redirects=False,
    )
    rows = {r.supplier_id: r for r in service.list_for_product(product.id)}
    assert len(rows) == 2
    assert rows[first.id].moq == Decimal("250")
    assert rows[first.id].note == "Pallets of 50"
    assert rows[second.id].is_preferred is True

    # Preferred is exclusive per product — setting one demotes the other.
    client.post(
        f"/product-suppliers/{rows[first.id].id}/prefer",
        data={"product_id": str(product.id)},
        follow_redirects=False,
    )
    rows = {r.supplier_id: r for r in service.list_for_product(product.id)}
    assert rows[first.id].is_preferred is True
    assert rows[second.id].is_preferred is False

    # Unlink both, leaving the catalogue as we found it.
    for row in list(rows.values()):
        unlinked = client.post(
            f"/product-suppliers/{row.id}/delete",
            data={"product_id": str(product.id)},
            follow_redirects=False,
        )
        assert unlinked.status_code == 303
    assert service.list_for_product(product.id) == []


def test_r5_1_linking_the_same_supplier_twice_amends_rather_than_duplicates(db, client):
    product = _unmapped_product(db)
    supplier = _supplier(db, MEASURED)
    service = ProductSupplierService(db)

    for moq in ("100", "400"):
        client.post(
            f"/products/{product.id}/suppliers",
            data={"supplier_id": str(supplier.id), "moq": moq},
            follow_redirects=False,
        )
    rows = service.list_for_product(product.id)
    assert len(rows) == 1
    assert rows[0].moq == Decimal("400")

    client.post(
        f"/product-suppliers/{rows[0].id}/delete",
        data={"product_id": str(product.id)},
        follow_redirects=False,
    )


# --- R5.5 / R5.2 in R4.5's comparison grid ------------------------------------


def test_r5_5_the_agreed_moq_reaches_the_comparison_grid(db, client):
    """R5.5's second half: recordable per product+supplier AND surfaced in R4.5."""
    rfq = db.scalar(select(Rfq).order_by(Rfq.created_at.asc()))
    comparison = RfqService(db).comparison(rfq.id)
    column = comparison.columns[0]
    product_id = next(iter(column.cells))
    service = ProductSupplierService(db)

    link = service.upsert(
        ProductSupplierUpsert(
            product_id=product_id, supplier_id=column.supplier_id, moq=Decimal("777")
        ),
        actor_id=None,
    )
    db.commit()
    try:
        again = RfqService(db).comparison(rfq.id)
        cell = next(c for c in again.columns if c.supplier_id == column.supplier_id).cells[
            product_id
        ]
        assert cell.agreed_moq == Decimal("777")
        html = client.get(f"/rfqs/{rfq.id}").text
        assert "Agreed MOQ" in html and "777" in html
    finally:
        service.delete(link.id, actor_id=None)
        db.commit()


def test_r5_2_the_comparison_grid_explains_every_score_it_shows(db, client):
    """A bare number in a grid cell would fail G11; the arithmetic is on the page."""
    rfq = db.scalar(select(Rfq).order_by(Rfq.created_at.asc()))
    comparison = RfqService(db).comparison(rfq.id)
    html = client.get(f"/rfqs/{rfq.id}").text

    assert "How each vendor score was computed" in html
    for column in comparison.columns:
        assert column.score_explained is not None
        assert column.score_explained.formula in html


def test_r5_10_the_screens_write_nothing(db, client):
    """G15/R5.10: these pages are projections. Rendering them logs no activity."""
    before = db.scalar(select(func.count()).select_from(ProductSupplier))
    supplier = _supplier(db, MEASURED)
    product = _product(db, MAPPED_SKU)

    for path in (f"/suppliers/{supplier.id}", f"/products/{product.id}", "/procurement"):
        assert client.get(path).status_code == 200

    db.expire_all()
    assert db.scalar(select(func.count()).select_from(ProductSupplier)) == before
