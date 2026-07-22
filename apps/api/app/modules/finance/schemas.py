"""Finance schemas."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class InvoiceLineRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    qty: Decimal
    unit_price_minor: int
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int


class InvoiceListRow(BaseModel):
    id: uuid.UUID
    invoice_no: str
    customer_name: str | None = None
    total_minor: int
    paid_minor: int
    balance_minor: int
    status: str
    invoice_date: date
    due_date: date | None = None


class InvoiceDetail(BaseModel):
    id: uuid.UUID
    invoice_no: str
    customer_id: uuid.UUID
    customer_name: str | None = None
    sales_order_id: uuid.UUID | None = None
    status: str
    invoice_date: date
    due_date: date | None = None
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    paid_minor: int
    balance_minor: int
    lines: list[InvoiceLineRead]


class PaymentCreate(BaseModel):
    amount_minor: int = Field(gt=0)
    method: str = "bank"


class PaymentResult(BaseModel):
    payment_id: uuid.UUID
    payment_no: str
    invoice_id: uuid.UUID
    amount_minor: int
    invoice_status: str
    balance_minor: int


# --- Bills (buy side; mirror of Invoice) ---------------------------------


class BillLineRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    qty: Decimal
    unit_price_minor: int
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int


class BillListRow(BaseModel):
    id: uuid.UUID
    bill_no: str
    supplier_name: str | None = None
    total_minor: int
    paid_minor: int
    balance_minor: int
    status: str
    bill_date: date
    due_date: date | None = None


class BillDetail(BaseModel):
    id: uuid.UUID
    bill_no: str
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    purchase_order_id: uuid.UUID | None = None
    status: str
    bill_date: date
    due_date: date | None = None
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    paid_minor: int
    balance_minor: int
    lines: list[BillLineRead]


class BillPaymentCreate(BaseModel):
    amount_minor: int = Field(gt=0)
    method: str = "bank"


class BillPaymentResult(BaseModel):
    payment_id: uuid.UUID
    payment_no: str
    bill_id: uuid.UUID
    amount_minor: int
    bill_status: str
    balance_minor: int
