"""Declarative base and shared column mixins (decisions D6, D7, D1).

Every entity table inherits `Base` + `EntityMixin`, giving it a UUIDv7 primary
key, full audit columns, and soft-delete. Operational tables additionally mix in
`BusinessUnitMixin` (decision D1: business_unit as a first-class dimension).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.uuid7 import uuid7


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all ApexOS models."""


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid7
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class EntityMixin(UUIDMixin, TimestampMixin, AuditMixin):
    """Standard mixin for all entities: UUIDv7 PK + audit columns + soft-delete."""


class BusinessUnitMixin:
    """Adds the first-class `business_unit_id` dimension (decision D1)."""

    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("business_unit.id"), nullable=False, index=True
    )
