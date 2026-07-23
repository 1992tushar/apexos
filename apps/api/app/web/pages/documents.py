"""DocKeeper pages: list + filter + upload + inline view/download + delete."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import Actor, get_current_actor
from app.modules.documents.models import DOCUMENT_CATEGORIES
from app.modules.documents.service import DocumentService
from app.web.core import redirect, render

router = APIRouter()


@router.get("/documents")
def list_documents(
    request: Request,
    q: str = Query(default=""),
    category: str = Query(default=""),
    db: Session = Depends(get_db),
):
    svc = DocumentService(db)
    rows, total = svc.list(
        entity_type=None,
        entity_id=None,
        category=category or None,
        q=q or None,
        page=1,
        page_size=200,
    )
    counts = svc.category_counts()
    return render(
        request,
        "documents/list.html",
        documents=rows,
        total=total,
        categories=DOCUMENT_CATEGORIES,
        counts=counts,
        all_count=sum(counts.values()),
        active_category=category or "",
        query=q or "",
    )


@router.post("/documents")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("other"),
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
            category=category,
        )
    except (AppError, ValueError) as exc:
        db.rollback()
        return redirect("/documents", err=getattr(exc, "message", "Could not upload document"))
    return redirect("/documents", ok="Document uploaded")


@router.post("/documents/{document_id}/delete")
def delete_document(
    request: Request,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        DocumentService(db).delete(document_id, actor_id=actor.id)
    except AppError as exc:
        db.rollback()
        return redirect("/documents", err=getattr(exc, "message", "Could not delete document"))
    return redirect("/documents", ok="Document deleted")


@router.get("/documents/{document_id}/download")
def download_document(
    request: Request,
    document_id: uuid.UUID,
    dl: int = Query(default=0),
    db: Session = Depends(get_db),
):
    svc = DocumentService(db)
    try:
        doc = svc.get(document_id)
        data = svc.read_bytes(doc)
    except AppError as exc:
        return render(
            request, "error.html", status_code=exc.status_code, code="Not found", message=exc.message
        )
    # dl=1 forces a save dialog (attachment); otherwise render inline in the browser.
    disposition = "attachment" if dl else "inline"
    return Response(
        content=data,
        media_type=doc.content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{doc.filename}"'},
    )
