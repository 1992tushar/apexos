"""Document service — upload/list/fetch with a pluggable storage backend.

Storage is Cloudflare R2 when configured (all `R2_*` env vars set), otherwise a
local-disk fallback under `settings.documents_local_dir` (gitignored) so the app
runs locally without cloud credentials. `upload` records metadata + emits one
`activity_log` row (D10). The R2 client is imported lazily so `boto3` is only
required when R2 is actually enabled.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.db.soft_delete import soft_delete
from app.db.uuid7 import uuid7
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit
from app.modules.documents.models import DEFAULT_CATEGORY, DOCUMENT_CATEGORIES, Document
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import DocumentRead

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(filename: str) -> str:
    cleaned = _SAFE.sub("_", (filename or "file").strip()) or "file"
    return cleaned[:180]


def _clean_category(category: str | None) -> str:
    """Coerce an incoming category to one of the canonical values."""
    value = (category or "").strip().lower()
    return value if value in DOCUMENT_CATEGORIES else DEFAULT_CATEGORY


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DocumentRepository(db)
        self.activity = ActivityService(db)

    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    # --- storage backends ----------------------------------------------
    def _store(self, key: str, data: bytes, content_type: str) -> str:
        """Persist bytes and return the backend used ('r2' | 'local')."""
        backend = settings.documents_backend
        if backend == "r2":
            self._store_r2(key, data, content_type)
            return "r2"
        self._store_local(key, data)
        return "local"

    def _store_local(self, key: str, data: bytes) -> None:
        root = Path(settings.documents_local_dir)
        path = root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _store_r2(self, key: str, data: bytes, content_type: str) -> None:
        # Imported lazily so boto3 is only needed when R2 is configured.
        import boto3  # type: ignore[import-untyped]

        client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
        client.put_object(
            Bucket=settings.r2_bucket, Key=key, Body=data, ContentType=content_type
        )

    def read_bytes(self, document: Document) -> bytes:
        """Fetch a document's bytes from its backend (used by the download route)."""
        if document.storage_backend == "local":
            path = Path(settings.documents_local_dir) / document.storage_key
            if not path.exists():
                raise NotFoundError("Document bytes are missing from local storage")
            return path.read_bytes()
        import boto3  # type: ignore[import-untyped]

        client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
        obj = client.get_object(Bucket=settings.r2_bucket, Key=document.storage_key)
        return obj["Body"].read()

    # --- public API ----------------------------------------------------
    def list(
        self, *, entity_type, entity_id, page, page_size, category=None, q=None
    ):
        rows, total = self.repo.search(
            entity_type=entity_type,
            entity_id=entity_id,
            category=category,
            q=q,
            page=page,
            page_size=page_size,
        )
        return [DocumentRead.model_validate(d) for d in rows], total

    def category_counts(self) -> dict[str, int]:
        return self.repo.category_counts()

    def get(self, document_id: uuid.UUID) -> Document:
        doc = self.repo.get(document_id)
        if doc is None:
            raise NotFoundError(f"Document {document_id} not found")
        return doc

    def delete(self, document_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        """Soft-delete a document; the bytes are left in storage."""
        soft_delete(self.db, self.get(document_id), actor_id=actor_id, label="Document")

    def upload(
        self,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        business_unit_id: uuid.UUID | None,
        actor_id: uuid.UUID | None,
        category: str | None = None,
    ) -> DocumentRead:
        """Store the bytes and record the document metadata."""
        if not data:
            raise ValidationError("Uploaded file is empty")
        key = f"{uuid7()}_{_safe_name(filename)}"
        backend = self._store(key, data, content_type or "application/octet-stream")
        document = Document(
            filename=_safe_name(filename),
            content_type=content_type or "application/octet-stream",
            size_bytes=len(data),
            category=_clean_category(category),
            storage_backend=backend,
            storage_key=key,
            entity_type=entity_type,
            entity_id=entity_id,
            uploaded_by=actor_id,
            business_unit_id=business_unit_id or self._default_bu(),
            created_by=actor_id,
        )
        self.repo.add(document)
        self.activity.log(
            actor_id=actor_id,
            verb="uploaded",
            entity_type="document",
            entity_id=document.id,
            summary=f"Document {document.filename} uploaded",
            data={"linked_to": entity_type} if entity_type else None,
        )
        return DocumentRead.model_validate(document)
