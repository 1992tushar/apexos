"""Part 13 — GST tax-invoice print/download (R16.1-R16.6).

`_make_invoice` builds a header + one line directly (the `db` fixture rolls back), the
same pattern `test_finance_ledgers.py` uses — a print view needs a product and a
customer behind the line, which a header-only fixture does not exercise.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.core.errors import NotFoundError
from app.modules.config.schemas import CompanyProfileUpdate
from app.modules.config.service import CompanyProfileService, default_business_unit
from app.modules.customers.models import Customer
from app.modules.finance.invoice_print import InvoicePrintService, _state_code
from app.modules.finance.models import Invoice, InvoiceLine
from app.modules.products.models import Product


def _customer(db, *, bu_id, gstin: str | None) -> Customer:
    from app.modules.config.models import CustomerType

    ctype = db.scalar(select(CustomerType).where(CustomerType.deleted_at.is_(None)).limit(1))
    customer = Customer(
        customer_type_id=ctype.id,
        code=f"CUSTT-{uuid.uuid4().hex[:8]}",
        name="Print Test Customer",
        gstin=gstin,
        billing_address="1 Test Lane",
        city="Testville",
        state="Maharashtra" if gstin is None or gstin.startswith("27") else "Karnataka",
        business_unit_id=bu_id,
    )
    db.add(customer)
    db.flush()
    return customer


def _invoice(db, *, customer_id, bu_id, product_id, tax_rate_bps=1800) -> Invoice:
    subtotal = 100000  # 1000.00 rupees
    tax = subtotal * tax_rate_bps // 10000
    invoice = Invoice(
        customer_id=customer_id,
        invoice_no=f"INVP-{uuid.uuid4().hex[:8]}",
        invoice_date=date.today(),
        status="issued",
        subtotal_minor=subtotal,
        tax_minor=tax,
        total_minor=subtotal + tax,
        business_unit_id=bu_id,
    )
    db.add(invoice)
    db.flush()
    line = InvoiceLine(
        invoice_id=invoice.id,
        product_id=product_id,
        qty=1,
        unit_price_minor=subtotal,
        tax_rate_bps=tax_rate_bps,
        line_subtotal_minor=subtotal,
        line_tax_minor=tax,
        line_total_minor=subtotal + tax,
        line_no=1,
    )
    db.add(line)
    db.flush()
    return invoice


def _any_product(db) -> Product:
    return db.scalar(select(Product).where(Product.deleted_at.is_(None)).limit(1))


def test_r16_1_the_company_profile_is_a_single_row_created_on_first_read(db):
    row = CompanyProfileService(db).get()
    assert row.legal_name
    again = CompanyProfileService(db).get()
    assert again.id == row.id, "a second read must not create a second row"


def test_r16_1_updating_the_company_profile_clears_the_placeholder_flag(db):
    svc = CompanyProfileService(db)
    row = svc.get()
    updated = svc.update(
        CompanyProfileUpdate(
            legal_name=row.legal_name,
            address_line1="42 Real Street",
            city=row.city,
            state=row.state,
            gstin="27AAAAA0000A1Z5",
        ),
        actor_id=None,
    )
    assert updated.is_placeholder is False
    assert updated.address_line1 == "42 Real Street"


def test_r16_2_a_product_with_no_hsn_prints_blank_not_blocked(db):
    bu_id = default_business_unit(db)
    product = _any_product(db)
    assert product.hsn_code is None, "seeded demo products carry no HSN by default"
    customer = _customer(db, bu_id=bu_id, gstin=None)
    invoice = _invoice(db, customer_id=customer.id, bu_id=bu_id, product_id=product.id)

    view = InvoicePrintService(db).get(invoice.id)
    assert view.lines[0].hsn_code is None


def test_r16_2_setting_the_hsn_code_reaches_the_print_line(db):
    from app.modules.products.service import ProductService

    bu_id = default_business_unit(db)
    product = _any_product(db)
    ProductService(db).set_hsn(product.id, "4818", actor_id=None)
    db.flush()

    customer = _customer(db, bu_id=bu_id, gstin=None)
    invoice = _invoice(db, customer_id=customer.id, bu_id=bu_id, product_id=product.id)
    view = InvoicePrintService(db).get(invoice.id)
    assert view.lines[0].hsn_code == "4818"

    # Restore, so this test does not leak state into others sharing the seeded product.
    ProductService(db).set_hsn(product.id, None, actor_id=None)


def test_r16_3_state_code_is_read_from_the_gstins_first_two_digits():
    assert _state_code("27AAAAA0000A1Z5") == "27"
    assert _state_code("29AAAAA0000A1Z5") == "29"
    assert _state_code(None) is None
    assert _state_code("") is None


def test_r16_3_same_state_customer_splits_cgst_and_sgst(db):
    bu_id = default_business_unit(db)
    product = _any_product(db)
    # Company profile seeds to state_code 27 (Maharashtra) — match it.
    customer = _customer(db, bu_id=bu_id, gstin="27AAAAA0000A1Z5")
    invoice = _invoice(db, customer_id=customer.id, bu_id=bu_id, product_id=product.id)

    view = InvoicePrintService(db).get(invoice.id)
    assert view.same_state is True
    assert view.state_assumed is False
    line = view.lines[0]
    assert line.igst_minor == 0
    assert line.cgst_minor + line.sgst_minor == invoice.tax_minor
    assert view.cgst_total_minor == view.sgst_total_minor


def test_r16_3_different_state_customer_uses_igst(db):
    bu_id = default_business_unit(db)
    product = _any_product(db)
    customer = _customer(db, bu_id=bu_id, gstin="29AAAAA0000A1Z5")  # Karnataka
    invoice = _invoice(db, customer_id=customer.id, bu_id=bu_id, product_id=product.id)

    view = InvoicePrintService(db).get(invoice.id)
    assert view.same_state is False
    line = view.lines[0]
    assert line.cgst_minor == 0 and line.sgst_minor == 0
    assert line.igst_minor == invoice.tax_minor


def test_r16_3_a_customer_with_no_gstin_assumes_same_state_and_says_so(db):
    bu_id = default_business_unit(db)
    product = _any_product(db)
    customer = _customer(db, bu_id=bu_id, gstin=None)
    invoice = _invoice(db, customer_id=customer.id, bu_id=bu_id, product_id=product.id)

    view = InvoicePrintService(db).get(invoice.id)
    assert view.same_state is True
    assert view.state_assumed is True


def test_r16_4_the_print_view_carries_every_figure_the_template_needs_with_no_query_in_it(db):
    bu_id = default_business_unit(db)
    product = _any_product(db)
    customer = _customer(db, bu_id=bu_id, gstin=None)
    invoice = _invoice(db, customer_id=customer.id, bu_id=bu_id, product_id=product.id)

    view = InvoicePrintService(db).get(invoice.id)
    assert view.invoice_no == invoice.invoice_no
    assert view.company_legal_name
    assert view.customer_name == customer.name
    assert view.total_minor == invoice.total_minor


def test_r16_4_the_print_route_renders_the_standalone_document(client):
    """R16.4 end to end: the route resolves a real seeded invoice."""
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        invoice = session.scalar(select(Invoice))
        assert invoice is not None, "the seed produced no invoice to print"
        invoice_id = invoice.id
    finally:
        session.close()

    resp = client.get(f"/invoices/{invoice_id}/print")
    assert resp.status_code == 200
    assert "TAX INVOICE" in resp.text
    assert "Print / Save as PDF" in resp.text


def test_r16_4_printing_an_unknown_invoice_id_is_a_clean_not_found(db):
    with pytest.raises(NotFoundError):
        InvoicePrintService(db).get(uuid.uuid4())


def test_r16_6_printing_does_not_write_or_mutate_the_invoice(db):
    bu_id = default_business_unit(db)
    product = _any_product(db)
    customer = _customer(db, bu_id=bu_id, gstin=None)
    invoice = _invoice(db, customer_id=customer.id, bu_id=bu_id, product_id=product.id)
    before_status, before_total = invoice.status, invoice.total_minor

    InvoicePrintService(db).get(invoice.id)
    InvoicePrintService(db).get(invoice.id)

    db.refresh(invoice)
    assert invoice.status == before_status
    assert invoice.total_minor == before_total


def test_r3_7_company_profile_has_a_references_entry():
    """Every model owes `references.py` an entry, even empty (R3.7)."""
    from app.db.references import REFERENCES

    assert "company_profile" in REFERENCES
    assert REFERENCES["company_profile"] == ()
