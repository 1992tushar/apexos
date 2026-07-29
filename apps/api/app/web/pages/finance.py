"""Finance pages: receivables (invoices) + payables (bills) with inline payments.

The /finance index lists both ledgers with stat tiles for total outstanding, and
each open document carries an inline "record payment" form. Detail pages render
the document's lines and totals. All writes go through the domain services with
`actor_id`; on a caught domain error we `db.rollback()` and PRG-redirect back.

Part 8 C1 adds four read-only screens over the same ledgers — the party statement
(R10.1), AR/AP ageing (R10.5), the collections list (R10.7) and payments due
(R10.8) — plus the allocation form (R10.9). Each of the four offers CSV export
through Part 2's one export path (R10.12), and each honours the state in the query
string exactly as its screen shows it: the export is `csv_rows_response` over the
rows already projected, so "the export matches what is on screen" is structural.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.db.listing import Column, ListSpec
from app.modules.customers.models import Customer
from app.modules.finance.ageing import AgeingService, bucket_boundaries
from app.modules.finance.allocation import AllocationService
from app.modules.finance.cash import CashFlowService, default_window
from app.modules.finance.ledger import PartyLedgerService, today
from app.modules.finance.models import Bill, Invoice, Payment
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import (
    AR_AGE_BUCKETS,
    AllocationCreate,
    BillPaymentCreate,
    PaymentCreate,
)
from app.modules.finance.service import BillService, InvoiceService
from app.web.core import form_action, render
from app.web.listing import csv_rows_response, wants_csv
from app.web.security import require_web_permission

router = APIRouter()

INVOICE_STATUSES = ["issued", "part_paid", "paid", "cancelled"]
BILL_STATUSES = ["issued", "part_paid", "paid", "cancelled"]
PAYMENT_METHODS = ["cash", "bank", "upi", "cheque", "card"]

# --- export specs (R10.12) --------------------------------------------------
#
# A `ListSpec` here is used for its COLUMNS only: these rows are service projections,
# not a `query_page` result, so `csv_rows_response` formats what the screen already
# holds. That is Part 2's one CSV writer reused, not a second one — `ReportService.to_csv`
# is already a second and a third would be indefensible.

LEDGER_EXPORT = ListSpec(
    entity="statement",
    model=Invoice,
    columns=(
        Column("occurred_on", "Date", kind="date"),
        Column("doc_type", "Type"),
        Column("doc_no", "Document", kind="mono"),
        Column("detail", "Detail"),
        Column("debit_minor", "Debit", kind="money"),
        Column("credit_minor", "Credit", kind="money"),
        Column("balance_minor", "Balance", kind="money"),
    ),
)

AGEING_EXPORT = ListSpec(
    entity="ageing",
    model=Customer,
    columns=(
        Column("party_name", "Party"),
        Column("outstanding_minor", "Outstanding", kind="money"),
        Column("due_minor", "Not yet due", kind="money"),
        Column("overdue_minor", "Overdue", kind="money"),
        # Generated from the constant, so a bucket added there appears in the export.
        *(Column(f"bucket_{key}", label, kind="money") for key, label, _u in AR_AGE_BUCKETS),
        Column("unaged_minor", "Credits not against an open document", kind="money"),
        Column("open_count", "Open documents", kind="number"),
        Column("oldest_days_overdue", "Oldest days overdue", kind="number"),
    ),
)

COLLECTIONS_EXPORT = ListSpec(
    entity="collections",
    model=Customer,
    columns=(
        Column("customer_name", "Customer"),
        Column("overdue_minor", "Overdue", kind="money"),
        Column("outstanding_minor", "Outstanding", kind="money"),
        Column("oldest_days_overdue", "Days overdue", kind="number"),
        Column("oldest_doc_no", "Oldest invoice", kind="mono"),
        Column("open_count", "Open invoices", kind="number"),
        Column("reason", "Reason"),
    ),
)

PAYMENTS_DUE_EXPORT = ListSpec(
    entity="payments-due",
    model=Bill,
    columns=(
        Column("bill_no", "Bill", kind="mono"),
        Column("supplier_name", "Supplier"),
        Column("due_date", "Due", kind="date"),
        Column("days_overdue", "Days overdue", kind="number"),
        Column("bucket_label", "Bucket"),
        Column("open_minor", "Open", kind="money"),
    ),
)

CASH_FLOW_EXPORT = ListSpec(
    entity="cash-flow",
    model=Payment,
    columns=(
        Column("label", "Month"),
        Column("in_minor", "Cash in", kind="money"),
        Column("out_minor", "Cash out", kind="money"),
        Column("net_minor", "Net", kind="money"),
        Column("receipts", "Receipts", kind="number"),
        Column("payments", "Payments", kind="number"),
    ),
)

CASH_CYCLE_EXPORT = ListSpec(
    entity="cash-cycle",
    model=Payment,
    columns=(
        Column("component", "Component"),
        Column("days", "Days", kind="number"),
        Column("formula", "Formula"),
        Column("window", "Window"),
    ),
)


def _as_of(raw: str | None) -> date:
    """The report date from the query string, degrading to today on anything odd.

    A stale bookmark renders the screen rather than an error page — the same rule
    `params_from_request` applies to a filter value it cannot coerce.
    """
    if raw:
        try:
            return date.fromisoformat(raw.strip())
        except ValueError:
            pass
    return today()


def _window(raw_from: str | None, raw_to: str | None) -> tuple[date, date]:
    """The `(date_from, date_to)` for a flow screen (R11.13's parameters, off the URL).

    Degrades the same way `_as_of` does, and additionally repairs a reversed window: a
    bookmark with `from` after `to` renders the swapped range rather than an empty screen
    that looks like "no cash moved".
    """
    default_from, default_to = default_window()
    start = _as_of(raw_from) if raw_from else default_from
    end = _as_of(raw_to) if raw_to else default_to
    return (end, start) if start > end else (start, end)


@router.get("/finance")
def finance_index(
    request: Request,
    inv_status: str | None = None,
    bill_status: str | None = None,
    db: Session = Depends(get_db),
):
    invoices, _ = InvoiceService(db).list(status=inv_status or None, page=1, page_size=200)
    bills, _ = BillService(db).list(status=bill_status or None, page=1, page_size=200)
    receivable = sum(i.balance_minor for i in invoices)
    payable = sum(b.balance_minor for b in bills)
    return render(
        request,
        "finance/index.html",
        invoices=invoices,
        bills=bills,
        receivable=receivable,
        payable=payable,
        inv_status=inv_status or "",
        bill_status=bill_status or "",
        invoice_statuses=INVOICE_STATUSES,
        bill_statuses=BILL_STATUSES,
        methods=PAYMENT_METHODS,
    )


@router.post("/invoices/{invoice_id}/payments")
def record_invoice_payment(
    request: Request,
    invoice_id: uuid.UUID,
    amount_rupees: str = Form(...),
    method: str = Form("bank"),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("payment.create")),
):
    def work():
        payload = PaymentCreate(
            amount_minor=int(round(float(amount_rupees) * 100)), method=method
        )
        return InvoiceService(db).add_payment(invoice_id, payload, actor_id=actor.id)

    return form_action(
        db, work, back="/finance",
        success=("/finance", "Payment recorded"),
        err="Could not record payment",
    )


@router.post("/bills/{bill_id}/payments")
def record_bill_payment(
    request: Request,
    bill_id: uuid.UUID,
    amount_rupees: str = Form(...),
    method: str = Form("bank"),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("payment.create")),
):
    def work():
        payload = BillPaymentCreate(
            amount_minor=int(round(float(amount_rupees) * 100)), method=method
        )
        return BillService(db).add_payment(bill_id, payload, actor_id=actor.id)

    return form_action(
        db, work, back="/finance",
        success=("/finance", "Payment recorded"),
        err="Could not record payment",
    )


@router.get("/invoices/{invoice_id}")
def invoice_detail(request: Request, invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    # A missing invoice raises NotFoundError → the web error handler renders error.html.
    inv = InvoiceService(db).get(invoice_id)
    repo = FinanceRepository(db)
    # R10.3: what was applied to this invoice, and why the balance is what it is. Payments
    # have no page of their own and credit notes rendered only on the customer page, so
    # before Part 8 a reduced balance had nowhere to drill through to.
    return render(
        request,
        "finance/invoice.html",
        inv=inv,
        applied=[
            {
                "payment_no": payment.payment_no,
                "paid_at": payment.paid_at,
                "method": payment.method,
                "amount_minor": alloc.amount_minor,
            }
            for alloc, payment in repo.allocations_for_invoice(invoice_id)
        ],
        credits=repo.credit_notes_for_invoice(invoice_id),
    )


@router.get("/bills/{bill_id}")
def bill_detail(request: Request, bill_id: uuid.UUID, db: Session = Depends(get_db)):
    # A missing bill raises NotFoundError → the web error handler renders error.html.
    bill = BillService(db).get(bill_id)
    return render(
        request,
        "finance/bill.html",
        bill=bill,
        applied=[
            {
                "payment_no": payment.payment_no,
                "paid_at": payment.paid_at,
                "method": payment.method,
                "amount_minor": alloc.amount_minor,
            }
            for alloc, payment in FinanceRepository(db).allocations_for_bill(bill_id)
        ],
    )


# --- Part 8 C1: the four projections (R10.1, R10.5, R10.7, R10.8) -----------


@router.get("/finance/ledger")
def finance_ledger(
    request: Request,
    side: str = "receivable",
    customer_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    """A party's running statement (R10.1–R10.4).

    Renders with no party selected — the route walk requests every plain GET blind and a
    500 there would be a broken screen, so "pick a party" is a real empty state rather
    than an accident.
    """
    payable = side == "payable"
    repo = FinanceRepository(db)
    parties = repo.suppliers_with_activity() if payable else repo.customers_with_activity()
    party_id = supplier_id if payable else customer_id

    statement = None
    note = None
    if party_id is not None:
        svc = PartyLedgerService(db)
        statement = (
            svc.vendor_statement(party_id) if payable else svc.customer_statement(party_id)
        )
        note = svc.statement_note(statement)
        if wants_csv(request):
            return csv_rows_response(LEDGER_EXPORT, statement.lines)

    return render(
        request,
        "finance/ledger.html",
        side="payable" if payable else "receivable",
        parties=parties,
        party_id=party_id,
        statement=statement,
        note=note,
        methods=PAYMENT_METHODS,
    )


@router.get("/finance/ageing")
def finance_ageing(
    request: Request,
    side: str = "receivable",
    as_of: str | None = None,
    db: Session = Depends(get_db),
):
    """AR or AP outstanding, aged, with the due-vs-overdue split (R10.5, R10.6)."""
    stamp = _as_of(as_of)
    svc = AgeingService(db)
    report = svc.ap_ageing(as_of=stamp) if side == "payable" else svc.ar_ageing(as_of=stamp)
    if wants_csv(request):
        return csv_rows_response(AGEING_EXPORT, [row.flat() for row in report.rows])
    return render(
        request,
        "finance/ageing.html",
        report=report,
        side=report.side,
        as_of=stamp.isoformat(),
        boundaries=bucket_boundaries(),
    )


@router.get("/finance/collections")
def finance_collections(request: Request, as_of: str | None = None, db: Session = Depends(get_db)):
    """Who to chase today, in priority order, with the reason per entry (R10.7)."""
    stamp = _as_of(as_of)
    entries = AgeingService(db).collections(as_of=stamp)
    if wants_csv(request):
        return csv_rows_response(COLLECTIONS_EXPORT, [e.flat() for e in entries])
    return render(
        request,
        "finance/collections.html",
        entries=entries,
        as_of=stamp.isoformat(),
        total_overdue=sum(e.overdue_minor for e in entries),
        methods=PAYMENT_METHODS,
    )


@router.get("/finance/payments-due")
def finance_payments_due(request: Request, as_of: str | None = None, db: Session = Depends(get_db)):
    """The bills to pay, oldest due first (R10.8)."""
    stamp = _as_of(as_of)
    entries = AgeingService(db).payments_due(as_of=stamp)
    if wants_csv(request):
        return csv_rows_response(PAYMENTS_DUE_EXPORT, [e.flat() for e in entries])
    return render(
        request,
        "finance/payments_due.html",
        entries=entries,
        as_of=stamp.isoformat(),
        total_due=sum(e.open_minor for e in entries),
        overdue_total=sum(e.open_minor for e in entries if e.days_overdue > 0),
        methods=PAYMENT_METHODS,
    )


@router.get("/finance/cash-flow")
def finance_cash_flow(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    """Cash in vs out over a window, actual and committed (R11.1, R11.2)."""
    start, end = _window(date_from, date_to)
    report = CashFlowService(db).cash_flow(date_from=start, date_to=end)
    if wants_csv(request):
        return csv_rows_response(CASH_FLOW_EXPORT, [row.flat() for row in report.rows])
    return render(
        request,
        "finance/cash_flow.html",
        report=report,
        date_from=start.isoformat(),
        date_to=end.isoformat(),
    )


@router.get("/finance/cash-cycle")
def finance_cash_cycle(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
):
    """Working capital as at the window's end, and the cycle over it (R11.3, R11.4)."""
    start, end = _window(date_from, date_to)
    svc = CashFlowService(db)
    cycle = svc.cash_conversion_cycle(date_from=start, date_to=end)
    if wants_csv(request):
        return csv_rows_response(CASH_CYCLE_EXPORT, cycle.flat_rows())
    return render(
        request,
        "finance/cash_cycle.html",
        cycle=cycle,
        snapshot=svc.working_capital(as_of=end),
        date_from=start.isoformat(),
        date_to=end.isoformat(),
    )


@router.post("/finance/allocate")
def allocate_across_documents(
    request: Request,
    side: str = Form("receivable"),
    party_id: uuid.UUID = Form(...),
    amount_rupees: str = Form(...),
    method: str = Form("bank"),
    back: str = Form("/finance/collections"),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("payment.create")),
):
    """Spread one receipt or payment across the party's open documents (R10.9)."""
    payable = side == "payable"

    def work():
        payload = AllocationCreate(
            amount_minor=int(round(float(amount_rupees) * 100)), method=method
        )
        svc = AllocationService(db)
        return (
            svc.allocate_payment(party_id, payload, actor_id=actor.id)
            if payable
            else svc.allocate_receipt(party_id, payload, actor_id=actor.id)
        )

    def flash(result):
        settled = sum(1 for line in result.lines if line.open_after_minor == 0)
        return back, (
            f"{result.payment_no}: applied across {len(result.lines)} document(s), "
            f"{settled} settled"
        )

    return form_action(db, work, back=back, success=flash, err="Could not apply the payment")
