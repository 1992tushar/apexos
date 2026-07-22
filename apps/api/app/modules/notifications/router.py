"""Notifications router — inbox list, push, mark read."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.notifications.schemas import (
    NotificationCreate,
    NotificationList,
    NotificationRead,
)
from app.modules.notifications.service import NotificationService

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=NotificationList)
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, unread = NotificationService(db).list(unread_only=unread_only, limit=limit)
    return NotificationList(items=items, unread=unread)


@router.post("/notifications", response_model=NotificationRead, status_code=201)
def push_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("notification.push")),
):
    return NotificationService(db).push(payload, actor_id=actor.id)


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("notification.read")),
):
    return NotificationService(db).mark_read(notification_id, actor_id=actor.id)


@router.post("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("notification.read")),
):
    count = NotificationService(db).mark_all_read(actor_id=actor.id)
    return {"marked": count}
