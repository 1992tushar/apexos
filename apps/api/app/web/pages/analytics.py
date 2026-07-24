"""Analytics page — a read-only KPI board with stat tiles, trend bar charts, and
top-N rankings. Owns no writes; renders the projection returned by AnalyticsService."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.modules.analytics.service import AnalyticsService
from app.web.core import render, render_error

router = APIRouter()


@router.get("/analytics")
def analytics_index(request: Request, db: Session = Depends(get_db)):
    try:
        board = AnalyticsService(db).board()
    except AppError as exc:
        return render_error(request, exc, code="Analytics unavailable")
    max_rev = max((p.amount_minor for p in board.revenue_trend), default=0)
    max_pur = max((p.amount_minor for p in board.purchase_trend), default=0)
    return render(
        request,
        "analytics/index.html",
        board=board,
        max_rev=max_rev,
        max_pur=max_pur,
    )
