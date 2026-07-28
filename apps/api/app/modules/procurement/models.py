"""Procurement models — the buy-side mirror of Sales.

`purchase_order` → `goods_receipt` (stock IN) mirrors `sales_order` →
`fulfillment` (stock OUT). `purchase_order_line.qty_received` tracks partial
receipts against the ordered quantity.

Part 3 adds the **pre-order** half in front of the PO: a requisition is the
request ("we need this"), an RFQ asks suppliers what they would charge, and a
quotation is one supplier's answer. Both paths converge on `purchase_order` —
a requisition converts straight to a PO when the price is already known, or via
an RFQ when it is not. Nothing here re-implements the PO; conversion calls
`PurchaseOrderService.create`.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class PurchaseOrder(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "purchase_order"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("supplier.id"), nullable=False
    )
    po_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    order_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # R4.11: part 4 MEASURES lead time (confirm → receipt) rather than having it
    # typed in, so the confirm instant has to survive as data. `updated_at` cannot
    # stand in — any later revision or receipt overwrites it.
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    lines: Mapped[list[PurchaseOrderLine]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.line_no",
    )
    revisions: Mapped[list[PurchaseOrderRevision]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderRevision.revision_no",
    )


class PurchaseOrderLine(Base, EntityMixin):
    __tablename__ = "purchase_order_line"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("purchase_order.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    order: Mapped[PurchaseOrder] = relationship(back_populates="lines")


class GoodsReceipt(Base, EntityMixin):
    __tablename__ = "goods_receipt"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("purchase_order.id"), nullable=False
    )
    # R4.10: which version of the order these goods were accepted against. Nullable
    # only because receipts taken before revisions existed have no answer; every
    # receipt written from now on records one.
    purchase_order_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("purchase_order_revision.id"), nullable=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("warehouse.id"), nullable=False
    )
    receipt_no: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="received")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list[GoodsReceiptLine]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class GoodsReceiptLine(Base, EntityMixin):
    __tablename__ = "goods_receipt_line"

    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("goods_receipt.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")


# ---------------------------------------------------------------------------
# PO revisions — the append-only history of what was agreed (R4.7)
# ---------------------------------------------------------------------------


class PurchaseOrderRevision(Base, EntityMixin):
    """One version of a purchase order's agreed content.

    A confirmed PO must not be mutated in place (R4.7), but a supplier who
    short-ships or re-prices is ordinary business. So each change appends a
    revision holding a **verbatim snapshot** of the lines as agreed, and the live
    `purchase_order_line` rows carry the current figures. Reading revision 1 after
    three revisions returns exactly what was confirmed.

    Never updated or deleted once written — this table is in G4's ledger list.
    There is deliberately no `superseded_at`: the *next* revision's `created_at`
    already says when this one stopped applying, and a column that gets written
    after insert would make the append-only claim untrue.

    `revision_no` 1 is written by `confirm`, not `create` — a draft has no agreement
    to preserve, and R4.7 is a statement about confirmed orders.
    """

    __tablename__ = "purchase_order_revision"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("purchase_order.id", ondelete="CASCADE"), nullable=False
    )
    revision_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    # Null on revision 1 (the confirmed baseline); required for every revision after,
    # because "why did this change" is the whole value of the history.
    reason: Mapped[str | None] = mapped_column(String(400), nullable=True)

    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    order: Mapped[PurchaseOrder] = relationship(back_populates="revisions")
    lines: Mapped[list[PurchaseOrderRevisionLine]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderRevisionLine.line_no",
    )


class PurchaseOrderRevisionLine(Base, EntityMixin):
    """A line as it stood in one revision. Carries no `qty_received`: receipts
    accrue against the live order line, not against a historical snapshot."""

    __tablename__ = "purchase_order_revision_line"

    purchase_order_revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("purchase_order_revision.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    revision: Mapped[PurchaseOrderRevision] = relationship(back_populates="lines")


# ---------------------------------------------------------------------------
# Pre-order: requisition → (RFQ → quotations) → purchase order
# ---------------------------------------------------------------------------


class PurchaseRequisition(Base, EntityMixin, BusinessUnitMixin):
    """"We need this" — a request, before anyone has agreed a price.

    `created_by` (EntityMixin) is the requester; approval is a separate actor and
    reason, recorded here rather than only in the log so the screen can show who
    signed off without replaying activity (R4.2 keeps the log row as well).
    """

    __tablename__ = "purchase_requisition"

    requisition_no: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="requested")
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(String(400), nullable=True)

    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # Where the request went. Exactly one is set once status is 'converted'.
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("purchase_order.id"), nullable=True
    )
    rfq_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("rfq.id"), nullable=True
    )

    lines: Mapped[list[PurchaseRequisitionLine]] = relationship(
        back_populates="requisition",
        cascade="all, delete-orphan",
        order_by="PurchaseRequisitionLine.line_no",
    )


class PurchaseRequisitionLine(Base, EntityMixin):
    __tablename__ = "purchase_requisition_line"

    purchase_requisition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("purchase_requisition.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    requisition: Mapped[PurchaseRequisition] = relationship(back_populates="lines")


class Rfq(Base, EntityMixin, BusinessUnitMixin):
    """A request for quotation, issued to several suppliers at once (R4.3).

    `purchase_requisition_id` is nullable because an RFQ may be raised ad hoc —
    the founder asking the market a question without a requisition behind it.
    """

    __tablename__ = "rfq"

    rfq_no: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="issued")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(String(400), nullable=True)

    purchase_requisition_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("purchase_requisition.id"), nullable=True
    )
    # Set when a quotation wins the comparison; the PO it produced is on the quote.
    awarded_quotation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)

    lines: Mapped[list[RfqLine]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan", order_by="RfqLine.line_no"
    )
    suppliers: Mapped[list[RfqSupplier]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )


class RfqLine(Base, EntityMixin):
    __tablename__ = "rfq_line"

    rfq_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("rfq.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    rfq: Mapped[Rfq] = relationship(back_populates="lines")


class RfqSupplier(Base, EntityMixin):
    """One supplier this RFQ was issued to, and whether they came back."""

    __tablename__ = "rfq_supplier"

    rfq_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("rfq.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("supplier.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="invited")

    rfq: Mapped[Rfq] = relationship(back_populates="suppliers")


class SupplierQuotation(Base, EntityMixin, BusinessUnitMixin):
    """One supplier's answer to an RFQ: prices, lead time, MOQ per line.

    `lead_time_days` is what the supplier *promised*. Part 4 measures the actual
    lead time from PO confirm and receipt timestamps (R4.11) and may disagree —
    that comparison is the point, so this stays a quoted figure and is never
    overwritten from a receipt.
    """

    __tablename__ = "supplier_quotation"

    quotation_no: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("rfq.id"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("supplier.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="received")
    quoted_on: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(400), nullable=True)

    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # The PO this quotation became, once it won the comparison.
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("purchase_order.id"), nullable=True
    )

    lines: Mapped[list[SupplierQuotationLine]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="SupplierQuotationLine.line_no",
    )


class SupplierQuotationLine(Base, EntityMixin):
    __tablename__ = "supplier_quotation_line"

    supplier_quotation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("supplier_quotation.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    moq: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    quotation: Mapped[SupplierQuotation] = relationship(back_populates="lines")
