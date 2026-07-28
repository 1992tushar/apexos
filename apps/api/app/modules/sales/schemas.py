"""Sales order schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SalesOrderLineCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    unit_price_minor: int | None = None


# --- Sales return + credit note (Part 7 C2) -------------------------------


class ReturnLineCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)


class SalesReturnCreate(BaseModel):
    invoice_id: uuid.UUID
    reason: str = Field(min_length=1)
    warehouse_id: uuid.UUID | None = None
    lines: list[ReturnLineCreate] = Field(min_length=1)


class ReturnableLine(BaseModel):
    """What may still come back on one invoice line — all derived (R9.6/G7)."""

    product_id: uuid.UUID
    sku_code: str | None
    product_name: str | None
    invoiced_qty: Decimal
    returned_qty: Decimal
    returnable_qty: Decimal
    unit_price_minor: int
    tax_rate_bps: int

    @property
    def fully_returned(self) -> bool:
        return self.returnable_qty == 0


class SalesReturnLineRead(BaseModel):
    product_id: uuid.UUID
    sku_code: str | None
    product_name: str | None
    qty: Decimal
    unit_price_minor: int
    line_total_minor: int
    line_no: int


class CreditNoteRead(BaseModel):
    id: uuid.UUID
    credit_note_no: str
    invoice_id: uuid.UUID
    note_date: date
    total_minor: int
    reason: str | None


class SalesReturnDetail(BaseModel):
    id: uuid.UUID
    return_no: str
    customer_id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_no: str | None
    return_date: date
    reason: str
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    lines: list[SalesReturnLineRead]
    credit_note: CreditNoteRead | None


# --- Quotation (Part 7 C1) ------------------------------------------------


class QuotationLineCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    # None means "resolve from the price list". A quotation usually names its own price,
    # which is the entire point of quoting.
    unit_price_minor: int | None = None


class QuotationCreate(BaseModel):
    customer_id: uuid.UUID
    business_unit_id: uuid.UUID | None = None
    quotation_date: date | None = None
    valid_until: date | None = None
    note: str | None = None
    lines: list[QuotationLineCreate] = Field(min_length=1)


class QuotationRevise(BaseModel):
    """A new version of a sent quotation. The reason is required — "why did the price
    change" is the whole value of keeping the history (R9.2)."""

    reason: str = Field(min_length=1)
    valid_until: date | None = None
    lines: list[QuotationLineCreate] = Field(min_length=1)


class QuotationLineRead(BaseModel):
    product_id: uuid.UUID
    product_name: str | None = None
    sku_code: str | None = None
    qty: Decimal
    unit_price_minor: int
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int
    line_no: int


class QuotationRevisionRead(BaseModel):
    id: uuid.UUID
    revision_no: int
    reason: str | None
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    created_at: datetime
    is_current: bool
    lines: list[QuotationLineRead]


class QuotationDetail(BaseModel):
    id: uuid.UUID
    quotation_no: str
    customer_id: uuid.UUID
    customer_name: str | None = None
    quotation_date: date
    valid_until: date | None
    status: str
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    sales_order_id: uuid.UUID | None
    sales_order_no: str | None = None
    note: str | None
    lines: list[QuotationLineRead]
    revisions: list[QuotationRevisionRead]
    # Derived, not stored: whether the validity date has passed. Distinct from
    # `status == "expired"`, which is somebody having actually retired it.
    past_validity: bool = False

    @property
    def revision_count(self) -> int:
        return len(self.revisions)

    @property
    def is_open(self) -> bool:
        """Still able to become an order."""
        return self.status in ("draft", "sent")


class QuotationListRow(BaseModel):
    id: uuid.UUID
    quotation_no: str
    customer_name: str | None
    status: str
    quotation_date: date
    valid_until: date | None
    total_minor: int
    revision_count: int
    past_validity: bool


class SalesOrderCreate(BaseModel):
    customer_id: uuid.UUID
    business_unit_id: uuid.UUID | None = None
    order_date: date | None = None
    lines: list[SalesOrderLineCreate] = Field(min_length=1)


class SalesOrderLineRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    sku_code: str | None = None
    qty: Decimal
    unit_price_minor: int
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int


class FulfillmentRef(BaseModel):
    id: uuid.UUID
    fulfillment_no: str
    warehouse_id: uuid.UUID
    status: str
    shipped_at: datetime | None = None


class InvoiceRef(BaseModel):
    id: uuid.UUID
    invoice_no: str
    status: str
    total_minor: int


class SalesOrderListRow(BaseModel):
    id: uuid.UUID
    order_no: str
    customer_name: str | None = None
    status: str
    total_minor: int
    order_date: date
    line_count: int


class SalesOrderDetail(BaseModel):
    id: uuid.UUID
    order_no: str
    customer_id: uuid.UUID
    customer_name: str | None = None
    business_unit_id: uuid.UUID
    status: str
    order_date: date
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    lines: list[SalesOrderLineRead]
    fulfillments: list[FulfillmentRef]
    invoices: list[InvoiceRef]


class SalesOrderPage(BaseModel):
    items: list[SalesOrderListRow]
    total: int
    page: int
    page_size: int
