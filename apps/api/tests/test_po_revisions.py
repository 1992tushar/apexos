"""Part 3 C2 — PO revisions, partial receipt, back orders, receipt-against-revision.

The C2 half of R4.16: a revision preserves the prior version verbatim (R4.7),
partial receipt leaves the correct back-order quantity (R4.9), and a receipt
against a superseded revision is refused rather than silently accepted (R4.10).
Plus the invariants those rest on — one activity row per verb (G5), the back order
derived and never stored (G7), integer minor units throughout (G1).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, ValidationError
from app.db.references import REFERENCES, blocking_references
from app.modules.activity.models import ActivityLog
from app.modules.procurement.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderRevision,
)
from app.modules.procurement.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptLineInput,
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderRevise,
    PurchaseOrderReviseLine,
)
from app.modules.procurement.service import GoodsReceiptService, PurchaseOrderService
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier

# --- helpers -----------------------------------------------------------------

# Prices are passed explicitly rather than resolved from the seeded purchase
# prices, so the money assertions below are exact rather than incidental.
UNIT = 1250  # ₹12.50 in minor units


def _product(db, offset=0):
    row = list(
        db.scalars(
            select(Product)
            .where(Product.deleted_at.is_(None))
            .order_by(Product.sku_code)
            .offset(offset)
            .limit(1)
        )
    )
    assert row, "the seed must supply a product"
    return row[0]


def _supplier(db):
    row = db.scalar(
        select(Supplier).where(Supplier.deleted_at.is_(None)).order_by(Supplier.code).limit(1)
    )
    assert row is not None, "the seed must supply a supplier"
    return row


def _draft(db, *, qty="100", unit=UNIT, product=None):
    product = product or _product(db)
    return PurchaseOrderService(db).create(
        PurchaseOrderCreate(
            supplier_id=_supplier(db).id,
            order_date=date.today(),
            lines=[
                PurchaseOrderLineCreate(
                    product_id=product.id, qty=Decimal(qty), unit_price_minor=unit
                )
            ],
        ),
        actor_id=None,
    )


def _confirmed(db, **kw):
    po = _draft(db, **kw)
    return PurchaseOrderService(db).confirm(po.id, actor_id=None)


def _log_count(db, entity_type, entity_id, verb=None):
    stmt = (
        select(func.count())
        .select_from(ActivityLog)
        .where(ActivityLog.entity_type == entity_type, ActivityLog.entity_id == entity_id)
    )
    if verb:
        stmt = stmt.where(ActivityLog.verb == verb)
    return db.scalar(stmt) or 0


def _revise(db, order_id, qty, *, reason="supplier reduced the allocation", product=None):
    product = product or _product(db)
    return PurchaseOrderService(db).revise(
        order_id,
        PurchaseOrderRevise(
            reason=reason,
            lines=[PurchaseOrderReviseLine(product_id=product.id, qty=Decimal(qty))],
        ),
        actor_id=None,
    )


def _receive(db, order_id, qty=None, *, against=None, product=None):
    lines = None
    if qty is not None:
        product = product or _product(db)
        lines = [GoodsReceiptLineInput(product_id=product.id, qty=Decimal(qty))]
    return GoodsReceiptService(db).receive(
        order_id,
        GoodsReceiptCreate(lines=lines, against_revision_no=against),
        actor_id=None,
    )


# --- confirm: the R4.11 timestamp and the R4.7 baseline ----------------------


def test_a_draft_has_no_confirm_instant_and_no_revision(db):
    po = _draft(db)
    assert po.confirmed_at is None
    assert po.revision_no == 0
    assert po.revisions == []


def test_confirm_persists_the_instant_part_four_measures_from(db):
    po = _confirmed(db)
    # R4.11 — a real column, not `updated_at`, which the first receipt overwrites.
    assert po.confirmed_at is not None
    row = db.get(PurchaseOrder, po.id)
    assert row.confirmed_at is not None


def test_confirm_writes_revision_one_as_the_agreed_baseline(db):
    po = _confirmed(db, qty="100")
    assert po.revision_no == 1
    assert len(po.revisions) == 1
    v1 = po.revisions[0]
    assert v1.revision_no == 1
    assert v1.is_current is True
    # No reason: nothing was changed, this *is* the agreement.
    assert v1.reason is None
    assert v1.lines[0].qty == Decimal("100")


def test_confirm_still_writes_exactly_one_activity_row(db):
    """The revision snapshot must not smuggle in a second row (G5)."""
    po = _draft(db)
    before = _log_count(db, "purchase_order", po.id)
    PurchaseOrderService(db).confirm(po.id, actor_id=None)
    assert _log_count(db, "purchase_order", po.id, verb="confirmed") == 1
    assert _log_count(db, "purchase_order", po.id) == before + 1


# --- R4.7: a revision appends, and history stays readable verbatim -----------


def test_a_revision_preserves_the_prior_version_verbatim(db):
    """The core R4.7 case: read version 1 back after revising."""
    po = _confirmed(db, qty="100")
    v1_before = po.revisions[0]
    assert v1_before.total_minor == po.total_minor

    revised = _revise(db, po.id, "150", reason="Festive demand — increase the order")

    assert revised.revision_no == 2
    assert len(revised.revisions) == 2
    v1, v2 = revised.revisions[0], revised.revisions[1]

    # Version 1, untouched — quantity, price and every money figure as confirmed.
    assert v1.revision_no == 1
    assert v1.reason is None
    assert v1.lines[0].qty == Decimal("100")
    assert v1.lines[0].unit_price_minor == UNIT
    assert v1.subtotal_minor == v1_before.subtotal_minor
    assert v1.tax_minor == v1_before.tax_minor
    assert v1.total_minor == v1_before.total_minor
    assert v1.is_current is False

    # Version 2 carries the change and the reason for it.
    assert v2.lines[0].qty == Decimal("150")
    assert v2.reason == "Festive demand — increase the order"
    assert v2.is_current is True
    assert v2.subtotal_minor > v1.subtotal_minor

    # And the live order agrees with its current revision.
    assert revised.lines[0].qty == Decimal("150")
    assert revised.total_minor == v2.total_minor


def test_the_confirmed_order_is_not_mutated_in_place(db):
    """R4.7 stated as the negative: revising must not overwrite history."""
    po = _confirmed(db, qty="100")
    original_total = po.total_minor
    _revise(db, po.id, "10")
    stored = list(
        db.scalars(
            select(PurchaseOrderRevision)
            .where(PurchaseOrderRevision.purchase_order_id == po.id)
            .order_by(PurchaseOrderRevision.revision_no)
        )
    )
    assert [r.revision_no for r in stored] == [1, 2]
    assert stored[0].total_minor == original_total  # v1 still says what it said


def test_revisions_accumulate_rather_than_replace(db):
    po = _confirmed(db, qty="100")
    _revise(db, po.id, "90", reason="first cut")
    final = _revise(db, po.id, "80", reason="second cut")
    assert [r.revision_no for r in final.revisions] == [1, 2, 3]
    assert [r.lines[0].qty for r in final.revisions] == [
        Decimal("100"), Decimal("90"), Decimal("80")
    ]
    assert [r.reason for r in final.revisions] == [None, "first cut", "second cut"]
    assert final.revisions[-1].is_current is True


def test_a_revision_writes_exactly_one_activity_row(db):
    po = _confirmed(db, qty="100")
    before = _log_count(db, "purchase_order", po.id)
    _revise(db, po.id, "120")
    assert _log_count(db, "purchase_order", po.id, verb="revised") == 1
    assert _log_count(db, "purchase_order", po.id) == before + 1


def test_the_revision_activity_row_carries_the_reason(db):
    po = _confirmed(db, qty="100")
    _revise(db, po.id, "120", reason="Supplier raised the minimum")
    row = db.scalar(
        select(ActivityLog).where(
            ActivityLog.entity_id == po.id, ActivityLog.verb == "revised"
        )
    )
    assert row.data["reason"] == "Supplier raised the minimum"
    assert row.data["revision_no"] == 2
    assert "Supplier raised the minimum" in row.summary


def test_a_revision_needs_a_reason(db):
    po = _confirmed(db)
    with pytest.raises(ValidationError):
        PurchaseOrderService(db).revise(
            po.id,
            PurchaseOrderRevise(
                reason="   ",
                lines=[PurchaseOrderReviseLine(product_id=_product(db).id, qty=Decimal("5"))],
            ),
            actor_id=None,
        )


def test_a_draft_cannot_be_revised(db):
    po = _draft(db)
    with pytest.raises(ConflictError) as err:
        _revise(db, po.id, "50")
    assert "draft" in str(err.value)


def test_a_revision_can_add_a_product_that_was_not_ordered(db):
    first, second = _product(db, 0), _product(db, 1)
    po = _confirmed(db, qty="100", product=first)
    revised = PurchaseOrderService(db).revise(
        po.id,
        PurchaseOrderRevise(
            reason="Add the matching consumable",
            lines=[
                PurchaseOrderReviseLine(
                    product_id=second.id, qty=Decimal("20"), unit_price_minor=500
                )
            ],
        ),
        actor_id=None,
    )
    assert len(revised.lines) == 2
    # The untouched line keeps its quantity; the new one is priced as passed.
    by_product = {ln.product_id: ln for ln in revised.lines}
    assert by_product[first.id].qty == Decimal("100")
    assert by_product[second.id].qty == Decimal("20")
    assert by_product[second.id].unit_price_minor == 500
    assert len(revised.revisions[-1].lines) == 2


def test_revision_money_is_exact_integer_minor_units(db):
    """G1 — no float anywhere in the revision's arithmetic."""
    po = _confirmed(db, qty="3", unit=333)
    revised = _revise(db, po.id, "7")
    line = revised.lines[0]
    assert line.line_subtotal_minor == 7 * 333
    expected_tax = (7 * 333) * line.tax_rate_bps // 10000
    # Integer arithmetic, so at most the rounding step separates these.
    assert abs(line.line_tax_minor - expected_tax) <= 1
    assert line.line_total_minor == line.line_subtotal_minor + line.line_tax_minor
    assert revised.total_minor == line.line_total_minor
    assert isinstance(revised.total_minor, int)


