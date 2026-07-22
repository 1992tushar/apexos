"""CRM models — pipeline_stage (data-driven), lead, opportunity, competitor.

Leads are pre-sale prospects that convert into a `customer`; opportunities move
through `pipeline_stage`s (a data-driven master, D2). Money is integer minor units.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class PipelineStage(Base, EntityMixin):
    """Data-driven opportunity stage (e.g. New → Qualified → Proposal → Won/Lost)."""

    __tablename__ = "pipeline_stage"

    code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_won: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Lead(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "lead"

    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    customer_type_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer_type.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")  # open|converted|lost
    converted_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Opportunity(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "opportunity"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("lead.id"), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customer.id"), nullable=True
    )
    pipeline_stage_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("pipeline_stage.id"), nullable=False
    )
    estimated_value_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")  # open|won|lost
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Competitor(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "competitor"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    strength: Mapped[str | None] = mapped_column(String(24), nullable=True)  # low|medium|high
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
