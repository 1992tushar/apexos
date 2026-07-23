"""Tasks pages: list + inline create + complete action."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import Actor, get_current_actor
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.web.core import redirect, render

router = APIRouter()


@router.get("/tasks")
def list_tasks(request: Request, status: str | None = None, db: Session = Depends(get_db)):
    rows, total = TaskService(db).list(
        status=status or None, entity_type=None, entity_id=None, page=1, page_size=200
    )
    return render(
        request,
        "tasks/list.html",
        tasks=rows,
        total=total,
        status=status or "",
    )


@router.post("/tasks")
def create_task(
    request: Request,
    title: str = Form(...),
    priority: str = Form("normal"),
    due_date: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        payload = TaskCreate(
            title=title,
            priority=priority,
            due_date=date.fromisoformat(due_date) if due_date else None,
            description=description or None,
        )
        TaskService(db).create(payload, actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/tasks", err=getattr(exc, "message", "Could not create task"))
    return redirect("/tasks", ok="Task created")


@router.post("/tasks/{task_id}/complete")
def complete_task(
    request: Request,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        TaskService(db).complete(task_id, actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/tasks", err=getattr(exc, "message", "Could not complete task"))
    return redirect("/tasks", ok="Task completed")
