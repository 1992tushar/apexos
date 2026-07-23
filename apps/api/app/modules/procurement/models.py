"""Procurement models — the buy-side mirror of Sales.

`purchase_order` → `goods_receipt` (stock IN) mirrors `sales_order` →
`fulfillment` (stock OUT). `purchase_order_line.qty_received` tracks partial
receipts against the ordered quantity.
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
    func,
)
from sqlalchemy import Uuid
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

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.line_no",
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

    order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")


class GoodsReceipt(Base, EntityMixin):
    __tablename__ = "goods_receipt"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("purchase_order.id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("warehouse.id"), nullable=False
    )
    receipt_no: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="received")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["GoodsReceiptLine"]] = relationship(
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

    receipt: Mapped["GoodsReceipt"] = relationship(back_populates="lines")
