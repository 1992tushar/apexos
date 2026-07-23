"""Fulfillment models."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, EntityMixin


class Fulfillment(Base, EntityMixin):
    __tablename__ = "fulfillment"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("sales_order.id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("warehouse.id"), nullable=False
    )
    fulfillment_no: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["FulfillmentLine"]] = relationship(
        back_populates="fulfillment", cascade="all, delete-orphan"
    )


class FulfillmentLine(Base, EntityMixin):
    __tablename__ = "fulfillment_line"

    fulfillment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("fulfillment.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    fulfillment: Mapped["Fulfillment"] = relationship(back_populates="lines")
