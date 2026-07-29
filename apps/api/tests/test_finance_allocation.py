"""Part 8 C1 — spreading one payment across several documents (R10.9, R10.13).

R10.9 asks for two things and this file proves both: a partial payment spread across
multiple invoices, and an over-payment on one invoice **spilling to the next**. The rest of
the file pins the decisions that make those two safe — the spill order, the refusal of more
than is open, append-only allocation, and exactly one activity row.

Every test builds its own invoices on a customer with no finance history of its own, so the
subject is visible in the test and no other test's assertions are disturbed. `db`-fixture
writes roll back, so nothing survives the test either way.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.core.errors import NotFoundError, ValidationError
from app.modules.activity.models import ActivityLog
from app.modules.config.service import default_business_unit
from app.modules.customers.models import Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.finance.allocation import AllocationService
from app.modules.finance.ledger import open_bills, open_invoices
from app.modules.finance.models import Bill, Invoice, PaymentAllocation
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import AllocationCreate
from app.modules.suppliers.models import Supplier
from app.modules.suppliers.repository import SupplierRepository


@pytest.fixture()
def quiet_customer(db) -> Customer:
    """A customer with no invoices at all, so this test owns the whole open set."""
    busy = {cid for cid, _name in FinanceRepository(db).customers_with_activity()}
    customer = next(
        (
            row
            for row in db.scalars(
                select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code.desc())
            )
            if row.id not in busy
        ),
        None,
    )
    assert customer is not None, "every customer has invoices — no clean subject available"
    return customer


@pytest.fixture()
def three_invoices(db, quiet_customer) -> list[Invoice]:
    """Three open invoices, ₹100 / ₹200 / ₹300, due 60, 30 and 10 days ago.

    Deliberately created NEWEST-DUE FIRST, so a spill that ran in insertion order rather
    than due-date order would produce a visibly different answer.
    """
    bu_id = default_business_unit(db)
    made = []
    for total_minor, days_ago in ((300_00, 10), (200_00, 30), (100_00, 60)):
        due = date.today() - timedelta(days=days_ago)
        invoice = Invoice(
            customer_id=quiet_customer.id,
            invoice_no=f"INVA-{uuid.uuid4().hex[:8]}",
            invoice_date=due - timedelta(days=30),
            due_date=due,
            status="issued",
            subtotal_minor=total_minor,
            tax_minor=0,
            total_minor=total_minor,
            business_unit_id=bu_id,
        )
        db.add(invoice)
        made.append(invoice)
    db.flush()
    return made


def _open_map(db, customer_id) -> dict[str, int]:
    return {doc.doc_no: doc.open_minor for doc in open_invoices(db, customer_id=customer_id)}


def test_r10_9_a_partial_payment_spreads_across_multiple_invoices(
    db, quiet_customer, three_invoices
):
    """₹250 across a ₹100 and a ₹200 invoice: the first is settled, the second part paid."""
    result = AllocationService(db).allocate_receipt(
        quiet_customer.id, AllocationCreate(amount_minor=250_00), actor_id=None
    )
    assert result.allocated_minor == 250_00
    assert len(result.lines) == 2, "a partial payment did not reach a second invoice"

    first, second = result.lines
    assert (first.applied_minor, first.open_after_minor, first.status_after) == (100_00, 0, "paid")
    assert (second.applied_minor, second.open_after_minor, second.status_after) == (
        150_00, 50_00, "part_paid",
    )

    remaining = _open_map(db, quiet_customer.id)
    assert first.doc_no not in remaining, "a settled invoice is still open"
    assert remaining[second.doc_no] == 50_00
    # The third invoice was never reached, so it is untouched at its full ₹300.
    assert len(remaining) == 2 and 300_00 in remaining.values()


def test_r10_9_an_over_payment_spills_to_the_next_invoice(db, quiet_customer, three_invoices):
    """The case R10.9 names: more than one invoice's balance carries to the next.

    ₹150 against a ₹100 invoice settles it and the surplus ₹50 lands on the next one — it
    is not refused, and it is not left sitting on the first invoice as a negative balance.
    """
    result = AllocationService(db).allocate_receipt(
        quiet_customer.id, AllocationCreate(amount_minor=150_00), actor_id=None
    )
    assert [ln.applied_minor for ln in result.lines] == [100_00, 50_00]
    assert result.lines[0].open_after_minor == 0
    assert result.lines[1].open_after_minor == 150_00

    # And no invoice was pushed below zero by the spill.
    for doc in open_invoices(db, customer_id=quiet_customer.id):
        assert doc.open_minor > 0, doc.doc_no


def test_r10_9_the_spill_order_is_oldest_due_first(db, quiet_customer, three_invoices):
    """Insertion order is newest-due first, so this fails if the sort is dropped."""
    expected = [
        inv.invoice_no
        for inv in sorted(three_invoices, key=lambda i: (i.due_date, i.invoice_no))
    ]
    result = AllocationService(db).allocate_receipt(
        quiet_customer.id, AllocationCreate(amount_minor=600_00), actor_id=None
    )
    assert [ln.doc_no for ln in result.lines] == expected
    assert [ln.applied_minor for ln in result.lines] == [100_00, 200_00, 300_00]
    assert all(ln.open_after_minor == 0 for ln in result.lines)
    assert _open_map(db, quiet_customer.id) == {}


def test_r10_9_more_than_the_total_open_is_refused_with_the_figure(
    db, quiet_customer, three_invoices
):
    """Refused rather than held on account, so the receivable stays one number."""
    with pytest.raises(ValidationError) as caught:
        AllocationService(db).allocate_receipt(
            quiet_customer.id, AllocationCreate(amount_minor=600_01), actor_id=None
        )
    assert "600.00 open across 3 invoices" in caught.value.message, caught.value.message
    # Nothing was applied — the refusal is not a partial write.
    assert sum(_open_map(db, quiet_customer.id).values()) == 600_00


def test_r10_9_a_party_with_nothing_open_is_refused(db, quiet_customer):
    with pytest.raises(ValidationError) as caught:
        AllocationService(db).allocate_receipt(
            quiet_customer.id, AllocationCreate(amount_minor=100), actor_id=None
        )
    assert "no open invoices" in caught.value.message


def test_r10_9_an_unknown_party_is_a_not_found(db):
    with pytest.raises(NotFoundError):
        AllocationService(db).allocate_receipt(
            uuid.uuid4(), AllocationCreate(amount_minor=100), actor_id=None
        )
    with pytest.raises(NotFoundError):
        AllocationService(db).allocate_payment(
            uuid.uuid4(), AllocationCreate(amount_minor=100), actor_id=None
        )


def test_r10_9_allocation_appends_rows_and_never_edits_the_invoice(
    db, quiet_customer, three_invoices
):
    """G4: money applied is a new row. Only the documented `status` cache moves."""
    billed = {inv.invoice_no: (inv.total_minor, inv.subtotal_minor) for inv in three_invoices}
    before = db.scalar(select(func.count()).select_from(PaymentAllocation)) or 0

    AllocationService(db).allocate_receipt(
        quiet_customer.id, AllocationCreate(amount_minor=250_00), actor_id=None
    )

    after = db.scalar(select(func.count()).select_from(PaymentAllocation)) or 0
    assert after == before + 2, "the allocation did not append one row per document"
    for inv in three_invoices:
        db.refresh(inv)
        assert (inv.total_minor, inv.subtotal_minor) == billed[inv.invoice_no], inv.invoice_no


def test_r10_9_allocation_writes_exactly_one_activity_row(db, quiet_customer, three_invoices):
    """G5 — one row per state change, naming the documents it touched."""
    before = db.scalar(select(func.count()).select_from(ActivityLog)) or 0
    result = AllocationService(db).allocate_receipt(
        quiet_customer.id, AllocationCreate(amount_minor=250_00), actor_id=None
    )
    rows = list(
        db.scalars(
            select(ActivityLog).where(
                ActivityLog.entity_type == "payment", ActivityLog.entity_id == result.payment_id
            )
        )
    )
    assert (db.scalar(select(func.count()).select_from(ActivityLog)) or 0) == before + 1
    assert len(rows) == 1
    assert rows[0].verb == "payment_allocated"
    assert result.payment_no in rows[0].summary
    for line in result.lines:
        assert line.doc_no in rows[0].summary, "the log does not say where the money went"


def test_r10_9_the_receivable_drops_by_exactly_the_amount_applied(
    db, quiet_customer, three_invoices
):
    """The one receivable definition is what has to move, not a per-screen figure."""
    repo = CustomerRepository(db)
    before = repo.outstanding_minor(quiet_customer.id)
    AllocationService(db).allocate_receipt(
        quiet_customer.id, AllocationCreate(amount_minor=250_00), actor_id=None
    )
    assert repo.outstanding_minor(quiet_customer.id) == before - 250_00


def test_r10_9_the_buy_side_allocates_the_same_way(db):
    """One implementation, two directions — a vendor payment spills identically."""
    bu_id = default_business_unit(db)
    busy = {sid for sid, _name in FinanceRepository(db).suppliers_with_activity()}
    supplier = next(
        (
            row
            for row in db.scalars(
                select(Supplier).where(Supplier.deleted_at.is_(None)).order_by(Supplier.code.desc())
            )
            if row.id not in busy
        ),
        None,
    )
    assert supplier is not None, "every supplier has bills — no clean subject available"

    for total_minor, days_ago in ((400_00, 5), (100_00, 45)):
        due = date.today() - timedelta(days=days_ago)
        db.add(
            Bill(
                supplier_id=supplier.id,
                bill_no=f"BILA-{uuid.uuid4().hex[:8]}",
                bill_date=due - timedelta(days=30),
                due_date=due,
                status="issued",
                subtotal_minor=total_minor,
                tax_minor=0,
                total_minor=total_minor,
                business_unit_id=bu_id,
            )
        )
    db.flush()

    before = SupplierRepository(db).outstanding_minor(supplier.id)
    result = AllocationService(db).allocate_payment(
        supplier.id, AllocationCreate(amount_minor=150_00), actor_id=None
    )
    # Oldest due first: the ₹100 bill (45 days) before the ₹400 one (5 days).
    assert [ln.applied_minor for ln in result.lines] == [100_00, 50_00]
    assert result.side == "payable"
    assert SupplierRepository(db).outstanding_minor(supplier.id) == before - 150_00
    assert {doc.doc_no for doc in open_bills(db, supplier_id=supplier.id)} == {
        result.lines[1].doc_no
    }
