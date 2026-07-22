"""Sales order models."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
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


class SalesOrder(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "sales_order"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer.id"), nullable=False
    )
    order_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    order_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="SalesOrderLine.line_no"
    )


class SalesOrderLine(Base, EntityMixin):
    __tablename__ = "sales_order_line"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sales_order.id", ondelete="CASCADE"), nullable=False
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

    order: Mapped["SalesOrder"] = relationship(back_populates="lines")
