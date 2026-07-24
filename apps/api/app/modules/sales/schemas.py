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
