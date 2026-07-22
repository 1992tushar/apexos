"""Task repository — persistence + list projections."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.tasks.models import Task


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, task: Task) -> Task:
        self.db.add(task)
        self.db.flush()
        return task

    def get(self, task_id: uuid.UUID) -> Task | None:
        return self.db.scalar(
            select(Task).where(Task.id == task_id, Task.deleted_at.is_(None))
        )

    def search(
        self,
        *,
        status: str | None,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Task], int]:
        base = select(Task).where(Task.deleted_at.is_(None))
        if status:
            base = base.where(Task.status == status)
        if entity_type:
            base = base.where(Task.entity_type == entity_type)
        if entity_id:
            base = base.where(Task.entity_id == entity_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = list(
            self.db.scalars(
                base.order_by(Task.status.asc(), Task.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total

    def open_count(self) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.status == "open", Task.deleted_at.is_(None))
        ) or 0
