"""Categories pages: list + inline create + per-row reparent."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import Actor, get_current_actor
from app.modules.config.schemas import CategoryCreate
from app.modules.config.service import CategoryService, ConfigService
from app.web.core import redirect, render

router = APIRouter()


@router.get("/categories")
def list_categories(request: Request, db: Session = Depends(get_db)):
    cats = ConfigService(db).categories()
    pmodels = ConfigService(db).procurement_models()
    parent_names = {str(c.id): c.name for c in cats}
    return render(
        request,
        "categories/list.html",
        cats=cats,
        pmodels=pmodels,
        parent_names=parent_names,
    )


@router.post("/categories")
def create_category(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    procurement_model_id: str = Form(""),
    parent_category_id: str = Form(""),
    sort_order: str = Form("0"),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        payload = CategoryCreate(
            code=code,
            name=name,
            procurement_model_id=uuid.UUID(procurement_model_id)
            if procurement_model_id
            else None,
            parent_category_id=uuid.UUID(parent_category_id)
            if parent_category_id
            else None,
            sort_order=int(sort_order or 0),
        )
        CategoryService(db).create(payload, actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/categories", err=getattr(exc, "message", "Could not create category"))
    return redirect("/categories", ok="Category created")


@router.post("/categories/{category_id}/reparent")
def reparent_category(
    request: Request,
    category_id: uuid.UUID,
    parent_category_id: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        pid = uuid.UUID(parent_category_id) if parent_category_id else None
        CategoryService(db).reparent(category_id, pid, actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/categories", err=getattr(exc, "message", "Could not move category"))
    return redirect("/categories", ok="Category moved")
