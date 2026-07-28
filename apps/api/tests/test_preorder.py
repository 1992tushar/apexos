"""Part 3 C1 — the pre-order flow: requisition → RFQ → quotation → PO.

Covers the C1 half of R4.16: requisition→PO conversion, approval writing exactly
one activity_log row, the RFQ→quote comparison pick, and the guards that keep the
flow honest. R4.7–R4.11 (revisions, partial receipt, back orders) are C2's tests.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.activity.models import ActivityLog
from app.modules.procurement.models import (
    PurchaseRequisition,
    Rfq,
    SupplierQuotation,
)
from app.modules.procurement.preorder import RequisitionService, RfqService
from app.modules.procurement.schemas import (
    QuotationCreate,
    QuotationLineInput,
    RequisitionCreate,
    RequisitionLineCreate,
    RfqCreate,
    RfqLineCreate,
)
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier

# --- helpers -----------------------------------------------------------------


def _products(db, count=2):
    rows = list(
        db.scalars(
            select(Product)
            .where(Product.deleted_at.is_(None))
            .order_by(Product.sku_code)
            .limit(count)
        )
    )
    assert len(rows) == count, "the seed must supply enough products"
    return rows


def _suppliers(db, count=2):
    rows = list(
        db.scalars(
            select(Supplier)
            .where(Supplier.deleted_at.is_(None))
            .order_by(Supplier.code)
            .limit(count)
        )
    )
    assert len(rows) == count, "the seed must supply enough suppliers"
    return rows


def _raise_requisition(db, *, qty="10", products=None):
    items = products or _products(db, 2)
    return RequisitionService(db).create(
        RequisitionCreate(
            needed_by=date.today() + timedelta(days=14),
            note="test requisition",
            lines=[
                RequisitionLineCreate(product_id=p.id, qty=Decimal(qty)) for p in items
            ],
        ),
        actor_id=None,
    )


def _log_count(db, entity_type, entity_id, verb=None):
    stmt = select(func.count()).select_from(ActivityLog).where(
        ActivityLog.entity_type == entity_type, ActivityLog.entity_id == entity_id
    )
    if verb:
        stmt = stmt.where(ActivityLog.verb == verb)
    return db.scalar(stmt) or 0


def _issue_rfq(db, *, products=None, suppliers=None, qty="100"):
    items = products or _products(db, 1)
    vendors = suppliers or _suppliers(db, 2)
    return RfqService(db).issue(
        RfqCreate(
            supplier_ids=[s.id for s in vendors],
            due_date=date.today() + timedelta(days=7),
            note="test rfq",
            lines=[RfqLineCreate(product_id=p.id, qty=Decimal(qty)) for p in items],
        ),
        actor_id=None,
    )


# --- requisition: request → approve → convert (R4.1, R4.2) -------------------


def test_a_requisition_starts_awaiting_approval(db):
    req = _raise_requisition(db)
    assert req.status == "requested"
    assert req.requisition_no.startswith("REQ-")
    assert len(req.lines) == 2
    assert req.approved_at is None and req.approval_reason is None


def test_raising_a_requisition_writes_exactly_one_log_row(db):
    req = _raise_requisition(db)
    assert _log_count(db, "purchase_requisition", req.id) == 1
    assert _log_count(db, "purchase_requisition", req.id, "requested") == 1


def test_approval_records_the_actor_and_reason_and_writes_one_row(db):
    """R4.2: exactly one row, and the decision is readable off the requisition."""
    req = _raise_requisition(db)
    actor = uuid.UUID("00000000-0000-7000-8000-000000000001")
    approved = RequisitionService(db).approve(
        req.id, reason="Budget approved for Q3", actor_id=actor
    )
    assert approved.status == "approved"
    assert approved.approval_reason == "Budget approved for Q3"
    assert approved.approved_at is not None
    # The 'requested' row plus exactly one 'approved' row — no more.
    assert _log_count(db, "purchase_requisition", req.id, "approved") == 1
    assert _log_count(db, "purchase_requisition", req.id) == 2


def test_approval_without_a_reason_is_refused(db):
    req = _raise_requisition(db)
    with pytest.raises(ValidationError):
        RequisitionService(db).approve(req.id, reason="   ", actor_id=None)


def test_a_rejected_requisition_cannot_then_be_approved(db):
    req = _raise_requisition(db)
    service = RequisitionService(db)
    rejected = service.reject(req.id, reason="Not this quarter", actor_id=None)
    assert rejected.status == "rejected"
    with pytest.raises(ConflictError):
        service.approve(req.id, reason="Changed my mind", actor_id=None)


def test_converting_an_unapproved_requisition_is_refused(db):
    req = _raise_requisition(db)
    supplier = _suppliers(db, 1)[0]
    with pytest.raises(ConflictError) as exc:
        RequisitionService(db).convert_to_po(
            req.id, supplier_id=supplier.id, actor_id=None
        )
    assert "approve it first" in exc.value.message


def test_requisition_converts_to_a_purchase_order_carrying_its_lines(db):
    """R4.16: the conversion, and that it reuses PurchaseOrderService (G16)."""
    items = _products(db, 2)
    req = _raise_requisition(db, qty="7", products=items)
    service = RequisitionService(db)
    service.approve(req.id, reason="Needed for a customer order", actor_id=None)
    po = service.convert_to_po(
        req.id, supplier_id=_suppliers(db, 1)[0].id, actor_id=None
    )

    assert po.po_no.startswith("PO-")
    assert po.status == "draft"
    assert {ln.product_id for ln in po.lines} == {p.id for p in items}
    assert all(ln.qty == Decimal("7") for ln in po.lines)
    # Prices came from PurchaseOrderService, not from the requisition.
    assert all(ln.unit_price_minor > 0 for ln in po.lines)
    assert po.total_minor == sum(ln.line_total_minor for ln in po.lines)

    after = service.get(req.id)
    assert after.status == "converted"
    assert after.purchase_order_id == po.id
    assert after.po_no == po.po_no
    assert _log_count(db, "purchase_requisition", req.id, "converted") == 1


def test_a_converted_requisition_cannot_be_converted_twice(db):
    req = _raise_requisition(db)
    service = RequisitionService(db)
    service.approve(req.id, reason="ok", actor_id=None)
    supplier = _suppliers(db, 1)[0]
    service.convert_to_po(req.id, supplier_id=supplier.id, actor_id=None)
    with pytest.raises(ConflictError) as exc:
        service.convert_to_po(req.id, supplier_id=supplier.id, actor_id=None)
    assert "already been converted" in exc.value.message


def test_requisition_converts_to_an_rfq_with_the_same_lines(db):
    items = _products(db, 2)
    vendors = _suppliers(db, 2)
    req = _raise_requisition(db, qty="250", products=items)
    service = RequisitionService(db)
    service.approve(req.id, reason="No agreed price yet", actor_id=None)
    rfq = service.convert_to_rfq(
        req.id, supplier_ids=[s.id for s in vendors], actor_id=None
    )

    assert rfq.rfq_no.startswith("RFQ-")
    assert rfq.status == "issued"
    assert {ln.product_id for ln in rfq.lines} == {p.id for p in items}
    assert {s.supplier_id for s in rfq.suppliers} == {s.id for s in vendors}
    assert rfq.requisition_no == req.requisition_no

    after = service.get(req.id)
    assert after.status == "converted" and after.rfq_id == rfq.id


# --- RFQ + quotations (R4.3, R4.4) -------------------------------------------


def test_an_rfq_is_issued_to_several_suppliers_at_once(db):
    vendors = _suppliers(db, 2)
    rfq = _issue_rfq(db, suppliers=vendors)
    assert len(rfq.suppliers) == 2
    assert all(s.status == "invited" for s in rfq.suppliers)
    assert all(s.supplier_name for s in rfq.suppliers)
    assert _log_count(db, "rfq", rfq.id, "issued") == 1


def test_the_same_supplier_asked_twice_is_one_invitation(db):
    supplier = _suppliers(db, 1)[0]
    product = _products(db, 1)[0]
    rfq = RfqService(db).issue(
        RfqCreate(
            supplier_ids=[supplier.id, supplier.id],
            lines=[RfqLineCreate(product_id=product.id, qty=Decimal("5"))],
        ),
        actor_id=None,
    )
    assert len(rfq.suppliers) == 1


def test_capturing_a_quote_prices_the_lines_in_integer_minor_units(db):
    """G1: no float anywhere in the money path; tax is bps off the line subtotal."""
    product = _products(db, 1)[0]
    rfq = _issue_rfq(db, products=[product], qty="20")
    quote = RfqService(db).capture_quote(
        rfq.id,
        QuotationCreate(
            supplier_id=rfq.suppliers[0].supplier_id,
            lead_time_days=9,
            lines=[QuotationLineInput(product_id=product.id, unit_price_minor=1250)],
        ),
        actor_id=None,
    )
    line = quote.lines[0]
    assert isinstance(line.line_subtotal_minor, int)
    assert line.qty == Decimal("20")  # defaulted from the RFQ line
    assert line.line_subtotal_minor == 20 * 1250
    expected_tax = line.line_subtotal_minor * line.tax_rate_bps // 10000
    assert abs(line.line_tax_minor - expected_tax) <= 1  # rounding, still integral
    assert line.line_total_minor == line.line_subtotal_minor + line.line_tax_minor
    assert quote.total_minor == line.line_total_minor
    assert quote.lead_time_days == 9


def test_capturing_a_quote_marks_the_invitation_quoted_and_logs_once(db):
    rfq = _issue_rfq(db)
    supplier_id = rfq.suppliers[0].supplier_id
    product_id = rfq.lines[0].product_id
    RfqService(db).capture_quote(
        rfq.id,
        QuotationCreate(
            supplier_id=supplier_id,
            lines=[QuotationLineInput(product_id=product_id, unit_price_minor=900)],
        ),
        actor_id=None,
    )
    after = RfqService(db).get(rfq.id)
    statuses = {s.supplier_id: s.status for s in after.suppliers}
    assert statuses[supplier_id] == "quoted"
    assert _log_count(db, "rfq", rfq.id, "quoted") == 1


def test_a_supplier_cannot_quote_the_same_rfq_twice(db):
    """D3: a revised price is a new RFQ, not an edit of the quote on file."""
    rfq = _issue_rfq(db)
    service = RfqService(db)
    supplier_id = rfq.suppliers[0].supplier_id
    product_id = rfq.lines[0].product_id
    payload = QuotationCreate(
        supplier_id=supplier_id,
        lines=[QuotationLineInput(product_id=product_id, unit_price_minor=900)],
    )
    service.capture_quote(rfq.id, payload, actor_id=None)
    with pytest.raises(ConflictError) as exc:
        service.capture_quote(rfq.id, payload, actor_id=None)
    assert "already quoted" in exc.value.message


def test_quoting_a_product_that_is_not_on_the_rfq_is_refused(db):
    items = _products(db, 2)
    rfq = _issue_rfq(db, products=[items[0]])
    with pytest.raises(ValidationError) as exc:
        RfqService(db).capture_quote(
            rfq.id,
            QuotationCreate(
                supplier_id=rfq.suppliers[0].supplier_id,
                lines=[QuotationLineInput(product_id=items[1].id, unit_price_minor=500)],
            ),
            actor_id=None,
        )
    assert items[1].sku_code in exc.value.message


# --- the comparison + the pick (R4.5, R4.14, G11) ----------------------------


def _rfq_with_two_quotes(db):
    """One product, two quotes: cheaper unit price but a slower, larger-MOQ supplier."""
    product = _products(db, 1)[0]
    rfq = _issue_rfq(db, products=[product], qty="100")
    service = RfqService(db)
    fast, cheap = rfq.suppliers[0].supplier_id, rfq.suppliers[1].supplier_id
    service.capture_quote(
        rfq.id,
        QuotationCreate(
            supplier_id=fast,
            lead_time_days=5,
            lines=[
                QuotationLineInput(
                    product_id=product.id, unit_price_minor=1000, moq=Decimal("50")
                )
            ],
        ),
        actor_id=None,
    )
    service.capture_quote(
        rfq.id,
        QuotationCreate(
            supplier_id=cheap,
            lead_time_days=20,
            lines=[
                QuotationLineInput(
                    product_id=product.id, unit_price_minor=800, moq=Decimal("500")
                )
            ],
        ),
        actor_id=None,
    )
    return rfq, product, fast, cheap


def test_the_comparison_shows_price_lead_time_and_moq_per_supplier(db):
    rfq, product, fast, cheap = _rfq_with_two_quotes(db)
    cmp = RfqService(db).comparison(rfq.id)

    assert len(cmp.columns) == 2
    by_supplier = {c.supplier_id: c for c in cmp.columns}
    assert by_supplier[cheap].cells[product.id].unit_price_minor == 800
    assert by_supplier[fast].cells[product.id].unit_price_minor == 1000
    assert by_supplier[cheap].cells[product.id].moq == Decimal("500")
    assert by_supplier[fast].lead_time_days == 5
    # The trade-off is visible: cheapest is not fastest.
    assert by_supplier[cheap].cells[product.id].is_cheapest is True
    assert by_supplier[fast].cells[product.id].is_cheapest is False
    assert by_supplier[cheap].is_cheapest_total is True
    assert by_supplier[fast].is_fastest is True
    assert by_supplier[cheap].is_fastest is False


def test_the_comparison_says_unknown_for_score_rather_than_inventing_one(db):
    """R4.14 + G11: part 4 owns scoring; a placeholder number would mislead."""
    rfq, *_ = _rfq_with_two_quotes(db)
    cmp = RfqService(db).comparison(rfq.id)
    assert all(c.score is None for c in cmp.columns)
    assert "part 4" in cmp.score_note


def test_the_comparison_names_suppliers_that_have_not_answered(db):
    rfq = _issue_rfq(db)
    product_id = rfq.lines[0].product_id
    RfqService(db).capture_quote(
        rfq.id,
        QuotationCreate(
            supplier_id=rfq.suppliers[0].supplier_id,
            lines=[QuotationLineInput(product_id=product_id, unit_price_minor=700)],
        ),
        actor_id=None,
    )
    cmp = RfqService(db).comparison(rfq.id)
    assert len(cmp.columns) == 1
    assert len(cmp.invited_not_quoted) == 1


def test_reading_the_comparison_writes_no_activity_rows(db):
    """G15: a projection owns no entities."""
    rfq, *_ = _rfq_with_two_quotes(db)
    before = _log_count(db, "rfq", rfq.id)
    RfqService(db).comparison(rfq.id)
    RfqService(db).get(rfq.id)
    assert _log_count(db, "rfq", rfq.id) == before


def test_awarding_a_quotation_creates_a_po_at_the_quoted_prices(db):
    """R4.16: the comparison pick becomes a purchase order, quoted price intact."""
    rfq, product, _fast, cheap = _rfq_with_two_quotes(db)
    service = RfqService(db)
    winner = next(
        c for c in service.comparison(rfq.id).columns if c.supplier_id == cheap
    )
    po = service.award(rfq.id, winner.quotation_id, actor_id=None)

    assert po.supplier_id == cheap
    assert len(po.lines) == 1
    assert po.lines[0].unit_price_minor == 800  # the quoted price, not the list price
    assert po.lines[0].qty == Decimal("100")
    assert po.lines[0].line_subtotal_minor == 100 * 800

    after = service.get(rfq.id)
    assert after.status == "awarded"
    assert after.awarded_quotation_id == winner.quotation_id
    awarded = next(q for q in after.quotations if q.id == winner.quotation_id)
    assert awarded.status == "awarded" and awarded.po_no == po.po_no
    assert _log_count(db, "rfq", rfq.id, "awarded") == 1


def test_the_losing_quotations_are_left_exactly_as_received(db):
    """No state change without a decision behind it — the award is on the RFQ."""
    rfq, _product, fast, cheap = _rfq_with_two_quotes(db)
    service = RfqService(db)
    winner = next(c for c in service.comparison(rfq.id).columns if c.supplier_id == cheap)
    service.award(rfq.id, winner.quotation_id, actor_id=None)
    loser = next(q for q in service.get(rfq.id).quotations if q.supplier_id == fast)
    assert loser.status == "received"
    assert loser.purchase_order_id is None


def test_an_awarded_rfq_takes_no_further_quotes_and_no_second_award(db):
    rfq, product, _fast, cheap = _rfq_with_two_quotes(db)
    service = RfqService(db)
    columns = service.comparison(rfq.id).columns
    winner = next(c for c in columns if c.supplier_id == cheap)
    runner_up = next(c for c in columns if c.supplier_id != cheap)
    service.award(rfq.id, winner.quotation_id, actor_id=None)

    with pytest.raises(ConflictError):
        service.award(rfq.id, runner_up.quotation_id, actor_id=None)
    with pytest.raises(ConflictError):
        service.capture_quote(
            rfq.id,
            QuotationCreate(
                supplier_id=_suppliers(db, 3)[2].id,
                lines=[QuotationLineInput(product_id=product.id, unit_price_minor=1)],
            ),
            actor_id=None,
        )


def test_awarding_a_quotation_from_another_rfq_is_refused(db):
    first, product, _fast, cheap = _rfq_with_two_quotes(db)
    other = _issue_rfq(db, products=[product])
    service = RfqService(db)
    winner = next(c for c in service.comparison(first.id).columns if c.supplier_id == cheap)
    with pytest.raises(NotFoundError):
        service.award(other.id, winner.quotation_id, actor_id=None)


# --- quotation history (R4.6) ------------------------------------------------


def test_quotation_history_lists_every_price_a_product_was_quoted(db):
    rfq, product, fast, cheap = _rfq_with_two_quotes(db)
    rows = RfqService(db).quotation_history(product.id)
    quoted = {(r.supplier_id, r.unit_price_minor) for r in rows}
    assert (cheap, 800) in quoted
    assert (fast, 1000) in quoted
    assert all(r.quotation_no for r in rows)
    assert any(r.rfq_no == rfq.rfq_no for r in rows)


def test_quotation_history_can_be_narrowed_to_one_supplier(db):
    _rfq, product, _fast, cheap = _rfq_with_two_quotes(db)
    rows = RfqService(db).quotation_history(product.id, supplier_id=cheap)
    assert rows and all(r.supplier_id == cheap for r in rows)


def test_a_product_never_quoted_has_an_empty_history(db):
    lonely = db.scalar(
        select(Product)
        .where(Product.deleted_at.is_(None))
        .order_by(Product.sku_code.desc())
        .limit(1)
    )
    assert RfqService(db).quotation_history(lonely.id) == []


# --- relationship integrity for the new models (R3.7) -----------------------


def test_every_new_preorder_model_has_a_references_entry(db):
    """R3.7: a model missing from the map silently permits deleting live work."""
    from app.db.references import REFERENCES

    for model in (
        PurchaseRequisition,
        Rfq,
        SupplierQuotation,
    ):
        assert model.__tablename__ in REFERENCES, model.__tablename__
    for table in (
        "purchase_requisition_line",
        "rfq_line",
        "rfq_supplier",
        "supplier_quotation",
        "supplier_quotation_line",
    ):
        assert table in REFERENCES, table


def test_an_open_requisition_blocks_retiring_the_product_it_names(db):
    from app.db.references import blocking_references

    product = _products(db, 1)[0]
    req = _raise_requisition(db, products=[product])
    phrases = blocking_references(db, product)
    assert any(req.requisition_no in p for p in phrases), phrases


def test_a_converted_requisition_no_longer_blocks_the_product(db):
    """Closed pre-order work is history — R1.7's reasoning, applied to requisitions."""
    from app.db.references import blocking_references

    product = _products(db, 1)[0]
    req = _raise_requisition(db, products=[product])
    service = RequisitionService(db)
    service.reject(req.id, reason="Ordered elsewhere", actor_id=None)
    phrases = blocking_references(db, product)
    assert not any(req.requisition_no in p for p in phrases), phrases


