"""Document model — file metadata + storage pointer, polymorphically linked.

The bytes live in Cloudflare R2 (or local disk in dev); this row records the
metadata and the `storage_backend` + `storage_key` needed to fetch them.
"""
from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BusinessUnitMixin, EntityMixin


class Document(Base, EntityMixin, BusinessUnitMixin):
    __tablename__ = "document"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    storage_backend: Mapped[str] = mapped_column(String(8), nullable=False, default="local")  # r2 | local
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
