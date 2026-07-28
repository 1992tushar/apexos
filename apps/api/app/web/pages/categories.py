"""Categories pages: list + inline create + per-row reparent."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.activity.service import ActivityService
from app.modules.config.listing import CATEGORY_LIST
from app.modules.config.schemas import CategoryCreate
from app.modules.config.service import CategoryService, ConfigService
from app.web.core import form_action, render
from app.web.listing import csv_response_from_request, view_from_request, wants_csv
from app.web.security import require_web_permission

router = APIRouter()


@router.get("/categories")
def list_categories(request: Request, db: Session = Depends(get_db)):
    categories = CategoryService(db)
    if wants_csv(request):
        return csv_response_from_request(
            request, db, CATEGORY_LIST, project=categories.to_read_many
        )
    config = ConfigService(db)
    return render(
        request,
        "categories/list.html",
        view=view_from_request(
            request, db, CATEGORY_LIST, project=categories.to_read_many
        ),
        # The whole tree, not just this page of it — reparenting needs every category
        # in the target dropdown, and R3.4 asks for the tree on screen.
        tree=categories.tree(),
        cats=config.categories(),
        pmodels=config.procurement_models(),
    )


@router.get("/categories/{category_id}")
def category_detail(request: Request, category_id: uuid.UUID, db: Session = Depends(get_db)):
    return render(
        request,
        "categories/detail.html",
        c=CategoryService(db).get(category_id),
        history=ActivityService(db).history("category", category_id),
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
    # Categories are config-module masters: the JSON API guards their writes with
    # `config.write`, so the web routes use the same code (R1.5). Deletion is a
    # web-only capability and follows the `<entity>.delete` shape of the others.
    actor: Actor = Depends(require_web_permission("config.write")),
):
    def work():
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
        return CategoryService(db).create(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/categories", success=("/categories", "Category created"),
        err="Could not create category",
    )


@router.post("/categories/{category_id}/reparent")
def reparent_category(
    request: Request,
    category_id: uuid.UUID,
    parent_category_id: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("config.write")),
):
    def work():
        pid = uuid.UUID(parent_category_id) if parent_category_id else None
        return CategoryService(db).reparent(category_id, pid, actor_id=actor.id)

    return form_action(
        db, work, back="/categories", success=("/categories", "Category moved"),
        err="Could not move category",
    )


@router.post("/categories/{category_id}/delete")
def delete_category(
    request: Request,
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("category.delete")),
):
    return form_action(
        db, lambda: CategoryService(db).delete(category_id, actor_id=actor.id),
        back="/categories", success=("/categories", "Category deleted"),
        err="Could not delete category",
    )
