"""Procurement page: the buying calendar (R5.7), the recommendations (R5.8) and
the goods receipts already taken.

Both halves of the calendar come from one service call. The page computes nothing —
`ProcurementCalendarService` owns "what is due to arrive" and delegates "what is due
to order" to `RecommendationService`, which is R5.9's single entry point.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.procurement.recommend import ARRIVAL_BUCKETS, ProcurementCalendarService
from app.modules.procurement.service import GoodsReceiptService
from app.web.core import render

router = APIRouter()


@router.get("/procurement")
def procurement_index(request: Request, db: Session = Depends(get_db)):
    calendar = ProcurementCalendarService(db).calendar()
    return render(
        request,
        "procurement/index.html",
        calendar=calendar,
        buckets=ARRIVAL_BUCKETS,
        receipts=GoodsReceiptService(db).list_all(),
    )