# --- R4.9: the back order, derived --------------------------------------------


def test_partial_receipt_leaves_the_correct_back_order(db):
    po = _confirmed(db, qty="100")
    after = _receive(db, po.id, "40")
    line = after.lines[0]
    assert line.qty_received == Decimal("40")
    assert line.open_qty == Decimal("60")  # 100 − 40
    assert after.open_qty_total == Decimal("60")
    assert after.status == "partially_received"


def test_the_back_order_tracks_each_further_receipt(db):
    po = _confirmed(db, qty="100")
    assert _receive(db, po.id, "40").open_qty_total == Decimal("60")
    assert _receive(db, po.id, "35").open_qty_total == Decimal("25")
    final = _receive(db, po.id, "25")
    assert final.open_qty_total == Decimal("0")
    assert final.status == "received"


def test_the_back_order_is_derived_and_never_stored(db):
    """G7 — there must be no column holding it, or the two can disagree."""
    stored = set(PurchaseOrderLine.__table__.columns.keys())
    for forbidden in ("open_qty", "qty_open", "back_order_qty", "qty_outstanding"):
        assert forbidden not in stored
    # It is computed from the two persisted figures, every read.
    po = _confirmed(db, qty="100")
    _receive(db, po.id, "40")
    row = db.get(PurchaseOrder, po.id)
    line = row.lines[0]
    assert PurchaseOrderService.open_qty(line) == Decimal(line.qty) - Decimal(line.qty_received)


