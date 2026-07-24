"""Finance pages: receivables (invoices) + payables (bills) with inline payments.

The /finance index lists both ledgers with stat tiles for total outstanding, and
each open document carries an inline "record payment" form. Detail pages render
the document's lines and totals. All writes go through the domain services with
`actor_id`; on a caught domain error we `db.rollback()` and PRG-redirect back.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, get_current_actor
from app.modules.finance.schemas import BillPaymentCreate, PaymentCreate
from app.modules.finance.service import BillService, InvoiceService
from app.web.core import form_action, render

router = APIRouter()

INVOICE_STATUSES = ["issued", "part_paid", "paid", "cancelled"]
BILL_STATUSES = ["issued", "part_paid", "paid", "cancelled"]
PAYMENT_METHODS = ["cash", "bank", "upi", "cheque", "card"]


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
    actor: Actor = Depends(get_current_actor),
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
    actor: Actor = Depends(get_current_actor),
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
    return render(request, "finance/invoice.html", inv=inv)


@router.get("/bills/{bill_id}")
def bill_detail(request: Request, bill_id: uuid.UUID, db: Session = Depends(get_db)):
    # A missing bill raises NotFoundError → the web error handler renders error.html.
    bill = BillService(db).get(bill_id)
    return render(request, "finance/bill.html", bill=bill)
