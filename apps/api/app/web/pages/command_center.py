"""The Founder Command Center at `/` — Part 9's replacement for the placeholder.

Thin by design: one service call, one render. The projection is `CommandCenterService`,
and everything it knows came from the part that owns it (R12.10). This module
deliberately holds no arithmetic — if you find yourself adding a `sum()` here, the figure
belongs in a service.

**No query parameters.** The homepage is "today", and the report date is a parameter of
the *service* rather than of the URL — which is where tests drive it from. That keeps the
route free of the date-coercion this app otherwise needs on every dated screen (see
`finance.py:_as_of`), and it keeps the R1.5 route walk, which loads every plain GET with
no parameters at all, honest about what it proved.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.command_center.service import CommandCenterService
from app.web.core import render

router = APIRouter()


@router.get("/")
def command_center(request: Request, db: Session = Depends(get_db)):
    return render(request, "command_center/index.html", page=CommandCenterService(db).load())