def test_the_back_order_never_reads_negative(db):
    """A revision down to what arrived reads as nothing outstanding, not as −n."""
    po = _confirmed(db, qty="100")
    _receive(db, po.id, "40")
    closed = _revise(db, po.id, "40", reason="Balance cancelled")
    assert closed.lines[0].open_qty == Decimal("0")
    assert closed.open_qty_total == Decimal("0")
    assert closed.status == "received"


def test_a_revision_cannot_cut_a_line_below_what_arrived(db):
    po = _confirmed(db, qty="100")
    _receive(db, po.id, "40")
    with pytest.raises(ValidationError) as err:
        _revise(db, po.id, "30")
    message = str(err.value)
    assert "already been received" in message
    # Quantities read as a person writes them — `Numeric(18, 4)` would say 40.0000.
    assert "40 has already been received" in message
    assert "40.0000" not in message


def test_a_received_order_cannot_be_revised(db):
    po = _confirmed(db, qty="50")
    received = _receive(db, po.id)  # everything outstanding
    assert received.status == "received"
    with pytest.raises(ConflictError):
        _revise(db, po.id, "80")


# --- R4.10: which revision a receipt was taken against -----------------------


def test_a_receipt_records_the_revision_it_was_taken_against(db):
    po = _confirmed(db, qty="100")
    after = _receive(db, po.id, "40")
    assert after.goods_receipts[0].revision_no == 1


