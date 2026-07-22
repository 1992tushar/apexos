"""Analytics router — the KPI board (read-only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.analytics.schemas import KpiBoard
from app.modules.analytics.service import AnalyticsService

router = APIRouter(tags=["analytics"])


@router.get("/analytics/kpis", response_model=KpiBoard)
def kpi_board(db: Session = Depends(get_db)):
    """Headline KPIs, trends, and top customers/suppliers/products."""
    return AnalyticsService(db).board()
