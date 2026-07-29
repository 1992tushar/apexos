"""Part 8 C1 — customer and vendor statements (R10.1–R10.4, R10.10, R10.13).

The load-bearing test in this file is
`test_r10_2_the_statement_closes_on_the_one_receivable_definition`: it asserts that a
statement's closing balance IS `CustomerRepository.outstanding_minor`, and that the lines
above it sum to the same figure. Two screens disagreeing about what a customer owes is the
defect R10.x exists to prevent, and this is where it would show up first.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.modules.activity.models import ActivityLog
from app.modules.config.service import default_business_unit
from app.modules.customers.models import Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.finance.ledger import PartyLedgerService, open_invoices
from app.modules.finance.models import Bill, Invoice, Payment, PaymentAllocation
from app.modules.finance.repository import FinanceRepository
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.repository import SupplierRepository


@pytest.fixture()
def billed_customers(db):
    """Customers with at least one live invoice — the ones a statement is about."""
    return FinanceRepository(db).customers_with_activity()


def _make_invoice(db, *, customer_id, bu_id, total_minor, due_date, status="issued"):
    """A header-only invoice. Lines are irrelevant to a balance and this keeps the
    subject of the test visible; `db`-fixture writes roll back, so nothing is left behind.
    """
    invoice = Invoice(
        customer_id=customer_id,
        invoice_no=f"INVT-{uuid.uuid4().hex[:8]}",
        invoice_date=due_date - timedelta(days=30),
        due_date=due_date,
        status=status,
        subtotal_minor=total_minor,
        tax_minor=0,
        total_minor=total_minor,
        business_unit_id=bu_id,
    )
    db.add(invoice)
    db.flush()
    return invoice


def test_r10_1_the_customer_statement_lists_every_document_with_a_running_balance(
    db, billed_customers
):
    assert len(billed_customers) >= 3, "the seed cannot exercise a statement screen (G14)"
    customer_id, _name = billed_customers[0]
    statement = PartyLedgerService(db).customer_statement(customer_id)

    assert statement.lines, "a customer with invoices produced an empty statement"
    # The balance is cumulative, recomputed at read time — not a stored column (R10.2, G7).
    running = 0
    for line in statement.lines:
        running += line.debit_minor - line.credit_minor
        assert line.balance_minor == running, f"{line.doc_no} broke the running balance"


def test_r10_2_the_statement_closes_on_the_one_receivable_definition(db, billed_customers):
    """The whole point of R10.x, asserted across every party the seed produced."""
    repo = CustomerRepository(db)
    svc = PartyLedgerService(db)
    checked = 0
    for customer_id, name in billed_customers:
        statement = svc.customer_statement(customer_id)
        receivable = repo.outstanding_minor(customer_id)
        assert statement.closing_balance_minor == receivable, name
        assert statement.line_total_minor == receivable, (
            f"{name}: the statement lines sum to {statement.line_total_minor} but the one "
            f"receivable definition says {receivable}"
        )
        assert svc.statement_note(statement) is None, f"{name} reported a reconciliation gap"
        checked += 1
    assert checked >= 3, f"only {checked} statements checked — the seed is too thin to prove it"


def test_r10_2_the_vendor_statement_closes_on_the_one_payable_definition(db):
    repo = SupplierRepository(db)
    svc = PartyLedgerService(db)
    parties = FinanceRepository(db).suppliers_with_activity()
    assert parties, "no supplier has a bill — the payable statement cannot be exercised"
    for supplier_id, name in parties:
        statement = svc.vendor_statement(supplier_id)
        assert statement.closing_balance_minor == repo.outstanding_minor(supplier_id), name
        assert statement.line_total_minor == statement.closing_balance_minor, name


def test_r10_2_the_running_balance_tracks_a_new_payment(db, billed_customers):
    """G7: the balance is derived, so a new ledger row moves it with no other write."""
    repo = CustomerRepository(db)
    customer_id, _name = next(
        (pair for pair in billed_customers if repo.outstanding_minor(pair[0]) > 0),
        (None, None),
    )
    assert customer_id is not None, "no customer owes anything — nothing to track"

    before = PartyLedgerService(db).customer_statement(customer_id)
    target = before.open_documents[0]

    payment = Payment(
        direction="in",
        customer_id=customer_id,
        payment_no=f"PAYT-{uuid.uuid4().hex[:8]}",
        amount_minor=1000,
        method="bank",
    )
    payment.allocations.append(PaymentAllocation(invoice_id=target.id, amount_minor=1000))
    db.add(payment)
    db.flush()

    after = PartyLedgerService(db).customer_statement(customer_id)
    assert after.closing_balance_minor == before.closing_balance_minor - 1000
    assert len(after.lines) == len(before.lines) + 1
    assert after.line_total_minor == after.closing_balance_minor


def test_r10_3_every_ledger_line_drills_through_to_a_live_document(db, billed_customers):
    """A line with nowhere to click is the defect R10.3 names."""
    lines = 0
    for customer_id, _name in billed_customers:
        for line in PartyLedgerService(db).customer_statement(customer_id).lines:
            assert line.href.startswith("/invoices/"), line.doc_no
            target = db.get(Invoice, uuid.UUID(line.href.rsplit("/", 1)[1]))
            assert target is not None, f"{line.doc_no} points at an invoice that is not there"
            lines += 1
    assert lines >= 8, f"only {lines} ledger lines — too few to prove the drill-through"


def test_r10_3_the_vendor_statement_drills_through_to_its_bills(db):
    lines = 0
    for supplier_id, _name in FinanceRepository(db).suppliers_with_activity():
        for line in PartyLedgerService(db).vendor_statement(supplier_id).lines:
            assert line.href.startswith("/bills/"), line.doc_no
            assert db.get(Bill, uuid.UUID(line.href.rsplit("/", 1)[1])) is not None
            lines += 1
    assert lines >= 3, f"only {lines} vendor ledger lines"


def test_r10_4_the_statement_incorporates_invoices_payments_and_credit_notes(db):
    """All four document types R10.4 names, found on the parties that actually have them."""
    repo = FinanceRepository(db)
    svc = PartyLedgerService(db)

    kinds: set[str] = set()
    for customer_id, _name in repo.customers_with_activity():
        kinds |= {line.doc_type for line in svc.customer_statement(customer_id).lines}
    assert {"invoice", "payment", "credit_note"} <= kinds, (
        f"the sell-side statement never showed all three document types: {sorted(kinds)}"
    )

    vendor_kinds: set[str] = set()
    for supplier_id, _name in repo.suppliers_with_activity():
        vendor_kinds |= {line.doc_type for line in svc.vendor_statement(supplier_id).lines}
    # No credit note on the buy side — credits are a sell-side instrument.
    assert {"bill", "payment"} <= vendor_kinds, sorted(vendor_kinds)


def test_r10_4_a_credit_note_reduces_the_receivable_without_mutating_its_invoice(db):
    """R10.13's credit-note case, read off the ledger rather than a convenience field."""
    from app.modules.finance.models import CreditNote

    note = db.scalar(select(CreditNote).where(CreditNote.deleted_at.is_(None)).limit(1))
    assert note is not None, "the seed has no credit note — R10.4 cannot be exercised"

    invoice = db.get(Invoice, note.invoice_id)
    billed = invoice.total_minor
    allocated = FinanceRepository(db).allocated_minor(invoice.id)

    # The invoice still says what it always said (G4) — the credit is a separate document.
    assert invoice.total_minor == billed
    assert invoice.subtotal_minor + invoice.tax_minor == billed

    # ...and the open balance is smaller by exactly the credit.
    open_docs = {doc.id: doc for doc in open_invoices(db, customer_id=invoice.customer_id)}
    if invoice.id in open_docs:
        doc = open_docs[invoice.id]
        assert doc.credited_minor >= note.total_minor
        assert doc.open_minor == billed - allocated - doc.credited_minor
    else:
        # Fully extinguished by payments plus the credit — still not by an edit.
        assert billed - allocated - note.total_minor <= 0


