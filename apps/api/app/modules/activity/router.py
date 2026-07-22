"""Activity router — GET /activity?limit=."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.activity.schemas import ActivityRead
from app.modules.activity.service import ActivityService

router = APIRouter(tags=["activity"])


@router.get("/activity", response_model=list[ActivityRead])
def list_activity(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ActivityService(db).recent(limit)
