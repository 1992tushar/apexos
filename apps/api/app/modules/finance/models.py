"""Finance models (append-only ledgers, D3). Receivable is derived:
invoice.total − Σ allocations."""
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
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class Invoice(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "invoice"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer.id"), nullable=False
    )
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sales_order.id"), nullable=True
    )
    invoice_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    invoice_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="issued")
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceLine(Base, EntityMixin):
    __tablename__ = "invoice_line"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoice.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")


class Bill(Base, EntityMixin, BusinessUnitMixin):
    """Supplier bill — the buy-side mirror of Invoice (append-only, D3).
    Payable is derived: bill.total − Σ allocations."""

    __tablename__ = "bill"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("supplier.id"), nullable=False
    )
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("purchase_order.id"), nullable=True
    )
    bill_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    bill_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="issued")
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    lines: Mapped[list["BillLine"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan"
    )


class BillLine(Base, EntityMixin):
    __tablename__ = "bill_line"

    bill_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bill.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    bill: Mapped["Bill"] = relationship(back_populates="lines")


class Payment(Base, EntityMixin):
    __tablename__ = "payment"

    direction: Mapped[str] = mapped_column(String(3), nullable=False)  # in | out
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer.id"), nullable=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("supplier.id"), nullable=True
    )
    payment_no: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )


class PaymentAllocation(Base, EntityMixin):
    __tablename__ = "payment_allocation"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payment.id"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoice.id"), nullable=True
    )
    bill_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bill.id"), nullable=True
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    payment: Mapped["Payment"] = relationship(back_populates="allocations")
