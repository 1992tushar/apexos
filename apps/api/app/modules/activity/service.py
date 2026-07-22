"""Activity service — emit and read domain events (D10).

`ActivityService.log(...)` is the single entry point other services call to record
a domain event. It flushes (not commits) so the event participates in the caller's
transaction.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.activity.models import ActivityLog
from app.modules.activity.repository import ActivityRepository


class ActivityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ActivityRepository(db)

    def log(
        self,
        *,
        actor_id: uuid.UUID | None,
        verb: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        summary: str,
        data: dict | None = None,
    ) -> ActivityLog:
        log = ActivityLog(
            actor_id=actor_id,
            verb=verb,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            data=data,
            created_by=actor_id,
        )
        return self.repo.add(log)

    def recent(self, limit: int = 20) -> list[ActivityLog]:
        return self.repo.recent(limit)
