"""Task schemas (Create / Read + paginated envelope)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: str = "normal"
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    business_unit_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None
    status: str | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None = None
    status: str
    priority: str
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    completed_at: datetime | None = None
    created_at: datetime


class TaskPage(BaseModel):
    items: list[TaskRead]
    total: int
    page: int
    page_size: int
