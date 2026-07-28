"""Supplier models (partners domain — the buy-side mirror of Customer).

Structurally mirrors `customers.models`: a `supplier` (→supplier_type) with
contacts and a first-class `supplier_evaluation` scorecard (Foundation §4/§5).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class Supplier(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "supplier"

    supplier_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("supplier_type.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class SupplierContact(Base, EntityMixin):
    __tablename__ = "supplier_contact"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("supplier.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProductSupplier(Base, EntityMixin):
    """Which suppliers a product can be bought from (R5.1) and their MOQ (R5.5).

    The **only** new mutable entity Part 4 adds, and R5.10 names exactly these two
    things as legitimate new master data: a preferred/alternate mapping and a
    minimum order quantity are *recorded facts*, agreed with a supplier.

    What is deliberately NOT here: vendor score, lead time, on-time rate. Those are
    derived from receipt history every time they are shown (G7, R5.10) — storing
    them would make the number a thing that can go stale and disagree with the
    ledger it came from. `app/modules/suppliers/vendor.py` computes them.

    Nor is price: `purchase_price` already holds price per product+supplier with
    `valid_from`/`valid_to`, which is what R5.6's timeline reads.
    """

    __tablename__ = "product_supplier"

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("product.id"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("supplier.id"), nullable=False
    )
    #: Exactly one preferred supplier per product; the service enforces it, because
    #: "preferred" is a statement about the product, not about the link.
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Minimum the supplier will accept on one order (R5.5). Null = none agreed.
    moq: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    note: Mapped[str | None] = mapped_column(String(400), nullable=True)


class SupplierEvaluation(Base, EntityMixin):
    """Vendor scorecard (D-glossary: quality / price / reliability, 1–5 each)."""

    __tablename__ = "supplier_evaluation"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("supplier.id"), nullable=False
    )
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reliability_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluated_on: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
