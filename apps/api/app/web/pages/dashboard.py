"""Dashboard page: read-only command-center summary at the app root."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.modules.dashboard.service import DashboardService
from app.web.core import render, render_error

router = APIRouter()


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    try:
        s = DashboardService(db).summary()
    except AppError as exc:
        return render_error(request, exc, code="Dashboard unavailable")
    max_rev = max((pt.amount_minor for pt in s.revenue_trend), default=0)
    return render(request, "dashboard/index.html", s=s, max_rev=max_rev)
