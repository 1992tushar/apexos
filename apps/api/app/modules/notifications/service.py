"""Notification service — push (emits notification.sent), list, mark read."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.activity.service import ActivityService
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationCreate, NotificationRead


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.activity = ActivityService(db)

    def push(self, payload: NotificationCreate, *, actor_id: uuid.UUID | None) -> NotificationRead:
        notification = Notification(
            user_id=payload.user_id,
            title=payload.title,
            body=payload.body,
            level=payload.level or "info",
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            is_read=False,
            created_by=actor_id,
        )
        self.db.add(notification)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="sent",
            entity_type="notification",
            entity_id=notification.id,
            summary=f"Notification: {notification.title}",
        )
        return NotificationRead.model_validate(notification)

    def list(self, *, unread_only: bool, limit: int) -> tuple[list[NotificationRead], int]:
        base = select(Notification).where(Notification.deleted_at.is_(None))
        if unread_only:
            base = base.where(Notification.is_read.is_(False))
        rows = list(
            self.db.scalars(base.order_by(Notification.created_at.desc()).limit(limit))
        )
        unread = self.db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.is_read.is_(False), Notification.deleted_at.is_(None))
        ) or 0
        return [NotificationRead.model_validate(n) for n in rows], int(unread)

    def mark_read(self, notification_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> NotificationRead:
        notification = self.db.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.deleted_at.is_(None)
            )
        )
        if notification is None:
            raise NotFoundError(f"Notification {notification_id} not found")
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            notification.updated_by = actor_id
            self.db.flush()
        return NotificationRead.model_validate(notification)

    def mark_all_read(self, *, actor_id: uuid.UUID | None) -> int:
        rows = list(
            self.db.scalars(
                select(Notification).where(
                    Notification.is_read.is_(False), Notification.deleted_at.is_(None)
                )
            )
        )
        now = datetime.now(timezone.utc)
        for n in rows:
            n.is_read = True
            n.read_at = now
            n.updated_by = actor_id
        self.db.flush()
        return len(rows)
