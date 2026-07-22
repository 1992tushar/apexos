"""Documents router — multipart upload, list, and download."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.documents.schemas import DocumentPage, DocumentRead
from app.modules.documents.service import DocumentService

router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=DocumentPage)
def list_documents(
    entity_type: str | None = Query(default=None),
    entity_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = DocumentService(db).list(
        entity_type=entity_type, entity_id=entity_id, page=page, page_size=page_size
    )
    return DocumentPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    entity_type: str | None = Form(default=None),
    entity_id: uuid.UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("document.upload")),
):
    """Upload a file to the configured backend (Cloudflare R2 or local fallback)."""
    data = await file.read()
    return DocumentService(db).upload(
        filename=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        entity_type=entity_type,
        entity_id=entity_id,
        business_unit_id=None,
        actor_id=actor.id,
    )


@router.get("/documents/{document_id}/download")
def download_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Stream a document's bytes back with its original content type."""
    service = DocumentService(db)
    doc = service.get(document_id)
    data = service.read_bytes(doc)
    return Response(
        content=data,
        media_type=doc.content_type,
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )
