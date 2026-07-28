"""Procurement schemas (mirror of Sales schemas)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.db.explain import Explained


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
    # R4.9: the back order, DERIVED as ordered − received every time it is read
    # (G7). Never stored — a counter would be one bug away from disagreeing with
    # the receipts that produced it.
    open_qty: Decimal
    unit_price_minor: int
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int


class PurchaseOrderReviseLine(BaseModel):
    """A line's new figures. Identified by product, because that is what the
    founder is looking at on the screen; omitted lines keep what they had."""

    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    unit_price_minor: int | None = None


class PurchaseOrderRevise(BaseModel):
    """R4.7 — a change to a confirmed PO. The reason is required, not decorative:
    it is the only thing that explains the revision to whoever reads it later."""

    reason: str = Field(min_length=1)
    lines: list[PurchaseOrderReviseLine] = Field(min_length=1)


class PurchaseOrderRevisionLineRead(BaseModel):
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


class PurchaseOrderRevisionRead(BaseModel):
    id: uuid.UUID
    revision_no: int
    reason: str | None = None
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    created_at: datetime
    is_current: bool
    lines: list[PurchaseOrderRevisionLineRead]


class GoodsReceiptLineInput(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)


class GoodsReceiptCreate(BaseModel):
    """Optional per-line quantities for a partial receipt. When omitted, the
    outstanding quantity of every line is received."""

    lines: list[GoodsReceiptLineInput] | None = None
    # R4.10: the revision the goods were checked against. Passing a superseded one
    # is refused rather than quietly accepted — see GoodsReceiptService.receive.
    # Omitted means "whatever is current", which is what an unrevised PO wants.
    against_revision_no: int | None = None
    # When the goods actually arrived, if that is not now — a delivery taken on
    # Saturday and keyed in on Monday arrived on Saturday, and R5.3 measures lead
    # time from it. Set at insert, never patched afterwards (G4).
    received_at: datetime | None = None


class GoodsReceiptRef(BaseModel):
    id: uuid.UUID
    receipt_no: str
    warehouse_id: uuid.UUID
    status: str
    received_at: datetime | None = None
    revision_no: int | None = None


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
    confirmed_at: datetime | None = None
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    # 0 on a draft (nothing agreed yet); 1 once confirmed; higher after a revision.
    revision_no: int = 0
    # R4.9: the order's total back order, summed from the derived per-line figures.
    open_qty_total: Decimal = Decimal("0")
    lines: list[PurchaseOrderLineRead]
    revisions: list[PurchaseOrderRevisionRead] = []
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


# --- pre-order: requisitions -------------------------------------------------


class RequisitionLineCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)


class RequisitionCreate(BaseModel):
    business_unit_id: uuid.UUID | None = None
    needed_by: date | None = None
    note: str | None = None
    lines: list[RequisitionLineCreate] = Field(min_length=1)


class RequisitionLineRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    sku_code: str | None = None
    qty: Decimal
    line_no: int


class RequisitionListRow(BaseModel):
    id: uuid.UUID
    requisition_no: str
    status: str
    needed_by: date | None = None
    created_at: datetime
    line_count: int
    qty_total: Decimal
    outcome: str | None = None  # the PO or RFQ number it became


class RequisitionDetail(BaseModel):
    id: uuid.UUID
    requisition_no: str
    status: str
    needed_by: date | None = None
    note: str | None = None
    business_unit_id: uuid.UUID
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    approval_reason: str | None = None
    purchase_order_id: uuid.UUID | None = None
    po_no: str | None = None
    rfq_id: uuid.UUID | None = None
    rfq_no: str | None = None
    lines: list[RequisitionLineRead]


# --- pre-order: RFQs + quotations -------------------------------------------


class RfqLineCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)


class RfqCreate(BaseModel):
    """An ad-hoc RFQ (R4.3). A requisition-driven one goes through
    `RequisitionService.convert_to_rfq`, which copies the lines."""

    supplier_ids: list[uuid.UUID] = Field(min_length=1)
    business_unit_id: uuid.UUID | None = None
    due_date: date | None = None
    note: str | None = None
    lines: list[RfqLineCreate] = Field(min_length=1)


class QuotationLineInput(BaseModel):
    product_id: uuid.UUID
    unit_price_minor: int = Field(ge=0)
    qty: Decimal | None = None  # defaults to the RFQ line's quantity
    moq: Decimal | None = None


class QuotationCreate(BaseModel):
    supplier_id: uuid.UUID
    quoted_on: date | None = None
    valid_until: date | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    note: str | None = None
    lines: list[QuotationLineInput] = Field(min_length=1)


class QuotationLineRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    sku_code: str | None = None
    qty: Decimal
    unit_price_minor: int
    moq: Decimal | None = None
    tax_rate_bps: int
    line_subtotal_minor: int
    line_tax_minor: int
    line_total_minor: int


class QuotationRead(BaseModel):
    id: uuid.UUID
    quotation_no: str
    rfq_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    status: str
    quoted_on: date
    valid_until: date | None = None
    lead_time_days: int | None = None
    note: str | None = None
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    purchase_order_id: uuid.UUID | None = None
    po_no: str | None = None
    lines: list[QuotationLineRead]


class QuoteComparisonLine(BaseModel):
    """One product's numbers from one supplier, for the side-by-side (R4.5)."""

    product_id: uuid.UUID
    unit_price_minor: int | None = None
    #: The minimum this supplier stated *in this quote*.
    moq: Decimal | None = None
    #: The standing minimum on the product↔supplier mapping (R5.5). Separate from
    #: `moq` on purpose: what a supplier quoted once and what was agreed with them
    #: are different facts, and a founder comparing quotes wants to see both.
    agreed_moq: Decimal | None = None
    is_cheapest: bool = False


