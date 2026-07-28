"""Customer models (partners domain)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class Customer(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "customer"

    customer_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer_type.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class CustomerContact(Base, EntityMixin):
    __tablename__ = "customer_contact"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CustomerAddress(Base, EntityMixin):
    __tablename__ = "customer_address"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.id"), nullable=False
    )
    address_type: Mapped[str] = mapped_column(String(12), nullable=False, default="billing")
    line1: Mapped[str] = mapped_column(String(200), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(6), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CustomerCreditPolicy(Base, EntityMixin):
    """A customer's credit terms, VERSIONED (R8.3).

    A change appends a new row and stamps `valid_to` on the one it replaces; the current
    policy is the row with `valid_to IS NULL`. Editing a policy in place would destroy the
    answer to "what limit were they on when we approved that order?", which is the only
    reason to keep history at all.

    Part 6 added `delivery_preference` here rather than on `Customer` deliberately: it is
    part of the commercial arrangement that gets renegotiated, so it versions with the
    terms rather than being overwritten alongside the address.
    """

    __tablename__ = "customer_credit_policy"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.id"), nullable=False
    )
    credit_limit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_preference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Why this version exists. Blank on the row `create` writes; required on every change.
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="active")
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomerNote(Base, EntityMixin):
    """A dated note against a customer (R8.5). Append-only in practice: notes are
    soft-deleted with the one helper, never edited into something else."""

    __tablename__ = "customer_note"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.id"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
