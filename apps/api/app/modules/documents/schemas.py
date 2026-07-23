"""Document schemas (Read + paginated envelope). Uploads are multipart, not JSON."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    category: str
    storage_backend: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    created_at: datetime


class DocumentPage(BaseModel):
    items: list[DocumentRead]
    total: int
    page: int
    page_size: int
