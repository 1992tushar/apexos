"""Part 7 C2 — reservation wiring (R9.8/R9.9) and returns + credit notes (R9.4–R9.7).

The load-bearing test in this file is `test_r9_5_the_invoice_is_unchanged_after_a_return`.
It snapshots every column of the invoice and its lines before the return and compares them
after, because R9.5 is a direct test of G4: an invoice is a document the customer already
holds, and editing it down would destroy the record of what was billed.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, ValidationError
from app.modules.customers.credit import CreditPolicyService
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.schemas import CreditPolicySet
from app.modules.finance.models import CreditNote, Invoice
from app.modules.inventory.models import StockMovement
from app.modules.inventory.service import InventoryService, ReservationService
from app.modules.sales.returns import SalesReturnService
from app.modules.sales.schemas import (
    ReturnLineCreate,
    SalesOrderCreate,
    SalesOrderLineCreate,
    SalesReturnCreate,
)
from app.modules.sales.service import SalesOrderService


@pytest.fixture()
def customer(db):
    """A customer with a generous limit, so the credit gate never masks what is tested."""
    from app.modules.config.models import CustomerType
    from app.modules.customers.schemas import CustomerCreate
    from app.modules.customers.service import CustomerService

    ctype = db.scalar(select(CustomerType).where(CustomerType.deleted_at.is_(None)))
    made = CustomerService(db).create(
        CustomerCreate(
            name=f"Returns Co {uuid.uuid4().hex[:6]}",
            customer_type_id=ctype.id,
            city="Pune",
        ),
        actor_id=None,
    )
    CreditPolicyService(db).set_policy(
        made.id,
        CreditPolicySet(credit_limit_minor=99_000_000, reason="Generous for the tests"),
        actor_id=None,
    )
    return made


@pytest.fixture()
def stocked(db):
    """A product with enough stock that confirming can reserve against it."""
    for row in InventoryService(db).stock():
        if row.qty_on_hand >= 30:
            return row
    pytest.fail("no product with enough stock")


def _order(db, customer, stocked, qty: str = "6"):
    return SalesOrderService(db).create(
        SalesOrderCreate(
            customer_id=customer.id,
            lines=[
                SalesOrderLineCreate(
                    product_id=stocked.product_id, qty=Decimal(qty), unit_price_minor=250_00
                )
            ],
        ),
        actor_id=None,
    )


def _reserved(db, product_id) -> Decimal:
    return ReservationService(db).reserved(product_id)


# --- R9.8: confirm reserves ---------------------------------------------------


def test_r9_8_confirming_an_order_reserves_stock(db, customer, stocked):
    inventory = InventoryService(db)
    order = _order(db, customer, stocked, qty="6")

    on_hand_before = inventory.on_hand(stocked.product_id)
    reserved_before = _reserved(db, stocked.product_id)

    SalesOrderService(db).confirm(order.id, actor_id=None)

    # Reserved goes up; ON-HAND DOES NOT MOVE. Committing stock is not shipping it.
    assert _reserved(db, stocked.product_id) == reserved_before + Decimal("6")
    assert inventory.on_hand(stocked.product_id) == on_hand_before


def test_r9_8_the_reservation_records_the_order_it_is_for(db, customer, stocked):
    order = _order(db, customer, stocked, qty="3")
    SalesOrderService(db).confirm(order.id, actor_id=None)

    entries = ReservationService(db).entries(stocked.product_id)
    mine = [e for e in entries if e.ref_id == order.id]
    assert mine, "the reservation does not link back to its order"
    assert mine[0].ref_type == "sales_order"
    assert mine[0].reason == "RESERVE"


def test_r9_8_reservation_happens_after_the_credit_gate_not_before(db, customer, stocked):
    """A refused confirm must leave NO reservation behind — otherwise stock is held for an
    order that never confirmed. This is why the gate runs first."""
    order = _order(db, customer, stocked, qty="5")
    CreditPolicyService(db).set_policy(
        customer.id,
        CreditPolicySet(credit_limit_minor=1, reason="Deliberately tiny"),
        actor_id=None,
    )
    reserved_before = _reserved(db, stocked.product_id)

    with pytest.raises(ConflictError, match="over their credit limit"):
        SalesOrderService(db).confirm(order.id, actor_id=None)

    assert _reserved(db, stocked.product_id) == reserved_before, (
        "a refused confirm still reserved stock"
    )


def test_r9_8_there_is_no_reserved_flag_anywhere(db):
    """R6.5's acceptance, re-asserted now that sales actually calls the verb."""
    offenders = []
    for name, table in StockMovement.metadata.tables.items():
        for column in table.columns:
            if str(column.type).upper().startswith("BOOLEAN") and "reserv" in column.name.lower():
                offenders.append(f"{name}.{column.name}")
    assert not offenders, f"reservation must stay a ledger, not a flag: {offenders}"


