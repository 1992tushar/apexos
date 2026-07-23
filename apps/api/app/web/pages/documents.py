"""Documents pages: list + upload + inline download."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import Actor, get_current_actor
from app.modules.documents.service import DocumentService
from app.web.core import redirect, render

router = APIRouter()


@router.get("/documents")
def list_documents(request: Request, db: Session = Depends(get_db)):
    rows, total = DocumentService(db).list(
        entity_type=None, entity_id=None, page=1, page_size=200
    )
    return render(request, "documents/list.html", documents=rows, total=total)


@router.post("/documents")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    entity_type: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    data = await file.read()
    try:
        DocumentService(db).upload(
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            data=data,
            entity_type=entity_type or None,
            entity_id=None,
            business_unit_id=None,
            actor_id=actor.id,
        )
    except (AppError, ValueError) as exc:
        db.rollback()
        return redirect("/documents", err=getattr(exc, "message", "Could not upload document"))
    return redirect("/documents", ok="Document uploaded")


@router.get("/documents/{document_id}/download")
def download_document(request: Request, document_id: uuid.UUID, db: Session = Depends(get_db)):
    svc = DocumentService(db)
    try:
        doc = svc.get(document_id)
        data = svc.read_bytes(doc)
    except AppError as exc:
        return render(
            request, "error.html", status_code=exc.status_code, code="Not found", message=exc.message
        )
    return Response(
        content=data,
        media_type=doc.content_type,
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )
