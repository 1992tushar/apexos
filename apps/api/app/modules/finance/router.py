"""Finance router — invoices + payments (in), bills + payments (out), payables."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.finance.schemas import (
    BillDetail,
    BillListRow,
    BillPaymentCreate,
    BillPaymentResult,
    InvoiceDetail,
    InvoiceListRow,
    PaymentCreate,
    PaymentResult,
)
from app.modules.finance.service import BillService, InvoiceService

router = APIRouter(tags=["finance"])


@router.get("/invoices", response_model=list[InvoiceListRow])
def list_invoices(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, _ = InvoiceService(db).list(status=status, page=page, page_size=page_size)
    return items


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    return InvoiceService(db).get(invoice_id)


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentResult, status_code=201)
def add_payment(
    invoice_id: uuid.UUID,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("payment.create")),
):
    return InvoiceService(db).add_payment(invoice_id, payload, actor_id=actor.id)


# --- Bills (buy side) ----------------------------------------------------


@router.get("/bills", response_model=list[BillListRow])
def list_bills(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, _ = BillService(db).list(status=status, page=page, page_size=page_size)
    return items


@router.get("/bills/{bill_id}", response_model=BillDetail)
def get_bill(bill_id: uuid.UUID, db: Session = Depends(get_db)):
    return BillService(db).get(bill_id)


@router.post("/bills/{bill_id}/payments", response_model=BillPaymentResult, status_code=201)
def add_bill_payment(
    bill_id: uuid.UUID,
    payload: BillPaymentCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("payment.create")),
):
    return BillService(db).add_payment(bill_id, payload, actor_id=actor.id)
