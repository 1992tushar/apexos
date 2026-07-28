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

    def for_entity(
        self, entity_type: str, entity_id: uuid.UUID, limit: int = 50
    ) -> list[ActivityLog]:
        """Every logged event for one record, newest first (the change-history read).

        Ordered by `id` as well as `occurred_at`: the timestamp comes from
        `CURRENT_TIMESTAMP`, whose resolution is one second, so several events in
        the same transaction share it. UUIDv7 keys sort by creation time, which
        keeps them in the order they happened.
        """
        stmt = (
            select(ActivityLog)
            .where(
                ActivityLog.entity_type == entity_type,
                ActivityLog.entity_id == entity_id,
            )
            .order_by(ActivityLog.occurred_at.desc(), ActivityLog.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