def test_a_warehouse_reference_check_does_not_raise(db):
    """Regression: the map named `PurchaseOrder.warehouse_id`, a column that does
    not exist, so every warehouse deactivation died with an AttributeError instead
    of a refusal. The reference now reaches the warehouse through the goods receipt."""
    from app.db.references import blocking_references
    from app.modules.config.models import Warehouse

    warehouse = db.scalar(
        select(Warehouse).where(Warehouse.deleted_at.is_(None)).limit(1)
    )
    phrases = blocking_references(db, warehouse)
    assert isinstance(phrases, list)
    # The seeded Pune warehouse holds the opening stock, so it is genuinely blocked.
    assert any("stock movement" in p for p in phrases), phrases


# --- the screens (R4.13) ----------------------------------------------------


def _list_body(html: str) -> str:
    """The rows of the *list* table. These pages carry a second `<tbody>` above it —
    the bulk line-entry grid — so the list is the last one."""
    return html.rsplit("<tbody>", 1)[1].split("</tbody>")[0]


def test_the_requisition_list_is_the_shared_machinery(db, client):
    html = client.get("/requisitions").text
    # Markers only the shared macros emit: a page that grew its own table fails here.
    assert 'class="list-toolbar"' in html  # R2.1's toolbar, not a hand-rolled filter
    assert 'class="sort-arrow"' in html  # sortable headers built from the spec
    assert 'class="pagination-count"' in html
    assert "Export CSV" in html
    # Exactly two tables: the entry grid in the form, and the one list table.
    assert html.count("<tbody>") == 2
    assert "REQ-" in _list_body(html)


