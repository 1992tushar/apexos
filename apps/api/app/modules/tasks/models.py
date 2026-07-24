"""Task model — an actionable to-do optionally linked to any entity (polymorphic).

`entity_type`/`entity_id` form the polymorphic link (e.g. a task on a
`purchase_order` or a `customer`). Status transitions are `open` → `completed`.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class Task(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "task"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="normal")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
