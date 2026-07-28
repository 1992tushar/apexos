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
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class SalesOrder(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "sales_order"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.id"), nullable=False
    )
    order_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    order_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    lines: Mapped[list[SalesOrderLine]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="SalesOrderLine.line_no"
    )


class SalesOrderLine(Base, EntityMixin):
    __tablename__ = "sales_order_line"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("sales_order.id", ondelete="CASCADE"), nullable=False
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

    order: Mapped[SalesOrder] = relationship(back_populates="lines")


# ---------------------------------------------------------------------------
# Quotation (Part 7 C1) — the gap BEFORE the order
# ---------------------------------------------------------------------------


class Quotation(Base, EntityMixin, BusinessUnitMixin):
    """A price offered to a customer, before there is an order (R9.1).

    draft → sent → (revised…) → converted, or → expired. The live `quotation_line` rows
    carry the current figures; every version that was actually SENT is preserved verbatim
    in `quotation_revision` (R9.2).

    Deliberately its own document type — `SQT`, not `QUO`. `QUO` already numbers Part 3's
    *supplier* quotations, and sharing a type would interleave two unrelated sequences in
    `number_sequence`, which is invisible until the numbering looks wrong.

    `sales_order_id` records what this became (R9.3). Null until converted, and set once —
    a quotation converts to exactly one order.
    """

    __tablename__ = "quotation"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.id"), nullable=False, index=True
    )
    quotation_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    quotation_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    # What the customer was told the price holds until. Nullable: not every quote carries
    # an expiry, and inventing one would be a fact nobody agreed to.
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("sales_order.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(400), nullable=True)

    lines: Mapped[list[QuotationLine]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationLine.line_no",
    )
    revisions: Mapped[list[QuotationRevision]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationRevision.revision_no",
    )


class QuotationLine(Base, EntityMixin):
    __tablename__ = "quotation_line"

    quotation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("quotation.id", ondelete="CASCADE"), nullable=False
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

    quotation: Mapped[Quotation] = relationship(back_populates="lines")


class QuotationRevision(Base, EntityMixin):
    """One version of a quotation, exactly as it was sent (R9.2).

    The same shape Part 3 gave `PurchaseOrderRevision`, and mirrored rather than reinvented
    on purpose: append-only, current = `max(revision_no)`, and **deliberately no
    `superseded_at`** — the next revision's `created_at` already says when this one stopped
    applying, and a column written after insert would make the append-only claim untrue.
    This table is in G4's ledger list.

    `revision_no` 1 is written by `send`, not `create`. A draft nobody has seen has no
    agreement to preserve, which is the same reasoning R4.7 used for an unconfirmed PO.
    """

    __tablename__ = "quotation_revision"

    quotation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("quotation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    # Null on revision 1 (the baseline that was sent); required on every revision after,
    # because "why did the price change" is the whole value of the history.
    reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
    subtotal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    quotation: Mapped[Quotation] = relationship(back_populates="revisions")
    lines: Mapped[list[QuotationRevisionLine]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="QuotationRevisionLine.line_no",
    )


class QuotationRevisionLine(Base, EntityMixin):
    """A quoted line as it stood in one revision — the verbatim snapshot R9.2 requires."""

    __tablename__ = "quotation_revision_line"

    quotation_revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("quotation_revision.id", ondelete="CASCADE"), nullable=False
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

    revision: Mapped[QuotationRevision] = relationship(back_populates="lines")
