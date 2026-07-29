"""The Intelligence Layer at `/intelligence` (Part 10 C2).

Thin by design, exactly as `command_center.py` is: one service call, one render, no
arithmetic. If you find yourself adding a `sum()` here, the figure belongs in a service.

**No query parameters**, for the same reason the homepage has none: the report date is a
parameter of the *service*, which is where tests drive it from, and it keeps the R1.5 route
walk — which loads every plain GET with no parameters at all — honest about what it proved.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.intelligence.service import IntelligenceService
from app.web.core import render

router = APIRouter()


@router.get("/intelligence")
def intelligence(request: Request, db: Session = Depends(get_db)):
    return render(request, "intelligence/index.html", page=IntelligenceService(db).load())
