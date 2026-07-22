"""Identity schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel


class MeRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    permissions: list[str]