def test_the_requisition_list_filters_by_status(db, client):
    filtered = client.get("/requisitions?status=requested").text
    assert 'class="filter-chips"' in filtered
    assert "converted" not in _list_body(filtered)


def _shown_total(html: str) -> int:
    """The `Showing 1–25 of N` count the paginator renders. Read from the page rather
    than counting `<tr>`s: an empty list renders no table at all, and these pages
    carry a second table (the entry grid) that a naive count would pick up."""
    match = re.search(r"of ([\d,]+)\s*</div>", html)
    return int(match.group(1).replace(",", "")) if match else 0


def test_the_requisition_export_matches_the_screen(db, client):
    """R2.8: a filtered export is the same query with pagination removed."""
    page = client.get("/requisitions?status=requested")
    rows = _shown_total(page.text)
    assert rows > 0, "the seed leaves a requisition awaiting approval"

    csv = client.get("/requisitions?status=requested&export=csv")
    assert csv.status_code == 200
    body = csv.content.decode("utf-8-sig").strip().splitlines()
    assert len(body) - 1 == rows  # minus the header row
    assert body[0].startswith("Requisition,Status")

    unfiltered = client.get("/requisitions?export=csv")
    all_rows = unfiltered.content.decode("utf-8-sig").strip().splitlines()
    assert len(all_rows) > len(body)