class QuoteComparisonColumn(BaseModel):
    """A quoting supplier's column in the comparison."""

    quotation_id: uuid.UUID
    quotation_no: str
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    status: str
    lead_time_days: int | None = None
    total_minor: int
    is_cheapest_total: bool = False
    is_fastest: bool = False
    #: The measured vendor score, already rendered — "75" or literally "unknown"
    #: (R5.2/R5.11). A string because there is no number to show without history.
    score: str | None = None
    #: The same score with its arithmetic, so the grid can satisfy G11 rather than
    #: printing a bare figure. `.display` is what `score` above holds.
    score_explained: Explained | None = None
    cells: dict[uuid.UUID, QuoteComparisonLine]


class QuoteComparison(BaseModel):
    """The comparison as a grid: RFQ lines down, quoting suppliers across."""

    rfq_id: uuid.UUID
    rfq_no: str
    lines: list[RequisitionLineRead]  # same shape: product + qty per RFQ line
    columns: list[QuoteComparisonColumn]
    invited_not_quoted: list[str]  # supplier names still silent


class RfqSupplierRead(BaseModel):
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    status: str


class RfqListRow(BaseModel):
    id: uuid.UUID
    rfq_no: str
    status: str
    due_date: date | None = None
    created_at: datetime
    supplier_count: int
    quote_count: int
    line_count: int


class RfqDetail(BaseModel):
    id: uuid.UUID
    rfq_no: str
    status: str
    issued_at: datetime | None = None
    due_date: date | None = None
    note: str | None = None
    business_unit_id: uuid.UUID
    purchase_requisition_id: uuid.UUID | None = None
    requisition_no: str | None = None
    awarded_quotation_id: uuid.UUID | None = None
    lines: list[RequisitionLineRead]
    suppliers: list[RfqSupplierRead]
    quotations: list[QuotationRead]
    comparison: QuoteComparison


class QuotationHistoryRow(BaseModel):
    """One past quote for a product from a supplier (R4.6)."""

    quotation_id: uuid.UUID
    quotation_no: str
    rfq_no: str | None = None
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    quoted_on: date
    unit_price_minor: int
    moq: Decimal | None = None
    lead_time_days: int | None = None
    status: str