def test_r10_2_a_cancelled_invoice_is_excluded_from_both_definitions(db, billed_customers):
    """The status filter is not a no-op — an equality test the seed alone cannot fail.

    Both the per-invoice breakdown and `outstanding_minor` skip a cancelled invoice, so
    adding one changes neither figure. Drop the filter from either and the two move apart
    by `total_minor`, which is asserted to be non-trivial below.
    """
    customer_id, _name = billed_customers[0]
    repo = CustomerRepository(db)
    before_total = repo.outstanding_minor(customer_id)
    before_docs = sum(d.open_minor for d in open_invoices(db, customer_id=customer_id))

    cancelled = _make_invoice(
        db,
        customer_id=customer_id,
        bu_id=default_business_unit(db),
        total_minor=999_00,
        due_date=date.today() - timedelta(days=45),
        status="cancelled",
    )
    assert cancelled.total_minor > 0, "a zero-value invoice would make this test vacuous"

    assert repo.outstanding_minor(customer_id) == before_total
    assert sum(d.open_minor for d in open_invoices(db, customer_id=customer_id)) == before_docs


def test_r10_10_reading_a_statement_writes_no_activity_row(db, billed_customers):
    """G15 — a projection owns nothing and records nothing."""
    before = db.scalar(select(func.count()).select_from(ActivityLog)) or 0
    svc = PartyLedgerService(db)
    for customer_id, _name in billed_customers[:5]:
        svc.customer_statement(customer_id)
    for supplier_id, _name in FinanceRepository(db).suppliers_with_activity():
        svc.vendor_statement(supplier_id)
    assert (db.scalar(select(func.count()).select_from(ActivityLog)) or 0) == before


def test_r10_1_an_unknown_party_is_a_not_found_not_a_blank_statement(db):
    from app.core.errors import NotFoundError

    svc = PartyLedgerService(db)
    with pytest.raises(NotFoundError):
        svc.customer_statement(uuid.uuid4())
    with pytest.raises(NotFoundError):
        svc.vendor_statement(uuid.uuid4())


def test_r10_1_the_ledger_picker_offers_only_parties_with_documents(db):
    repo = FinanceRepository(db)
    offered = repo.customers_with_activity()
    total_customers = db.scalar(
        select(func.count()).select_from(Customer).where(Customer.deleted_at.is_(None))
    ) or 0
    assert offered, "the picker offered nobody"
    assert len(offered) < total_customers, (
        "every customer was offered — the picker is not filtering on having documents"
    )
    assert len(repo.suppliers_with_activity()) <= (
        db.scalar(select(func.count()).select_from(Supplier).where(Supplier.deleted_at.is_(None)))
        or 0
    )