# --- R9.9: fulfil consumes, cancel releases ----------------------------------


def test_r9_9_fulfilment_consumes_the_reservation_and_moves_the_stock(db, customer, stocked):
    inventory = InventoryService(db)
    svc = SalesOrderService(db)
    order = _order(db, customer, stocked, qty="4")
    svc.confirm(order.id, actor_id=None)

    reserved_after_confirm = _reserved(db, stocked.product_id)
    on_hand_before = inventory.on_hand(stocked.product_id)

    svc.fulfill(order.id, actor_id=None)

    # The reservation is retired AND the stock has left — not one or the other.
    assert _reserved(db, stocked.product_id) == reserved_after_confirm - Decimal("4")
    assert inventory.on_hand(stocked.product_id) == on_hand_before - Decimal("4")


def test_r9_9_cancelling_a_confirmed_order_releases_the_reservation(db, customer, stocked):
    inventory = InventoryService(db)
    svc = SalesOrderService(db)
    order = _order(db, customer, stocked, qty="7")

    reserved_before = _reserved(db, stocked.product_id)
    on_hand_before = inventory.on_hand(stocked.product_id)
    svc.confirm(order.id, actor_id=None)
    assert _reserved(db, stocked.product_id) == reserved_before + Decimal("7")

    cancelled = svc.cancel(order.id, reason="Customer changed their mind", actor_id=None)

    assert cancelled.status == "cancelled"
    # Back exactly where it started: released, and the stock never moved.
    assert _reserved(db, stocked.product_id) == reserved_before
    assert inventory.on_hand(stocked.product_id) == on_hand_before


def test_r9_9_cancelling_a_draft_releases_nothing_because_it_reserved_nothing(
    db, customer, stocked
):
    svc = SalesOrderService(db)
    order = _order(db, customer, stocked, qty="5")
    reserved_before = _reserved(db, stocked.product_id)

    svc.cancel(order.id, reason="Raised in error", actor_id=None)
    assert _reserved(db, stocked.product_id) == reserved_before


def test_r9_9_a_fulfilled_order_cannot_be_cancelled(db, customer, stocked):
    """The stock has physically left; undoing that is a return, not a cancellation."""
    svc = SalesOrderService(db)
    order = _order(db, customer, stocked, qty="2")
    svc.confirm(order.id, actor_id=None)
    svc.fulfill(order.id, actor_id=None)

    with pytest.raises(ConflictError, match="record a return instead"):
        svc.cancel(order.id, reason="Too late", actor_id=None)


def test_r9_9_cancelling_needs_a_reason(db, customer, stocked):
    svc = SalesOrderService(db)
    order = _order(db, customer, stocked, qty="2")
    with pytest.raises(ValidationError, match="needs a reason"):
        svc.cancel(order.id, reason="   ", actor_id=None)


# --- R9.4–R9.7: returns and credit notes -------------------------------------


def _invoiced_order(db, customer, stocked, qty: str = "6"):
    svc = SalesOrderService(db)
    order = _order(db, customer, stocked, qty=qty)
    svc.confirm(order.id, actor_id=None)
    svc.fulfill(order.id, actor_id=None)
    detail = svc.invoice(order.id, actor_id=None)
    invoice = db.scalar(
        select(Invoice).where(Invoice.sales_order_id == order.id, Invoice.deleted_at.is_(None))
    )
    assert invoice is not None
    del detail
    return order, invoice


def test_r9_6_returnable_starts_as_the_invoiced_quantity(db, customer, stocked):
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="6")

    lines = SalesReturnService(db).returnable(invoice.id)
    assert len(lines) == 1
    assert lines[0].invoiced_qty == Decimal("6")
    assert lines[0].returned_qty == Decimal("0")
    assert lines[0].returnable_qty == Decimal("6")
    assert not lines[0].fully_returned


