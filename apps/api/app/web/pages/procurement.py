"""Procurement page: read-only goods receipts overview."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.procurement.service import GoodsReceiptService
from app.web.core import render

router = APIRouter()


@router.get("/procurement")
def procurement_index(request: Request, db: Session = Depends(get_db)):
    receipts = GoodsReceiptService(db).list_all()
    return render(request, "procurement/index.html", receipts=receipts)