def test_a_receipt_after_a_revision_records_the_new_version(db):
    po = _confirmed(db, qty="100")
    _revise(db, po.id, "120")
    after = _receive(db, po.id, "10")
    assert after.goods_receipts[-1].revision_no == 2


def test_a_receipt_against_a_superseded_revision_is_refused(db):
    """R4.10 — explicitly handled, not silently accepted."""
    po = _confirmed(db, qty="100")
    _revise(db, po.id, "60", reason="Supplier cut the allocation")
    with pytest.raises(ConflictError) as err:
        _receive(db, po.id, "50", against=1)
    message = str(err.value)
    assert "revision 2" in message  # where the order actually is
    assert "revision 1" in message  # what the receipt claimed
    assert po.po_no in message


def test_a_refused_receipt_posts_no_stock_and_no_receipt(db):
    po = _confirmed(db, qty="100")
    _revise(db, po.id, "60")
    with pytest.raises(ConflictError):
        _receive(db, po.id, "50", against=1)
    fresh = PurchaseOrderService(db).get(po.id)
    assert fresh.goods_receipts == []
    assert fresh.lines[0].qty_received == Decimal("0")
    assert fresh.lines[0].open_qty == Decimal("60")


def test_a_receipt_naming_the_current_revision_is_accepted(db):
    po = _confirmed(db, qty="100")
    revised = _revise(db, po.id, "60")
    after = _receive(db, po.id, "20", against=revised.revision_no)
    assert after.lines[0].qty_received == Decimal("20")
    assert after.lines[0].open_qty == Decimal("40")
    assert after.goods_receipts[0].revision_no == 2


def test_a_receipt_naming_no_revision_still_works(db):
    """An unrevised PO's receive form has nothing to check against."""
    po = _confirmed(db, qty="100")
    after = _receive(db, po.id, "40", against=None)
    assert after.lines[0].qty_received == Decimal("40")
    assert after.goods_receipts[0].revision_no == 1


# --- R3.7: the new tables are declared, and the declaration works ------------


def test_the_revision_tables_are_declared_in_references(db):
    """C1's lesson: reading the map is not enough — exercise it.

    A missing key means "not yet considered", which is how the warehouse row went
    five checkpoints raising AttributeError instead of refusing.
    """
    for table in ("purchase_order_revision", "purchase_order_revision_line"):
        assert table in REFERENCES, f"{table} owes references.py an entry (R3.7)"

    po = _confirmed(db, qty="10")
    revision = db.scalar(
        select(PurchaseOrderRevision).where(PurchaseOrderRevision.purchase_order_id == po.id)
    )
    # Runs the real check rather than trusting the empty tuple by inspection.
    assert blocking_references(db, revision) == []


# --- the screen (R4.9 / R4.7 visible) ----------------------------------------


def test_the_seeded_revised_po_shows_its_history_and_back_order(client, api_prefix):
    """R4.15 — the seed leaves a revised PO with a live back order, and the detail
    page renders both."""
    listing = client.get(f"{api_prefix}/purchase-orders", params={"page_size": 200}).json()
    revised = None
    for row in listing["items"]:
        detail = client.get(f"{api_prefix}/purchase-orders/{row['id']}").json()
        if detail["revision_no"] >= 2:
            revised = detail
            break
    assert revised is not None, "the seed must leave a revised PO (R4.15)"
    assert Decimal(revised["open_qty_total"]) > 0, "and one with an outstanding back order"
    assert revised["confirmed_at"] is not None
    assert revised["revisions"][0]["reason"] is None
    assert revised["revisions"][-1]["reason"]

    page = client.get(f"/purchase-orders/{revised['id']}")
    assert page.status_code == 200
    html = page.text
    assert "Revision history" in html
    assert "Back order" in html
    assert f"Version {revised['revision_no']}" in html
    # The superseded version is still on the page, readable.
    assert "Version 1" in html