def test_r9_4_a_return_posts_stock_in_through_the_only_writer(db, customer, stocked):
    inventory = InventoryService(db)
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="6")

    on_hand_before = inventory.on_hand(stocked.product_id)
    ret = SalesReturnService(db).create(
        SalesReturnCreate(
            invoice_id=invoice.id,
            reason="Two cases damaged in transit",
            lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("2"))],
        ),
        actor_id=None,
    )

    assert inventory.on_hand(stocked.product_id) == on_hand_before + Decimal("2")
    movement = db.scalar(
        select(StockMovement).where(
            StockMovement.ref_type == "sales_return", StockMovement.ref_id == ret.id
        )
    )
    assert movement is not None
    assert movement.reason == "RETURN"
    assert movement.qty_delta == Decimal("2")


def test_r9_5_the_invoice_is_unchanged_after_a_return(db, customer, stocked):
    """R9.5 is a direct test of G4. Every column of the invoice and its lines is snapshotted
    before the return and compared after — not just the total."""
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="6")

    def snapshot(inv: Invoice) -> dict:
        return {
            "header": {c.name: getattr(inv, c.name) for c in Invoice.__table__.columns},
            "lines": [
                {c.name: getattr(ln, c.name) for c in ln.__table__.columns}
                for ln in sorted(inv.lines, key=lambda x: x.line_no)
            ],
        }

    before = snapshot(invoice)

    SalesReturnService(db).create(
        SalesReturnCreate(
            invoice_id=invoice.id,
            reason="Short-dated stock",
            lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("3"))],
        ),
        actor_id=None,
    )
    db.refresh(invoice)

    assert snapshot(invoice) == before, "the return mutated the invoice — G4/R9.5 violated"


def test_r9_5_a_return_raises_a_credit_note_against_the_invoice(db, customer, stocked):
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="6")

    ret = SalesReturnService(db).create(
        SalesReturnCreate(
            invoice_id=invoice.id,
            reason="Wrong size delivered",
            lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("2"))],
        ),
        actor_id=None,
    )

    assert ret.credit_note is not None
    assert ret.credit_note.credit_note_no.startswith("CRN-")
    assert ret.credit_note.invoice_id == invoice.id
    # The credit is for what was invoiced: 2 x 250.00 plus its tax.
    assert ret.credit_note.total_minor == ret.total_minor
    assert ret.total_minor > 0

    stored = db.scalar(select(CreditNote).where(CreditNote.sales_return_id == ret.id))
    assert stored is not None and stored.sales_return_id == ret.id


def test_r9_7_the_credit_note_reduces_the_receivable_through_the_ledger(db, customer, stocked):
    """R9.7 — the receivable falls because a credit note is subtracted from it, not because
    the invoice was edited."""
    repo = CustomerRepository(db)
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="6")

    outstanding_before = repo.outstanding_minor(customer.id)
    invoice_total_before = invoice.total_minor
    assert outstanding_before > 0

    ret = SalesReturnService(db).create(
        SalesReturnCreate(
            invoice_id=invoice.id,
            reason="Two cases returned",
            lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("2"))],
        ),
        actor_id=None,
    )

    assert repo.outstanding_minor(customer.id) == outstanding_before - ret.total_minor
    # And the invoice's own total is untouched: the reduction lives in the credit note, so
    # the receivable moved while the document the customer holds did not.
    db.refresh(invoice)
    assert invoice.total_minor == invoice_total_before


def test_r9_6_a_partial_return_leaves_the_correct_returnable_remainder(db, customer, stocked):
    svc = SalesReturnService(db)
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="6")

    svc.create(
        SalesReturnCreate(
            invoice_id=invoice.id,
            reason="First two back",
            lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("2"))],
        ),
        actor_id=None,
    )

    line = svc.returnable(invoice.id)[0]
    assert line.invoiced_qty == Decimal("6")
    assert line.returned_qty == Decimal("2")
    assert line.returnable_qty == Decimal("4")

    # A second partial return draws the remainder down further.
    svc.create(
        SalesReturnCreate(
            invoice_id=invoice.id,
            reason="Two more back",
            lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("2"))],
        ),
        actor_id=None,
    )
    assert svc.returnable(invoice.id)[0].returnable_qty == Decimal("2")


