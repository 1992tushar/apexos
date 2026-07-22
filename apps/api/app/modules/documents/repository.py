"""Document repository — metadata persistence + list projections."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, document: Document) -> Document:
        self.db.add(document)
        self.db.flush()
        return document

    def get(self, document_id: uuid.UUID) -> Document | None:
        return self.db.scalar(
            select(Document).where(Document.id == document_id, Document.deleted_at.is_(None))
        )

    def search(
        self,
        *,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Document], int]:
        base = select(Document).where(Document.deleted_at.is_(None))
        if entity_type:
            base = base.where(Document.entity_type == entity_type)
        if entity_id:
            base = base.where(Document.entity_id == entity_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = list(
            self.db.scalars(
                base.order_by(Document.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total
