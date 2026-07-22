"""Tasks router — thin; delegates to TaskService."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.tasks.schemas import TaskCreate, TaskPage, TaskRead, TaskUpdate
from app.modules.tasks.service import TaskService

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=TaskPage)
def list_tasks(
    status: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = TaskService(db).list(
        status=status, entity_type=entity_type, entity_id=entity_id,
        page=page, page_size=page_size,
    )
    return TaskPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/tasks", response_model=TaskRead, status_code=201)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("task.create")),
):
    return TaskService(db).create(payload, actor_id=actor.id)


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: uuid.UUID, db: Session = Depends(get_db)):
    return TaskService(db).get(task_id)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("task.update")),
):
    return TaskService(db).update(task_id, payload, actor_id=actor.id)


@router.post("/tasks/{task_id}/complete", response_model=TaskRead)
def complete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("task.complete")),
):
    return TaskService(db).complete(task_id, actor_id=actor.id)
