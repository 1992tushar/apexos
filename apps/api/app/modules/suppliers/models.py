"""Supplier models (partners domain — the buy-side mirror of Customer).

Structurally mirrors `customers.models`: a `supplier` (→supplier_type) with
contacts and a first-class `supplier_evaluation` scorecard (Foundation §4/§5).
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class Supplier(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "supplier"

    supplier_type_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("supplier_type.id"), nullable=False
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
        PGUUID(as_uuid=True), ForeignKey("supplier.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SupplierEvaluation(Base, EntityMixin):
    """Vendor scorecard (D-glossary: quality / price / reliability, 1–5 each)."""

    __tablename__ = "supplier_evaluation"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("supplier.id"), nullable=False
    )
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reliability_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluated_on: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
