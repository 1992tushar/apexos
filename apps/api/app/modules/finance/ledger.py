"""Party statements and the open-document primitive (R10.1–R10.4, R10.10).

Two things live here, and the second is why the first is trustworthy:

1. **`open_invoices` / `open_bills`** — the per-document open balance. This is the
   *sibling* `CustomerRepository.outstanding_minor` needed and did not have: that method
   answers "what does this customer owe in total", and an ageing screen has to know
   *which* documents that total is made of. The arithmetic is not re-derived — the
   filters are copied from `outstanding_minor`'s three terms, and
   `test_r10_5_the_buckets_reconcile_to_the_one_receivable` sums one to the other.

2. **`PartyLedgerService`** — the running statement (R10.1). Its closing balance is
   `outstanding_minor` / the supplier equivalent, **called, not recomputed**, and its
   lines are built from exactly the terms those methods sum, so
   `Σ(debit − credit) == closing balance` is true by construction rather than by luck.

Both are read-only projections over append-only ledgers: no new table, no new column,
no stored balance (R10.2, R10.10, G7), and no `activity_log` row is written by anything
in this module (G15).
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.money import minor_to_text
from app.modules.customers.repository import CustomerRepository
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import (
    LedgerLine,
    OpenDocument,
    PartyStatement,
    bucket_for,
)
from app.modules.suppliers.repository import SupplierRepository

#: Order the statement reads in when two documents share a date. A payment dated the
#: same day as the invoice it settles must come second or the running balance dips
#: negative for one line and reads as nonsense. `uuid7()` cannot break the tie — its low
#: bits come from `os.urandom`, so ordering by id is not ordering by anything.
_LINE_RANK = {"invoice": 0, "bill": 0, "credit_note": 1, "payment": 2}


def today() -> date:
    """The report date. One place, so a test can reason about "as of"."""
    return datetime.now(UTC).date()


def _due(doc_date: date, due_date: date | None) -> tuple[date, bool]:
    """The date the money is due, and whether we had to assume it.

    `due_date` is nullable on both `invoice` and `bill` but is never NULL in practice —
    `SalesOrderService.invoice` writes `order_date + payment_terms_days`, and 0 days when
    the customer has no credit policy. So a missing due date means the same thing as
    zero-day terms: due on issue. Ageing it any other way would put two customers with
    identical commercial terms in different buckets.
    """
    if due_date is None:
        return doc_date, True
    return due_date, False


def open_invoices(
    db: Session, *, customer_id: uuid.UUID | None = None, as_of: date | None = None
) -> list[OpenDocument]:
    """Every live invoice with an open balance, oldest first (R10.5's input).

    Four queries regardless of how many invoices there are: the invoices, then the
    allocations and the credit notes grouped by invoice. Documents whose balance is
    already zero are dropped — an ageing screen is about what is still owed.
    """
    stamp = as_of or today()
    repo = FinanceRepository(db)
    allocated = repo.allocated_by_invoice()
    credited = repo.credited_by_invoice()

    out: list[OpenDocument] = []
    for inv, party_name in repo.invoices_with_party(customer_id=customer_id):
        paid = allocated.get(inv.id, 0)
        credit = credited.get(inv.id, 0)
        # Clamped at zero: an over-credited invoice is not "negatively open". The excess
        # is a credit on the party and the ageing report carries it as `unaged_minor`.
        balance = max(0, int(inv.total_minor) - paid - credit)
        if balance == 0:
            continue
        due, assumed = _due(inv.invoice_date, inv.due_date)
        days = (stamp - due).days
        out.append(
            OpenDocument(
                id=inv.id,
                doc_no=inv.invoice_no,
                href=f"/invoices/{inv.id}",
                party_id=inv.customer_id,
                party_name=party_name,
                doc_date=inv.invoice_date,
                due_date=due,
                due_date_assumed=assumed,
                total_minor=int(inv.total_minor),
                allocated_minor=paid,
                credited_minor=credit,
                open_minor=balance,
                status=inv.status,
                days_overdue=days,
                bucket=bucket_for(days),
            )
        )
    return out


def open_bills(
    db: Session, *, supplier_id: uuid.UUID | None = None, as_of: date | None = None
) -> list[OpenDocument]:
    """Every live bill with an open balance, oldest first (R10.8's input).

    The buy-side mirror. There is no credit-note term: credits exist only on the sell
    side, so `credited_minor` is always 0 here and the shape stays the same.
    """
    stamp = as_of or today()
    repo = FinanceRepository(db)
    allocated = repo.allocated_by_bill()

    out: list[OpenDocument] = []
    for bill, party_name in repo.bills_with_party(supplier_id=supplier_id):
        paid = allocated.get(bill.id, 0)
        balance = max(0, int(bill.total_minor) - paid)
        if balance == 0:
            continue
        due, assumed = _due(bill.bill_date, bill.due_date)
        days = (stamp - due).days
        out.append(
            OpenDocument(
                id=bill.id,
                doc_no=bill.bill_no,
                href=f"/bills/{bill.id}",
                party_id=bill.supplier_id,
                party_name=party_name,
                doc_date=bill.bill_date,
                due_date=due,
                due_date_assumed=assumed,
                total_minor=int(bill.total_minor),
                allocated_minor=paid,
                credited_minor=0,
                open_minor=balance,
                status=bill.status,
                days_overdue=days,
                bucket=bucket_for(days),
            )
        )
    return out


class PartyLedgerService:
    """Running statements per customer and per vendor (R10.1–R10.4).

    A projection: it owns no entity, writes nothing, and every figure it shows is
    derived from the append-only ledgers at read time (R10.10, R10.2, G15).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FinanceRepository(db)
        self.customers = CustomerRepository(db)
        self.suppliers = SupplierRepository(db)

    def customer_statement(
        self, customer_id: uuid.UUID, *, as_of: date | None = None
    ) -> PartyStatement:
        """One customer's statement — invoices, credit notes and payments (R10.4).

        The closing balance is `CustomerRepository.outstanding_minor`, THE receivable.
        The lines below are its three terms itemised, so the two agree by construction;
        `test_r10_2_the_statement_closes_on_the_one_receivable_definition` pins it.
        """
        customer = self.customers.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")

        lines: list[LedgerLine] = []
        for inv, _name in self.repo.invoices_with_party(customer_id=customer_id):
            due, assumed = _due(inv.invoice_date, inv.due_date)
            detail = f"Due {due.isoformat()}"
            if assumed:
                detail += " (no terms recorded — due on issue)"
            lines.append(
                LedgerLine(
                    occurred_on=inv.invoice_date,
                    doc_type="invoice",
                    doc_no=inv.invoice_no,
                    href=f"/invoices/{inv.id}",
                    detail=detail,
                    debit_minor=int(inv.total_minor),
                )
            )

        for note in self.repo.credit_notes_for_customer(customer_id):
            lines.append(
                LedgerLine(
                    occurred_on=note.note_date,
                    doc_type="credit_note",
                    doc_no=note.credit_note_no,
                    # The invoice it credits — which, since Part 8 C1, lists its credits.
                    href=f"/invoices/{note.invoice_id}",
                    detail=note.reason or "Credit note",
                    credit_minor=int(note.total_minor),
                )
            )

        for alloc, payment, invoice_no in self.repo.customer_allocations(customer_id):
            lines.append(
                LedgerLine(
                    occurred_on=payment.paid_at.date(),
                    doc_type="payment",
                    doc_no=payment.payment_no,
                    href=f"/invoices/{alloc.invoice_id}",
                    detail=f"{payment.method} · applied to {invoice_no}",
                    credit_minor=int(alloc.amount_minor),
                )
            )

        return PartyStatement(
            side="receivable",
            party_id=customer_id,
            party_name=customer.name,
            party_href=f"/customers/{customer_id}",
            lines=self._with_running_balance(lines),
            closing_balance_minor=self.customers.outstanding_minor(customer_id),
            open_documents=open_invoices(self.db, customer_id=customer_id, as_of=as_of),
        )

    def vendor_statement(
        self, supplier_id: uuid.UUID, *, as_of: date | None = None
    ) -> PartyStatement:
        """One vendor's statement — bills and payments made (R10.1, R10.4).

        Two document types rather than three: a credit note is a sell-side instrument, so
        the buy side has no fourth term to itemise. The closing balance is
        `SupplierRepository.outstanding_minor`, THE payable.
        """
        supplier = self.suppliers.get(supplier_id)
        if supplier is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")

        lines: list[LedgerLine] = []
        for bill, _name in self.repo.bills_with_party(supplier_id=supplier_id):
            due, assumed = _due(bill.bill_date, bill.due_date)
            detail = f"Due {due.isoformat()}"
            if assumed:
                detail += " (no terms recorded — due on issue)"
            lines.append(
                LedgerLine(
                    occurred_on=bill.bill_date,
                    doc_type="bill",
                    doc_no=bill.bill_no,
                    href=f"/bills/{bill.id}",
                    detail=detail,
                    debit_minor=int(bill.total_minor),
                )
            )

        for alloc, payment, bill_no in self.repo.supplier_allocations(supplier_id):
            lines.append(
                LedgerLine(
                    occurred_on=payment.paid_at.date(),
                    doc_type="payment",
                    doc_no=payment.payment_no,
                    href=f"/bills/{alloc.bill_id}",
                    detail=f"{payment.method} · applied to {bill_no}",
                    credit_minor=int(alloc.amount_minor),
                )
            )

        return PartyStatement(
            side="payable",
            party_id=supplier_id,
            party_name=supplier.name,
            party_href=f"/suppliers/{supplier_id}",
            lines=self._with_running_balance(lines),
            closing_balance_minor=self.suppliers.outstanding_minor(supplier_id),
            open_documents=open_bills(self.db, supplier_id=supplier_id, as_of=as_of),
        )

    @staticmethod
    def _with_running_balance(lines: list[LedgerLine]) -> list[LedgerLine]:
        """Sort chronologically and carry the balance down the column (R10.2).

        Sorted by `(date, kind, doc_no)`: a payment ranks after the invoice it settles so
        a same-day settlement never shows a negative balance mid-statement, and `doc_no`
        is the final tiebreak because it is unique and monotonic where an id is not.
        """
        ordered = sorted(
            lines, key=lambda ln: (ln.occurred_on, _LINE_RANK.get(ln.doc_type, 9), ln.doc_no)
        )
        running = 0
        for line in ordered:
            running += line.debit_minor - line.credit_minor
            line.balance_minor = running
        return ordered

    def statement_note(self, statement: PartyStatement) -> str | None:
        """The reconciliation sentence, when the lines and the closing balance differ.

        They cannot differ today — the lines are the closing balance's own terms — so
        this normally returns None. It exists because a silent mismatch is exactly the
        failure R10.x is about, and a screen that says "these figures disagree by ₹X" is
        recoverable where one that quietly shows the wrong total is not.
        """
        gap = statement.closing_balance_minor - statement.line_total_minor
        if gap == 0:
            return None
        return (
            f"The lines below sum to {minor_to_text(statement.line_total_minor)} but the "
            f"balance is {minor_to_text(statement.closing_balance_minor)} — a difference of "
            f"{minor_to_text(gap)}. Report this."
        )
