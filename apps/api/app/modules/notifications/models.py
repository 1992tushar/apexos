"""Notification model — an in-app message, optionally linked to an entity."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, EntityMixin


class Notification(Base, EntityMixin):
    __tablename__ = "notification"

    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(12), nullable=False, default="info")  # info|success|warning|error
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