def test_r9_6_returning_more_than_is_returnable_is_refused_with_the_numbers(db, customer, stocked):
    svc = SalesReturnService(db)
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="6")
    svc.create(
        SalesReturnCreate(
            invoice_id=invoice.id,
            reason="Four back",
            lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("4"))],
        ),
        actor_id=None,
    )

    with pytest.raises(ConflictError) as excinfo:
        svc.create(
            SalesReturnCreate(
                invoice_id=invoice.id,
                reason="Three more, but only two are left",
                lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("3"))],
            ),
            actor_id=None,
        )
    message = str(excinfo.value)
    # A refusal the founder can act on states the arithmetic.
    assert "was invoiced" in message and "already came back" in message
    assert "returnable" in message


def test_r9_6_the_returnable_definition_is_clamped_at_zero(db):
    """One definition, clamped — the shape `open_qty` gave back orders."""
    assert SalesReturnService.returnable_qty(Decimal("6"), Decimal("2")) == Decimal("4")
    assert SalesReturnService.returnable_qty(Decimal("6"), Decimal("6")) == Decimal("0")
    # A data oddity must read as "nothing left", not as a negative allowance.
    assert SalesReturnService.returnable_qty(Decimal("6"), Decimal("9")) == Decimal("0")


def test_r9_4_a_return_needs_a_reason(db, customer, stocked):
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="4")

    with pytest.raises(ValidationError, match="needs a reason"):
        SalesReturnService(db).create(
            SalesReturnCreate(
                invoice_id=invoice.id,
                reason="   ",
                lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("1"))],
            ),
            actor_id=None,
        )


def test_r9_4_a_product_not_on_the_invoice_is_refused(db, customer, stocked):
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="4")

    with pytest.raises(ValidationError, match="is not on invoice"):
        SalesReturnService(db).create(
            SalesReturnCreate(
                invoice_id=invoice.id,
                reason="Never sold this",
                lines=[ReturnLineCreate(product_id=uuid.uuid4(), qty=Decimal("1"))],
            ),
            actor_id=None,
        )


def test_r9_4_an_over_return_writes_nothing_at_all(db, customer, stocked):
    """The whole payload is validated before anything is written, so a partly-invalid
    return does not leave half its stock posted."""
    inventory = InventoryService(db)
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="4")

    on_hand_before = inventory.on_hand(stocked.product_id)
    returns_before = db.scalar(
        select(func.count()).select_from(CreditNote).where(CreditNote.invoice_id == invoice.id)
    )

    with pytest.raises(ConflictError):
        SalesReturnService(db).create(
            SalesReturnCreate(
                invoice_id=invoice.id,
                reason="Too many",
                lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("99"))],
            ),
            actor_id=None,
        )

    assert inventory.on_hand(stocked.product_id) == on_hand_before
    assert db.scalar(
        select(func.count()).select_from(CreditNote).where(CreditNote.invoice_id == invoice.id)
    ) == returns_before


def test_r9_4_the_return_is_priced_as_invoiced_not_at_todays_price(db, customer, stocked):
    """A credit must be for what the customer actually paid."""
    _order_row, invoice = _invoiced_order(db, customer, stocked, qty="5")
    invoiced_unit = invoice.lines[0].unit_price_minor

    ret = SalesReturnService(db).create(
        SalesReturnCreate(
            invoice_id=invoice.id,
            reason="Priced as billed",
            lines=[ReturnLineCreate(product_id=stocked.product_id, qty=Decimal("2"))],
        ),
        actor_id=None,
    )
    assert ret.lines[0].unit_price_minor == invoiced_unit


def test_r3_7_the_return_models_declare_their_blocking_references(db):
    from app.db.references import REFERENCES

    for table in ("sales_return", "sales_return_line", "credit_note"):
        assert table in REFERENCES, f"{table} owes references.py an entry (R3.7)"
        assert REFERENCES[table] == (), (
            f"{table} is append-only history and should block nothing"
        )


def test_r9_4_stock_movement_is_still_written_only_through_record_movement(db):
    """G8, re-asserted now that returns post stock too."""
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    allowed = {
        Path("modules/inventory/service.py"),
        Path("modules/inventory/models.py"),
        Path("modules/inventory/repository.py"),
    }
    offenders = [
        str(p.relative_to(app_dir))
        for p in app_dir.rglob("*.py")
        if p.relative_to(app_dir) not in allowed
        and "StockMovement(" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"these bypass G8: {offenders}"
