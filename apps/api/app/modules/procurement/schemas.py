"""Procurement schemas (mirror of Sales schemas)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseOrderLineCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    unit_price_minor: int | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: uuid.UUID
    business_unit_id: uuid.UUID | None = None
    order_date: date | None = None
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)


class PurchaseOrderLineRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    sku_code: str | None = None
    qty: Decimal
    qty_received: Decimal
    unit_price_minor: int
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int


class GoodsReceiptLineInput(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)


class GoodsReceiptCreate(BaseModel):
    """Optional per-line quantities for a partial receipt. When omitted, the
    outstanding quantity of every line is received."""

    lines: list[GoodsReceiptLineInput] | None = None


class GoodsReceiptRef(BaseModel):
    id: uuid.UUID
    receipt_no: str
    warehouse_id: uuid.UUID
    status: str
    received_at: datetime | None = None


class BillRef(BaseModel):
    id: uuid.UUID
    bill_no: str
    status: str
    total_minor: int


class PurchaseOrderListRow(BaseModel):
    id: uuid.UUID
    po_no: str
    supplier_name: str | None = None
    status: str
    total_minor: int
    order_date: date
    line_count: int


class PurchaseOrderDetail(BaseModel):
    id: uuid.UUID
    po_no: str
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    business_unit_id: uuid.UUID
    status: str
    order_date: date
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    lines: list[PurchaseOrderLineRead]
    goods_receipts: list[GoodsReceiptRef]
    bills: list[BillRef]


class PurchaseOrderPage(BaseModel):
    items: list[PurchaseOrderListRow]
    total: int
    page: int
    page_size: int


class GoodsReceiptListRow(BaseModel):
    id: uuid.UUID
    receipt_no: str
    purchase_order_id: uuid.UUID
    po_no: str | None = None
    supplier_name: str | None = None
    warehouse_name: str | None = None
    status: str
    received_at: datetime | None = None
    line_count: int
