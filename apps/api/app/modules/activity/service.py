"""Activity service — emit and read domain events (D10).

`ActivityService.log(...)` is the single entry point other services call to record
a domain event. It flushes (not commits) so the event participates in the caller's
transaction.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.history import HistoryEntry, changes_from_data
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

    def history(
        self, entity_type: str, entity_id: uuid.UUID, *, limit: int = 50
    ) -> list[HistoryEntry]:
        """Change history for one record, derived from the log (R2.10).

        Newest first, with field-level before/after wherever the writing verb
        recorded one via `field_changes`. A pure read — it writes nothing (G15).
        """
        rows = self.repo.for_entity(entity_type, entity_id, limit)
        actors = self._actor_names({r.actor_id for r in rows if r.actor_id is not None})
        return [
            HistoryEntry(
                occurred_at=row.occurred_at,
                verb=row.verb,
                summary=row.summary,
                actor=self._actor_label(row.actor_id, actors),
                changes=changes_from_data(row.data),
            )
            for row in rows
        ]

    def _actor_names(self, actor_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not actor_ids:
            return {}
        from app.modules.identity.models import User  # local import avoids a cycle

        rows = self.db.execute(
            select(User.id, User.full_name).where(User.id.in_(actor_ids))
        ).all()
        return {row[0]: row[1] for row in rows}

    @staticmethod
    def _actor_label(actor_id: uuid.UUID | None, actors: dict[uuid.UUID, str]) -> str:
        """Who did it. Never guesses — an unresolvable actor says so (G11)."""
        if actor_id is None:
            return "System"
        return actors.get(actor_id) or "Unknown user"
