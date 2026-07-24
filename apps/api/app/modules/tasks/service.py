"""Task service — create / complete / update, each emitting one activity_log row."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import TaskCreate, TaskRead, TaskUpdate


class TaskService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TaskRepository(db)
        self.activity = ActivityService(db)

    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    def list(
        self,
        *,
        status: str | None,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ):
        rows, total = self.repo.search(
            status=status, entity_type=entity_type, entity_id=entity_id,
            page=page, page_size=page_size,
        )
        return [TaskRead.model_validate(t) for t in rows], total

    def get(self, task_id: uuid.UUID) -> TaskRead:
        task = self.repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return TaskRead.model_validate(task)

    def create(self, payload: TaskCreate, *, actor_id: uuid.UUID | None) -> TaskRead:
        task = Task(
            title=payload.title,
            description=payload.description,
            priority=payload.priority or "normal",
            due_date=payload.due_date,
            assignee_id=payload.assignee_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            status="open",
            business_unit_id=payload.business_unit_id or self._default_bu(),
            created_by=actor_id,
        )
        self.repo.add(task)
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="task",
            entity_id=task.id,
            summary=f"Task “{task.title}” created",
            data={"linked_to": payload.entity_type} if payload.entity_type else None,
        )
        return TaskRead.model_validate(task)

    def update(self, task_id: uuid.UUID, payload: TaskUpdate, *, actor_id: uuid.UUID | None) -> TaskRead:
        task = self.repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        data = payload.model_dump(exclude_unset=True)
        for field in ("title", "description", "priority", "due_date", "assignee_id", "status"):
            if field in data and data[field] is not None:
                setattr(task, field, data[field])
        if data.get("status") == "completed" and task.completed_at is None:
            task.completed_at = datetime.now(UTC)
        task.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="updated",
            entity_type="task",
            entity_id=task.id,
            summary=f"Task “{task.title}” updated",
        )
        return TaskRead.model_validate(task)

    def complete(self, task_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> TaskRead:
        task = self.repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        if task.status == "completed":
            raise ConflictError(f"Task {task.title} is already completed")
        task.status = "completed"
        task.completed_at = datetime.now(UTC)
        task.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="completed",
            entity_type="task",
            entity_id=task.id,
            summary=f"Task “{task.title}” completed",
        )
        return TaskRead.model_validate(task)