def test_the_rfq_list_renders_through_the_macros(db, client):
    html = client.get("/rfqs").text
    assert 'class="list-toolbar"' in html
    assert 'class="sort-arrow"' in html
    assert html.count("<tbody>") == 2  # the entry grid, then the list
    assert "RFQ-" in _list_body(html)


def test_the_seeded_requisition_awaiting_approval_offers_a_decision(db, client):
    """R4.15: the fresh-DB screen has something to act on."""
    req = db.scalar(
        select(PurchaseRequisition).where(PurchaseRequisition.status == "requested")
    )
    assert req is not None, "the seed must leave one requisition awaiting approval"
    html = client.get(f"/requisitions/{req.id}").text
    assert f"/requisitions/{req.id}/approve" in html
    assert f"/requisitions/{req.id}/reject" in html
    assert "Requisition history" in html


def test_the_seeded_rfq_renders_the_comparison_with_both_quotes(db, client):
    rfq = db.scalar(select(Rfq).order_by(Rfq.created_at.asc()))
    assert rfq is not None, "the seed must issue one RFQ"
    html = client.get(f"/rfqs/{rfq.id}").text
    quotes = db.scalars(
        select(SupplierQuotation).where(SupplierQuotation.rfq_id == rfq.id)
    ).all()
    assert len(quotes) == 2
    for quote in quotes:
        assert quote.quotation_no in html
    assert "cheapest" in html and "fastest" in html
    assert "unknown" in html  # the score, honestly labelled
    assert f"/rfqs/{rfq.id}/award" in html


