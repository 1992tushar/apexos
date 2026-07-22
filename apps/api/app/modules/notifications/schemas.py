"""Notification schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str | None = None
    level: str = "info"
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    body: str | None = None
    level: str
    is_read: bool
    read_at: datetime | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationRead]
    unread: int
