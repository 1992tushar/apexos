"""Activity log (append-only domain event stream, D10)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, EntityMixin


class ActivityLog(Base, EntityMixin):
    __tablename__ = "activity_log"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    verb: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