def test_the_product_detail_page_shows_its_quoted_prices(db, client):
    """R4.6 on the screen the founder is already looking at."""
    quote_line_product = db.scalar(
        select(SupplierQuotation.id).limit(1)
    )
    assert quote_line_product is not None
    quote = RfqService(db).get(
        db.scalar(select(Rfq.id).order_by(Rfq.created_at.asc()))
    )
    product_id = quote.lines[0].product_id
    html = client.get(f"/products/{product_id}").text
    assert "Quoted prices" in html
    assert "MOQ" in html


def test_an_unknown_requisition_id_renders_the_error_page(db, client):
    response = client.get(f"/requisitions/{uuid.uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.text.lower()


def test_the_bulk_entry_form_reports_an_unknown_sku_instead_of_dropping_it(db, client):
    """The picker is free text, so a typo must be named, never silently ignored."""
    response = client.post(
        "/requisitions",
        data={"product_code": ["NOPE-999"], "qty": ["5"], "note": "typo test"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "NOPE-999" in response.headers["location"]


# --- the API surface --------------------------------------------------------


def test_the_api_walks_requisition_to_po(db, client, api_prefix):
    items = _products(db, 1)
    supplier = _suppliers(db, 1)[0]
    created = client.post(
        f"{api_prefix}/requisitions",
        json={
            "note": "api walk",
            "lines": [{"product_id": str(items[0].id), "qty": "3"}],
        },
    )
    assert created.status_code == 201, created.text
    req_id = created.json()["id"]

    approved = client.post(
        f"{api_prefix}/requisitions/{req_id}/approve", json={"reason": "api approval"}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval_reason"] == "api approval"

    converted = client.post(
        f"{api_prefix}/requisitions/{req_id}/convert-to-po",
        json={"supplier_id": str(supplier.id)},
    )
    assert converted.status_code == 201, converted.text
    assert converted.json()["po_no"].startswith("PO-")


def test_the_api_compares_and_awards_an_rfq(db, client, api_prefix):
    items = _products(db, 1)
    vendors = _suppliers(db, 2)
    issued = client.post(
        f"{api_prefix}/rfqs",
        json={
            "supplier_ids": [str(s.id) for s in vendors],
            "lines": [{"product_id": str(items[0].id), "qty": "40"}],
        },
    )
    assert issued.status_code == 201, issued.text
    rfq_id = issued.json()["id"]

    for supplier, price, lead in ((vendors[0], 1500, 4), (vendors[1], 1400, 12)):
        quoted = client.post(
            f"{api_prefix}/rfqs/{rfq_id}/quotations",
            json={
                "supplier_id": str(supplier.id),
                "lead_time_days": lead,
                "lines": [
                    {"product_id": str(items[0].id), "unit_price_minor": price}
                ],
            },
        )
        assert quoted.status_code == 201, quoted.text

    comparison = client.get(f"{api_prefix}/rfqs/{rfq_id}/comparison").json()
    assert len(comparison["columns"]) == 2
    assert all(c["score"] is None for c in comparison["columns"])
    cheapest = next(c for c in comparison["columns"] if c["is_cheapest_total"])
    assert cheapest["supplier_id"] == str(vendors[1].id)

    awarded = client.post(
        f"{api_prefix}/rfqs/{rfq_id}/award",
        json={"quotation_id": cheapest["quotation_id"]},
    )
    assert awarded.status_code == 201, awarded.text
    assert awarded.json()["lines"][0]["unit_price_minor"] == 1400


def test_the_api_serves_quotation_history_for_a_product(db, client, api_prefix):
    _rfq, product, _fast, cheap = _rfq_with_two_quotes(db)
    db.commit()
    rows = client.get(f"{api_prefix}/products/{product.id}/quotations").json()
    assert any(r["unit_price_minor"] == 800 for r in rows)
    narrowed = client.get(
        f"{api_prefix}/products/{product.id}/quotations?supplier_id={cheap}"
    ).json()
    assert narrowed and all(r["supplier_id"] == str(cheap) for r in narrowed)
