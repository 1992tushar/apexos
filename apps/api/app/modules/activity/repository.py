"""Activity repository."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.models import ActivityLog


class ActivityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, log: ActivityLog) -> ActivityLog:
        self.db.add(log)
        self.db.flush()
        return log

    def recent(self, limit: int = 20) -> list[ActivityLog]:
        stmt = (
            select(ActivityLog)
            .order_by(ActivityLog.occurred_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
