"""Reports pages — read-only tabular projections with a filter form + CSV export.

Reports own no entities and write nothing, so there is no actor and no rollback:
GET-only handlers select a report from the catalog, run it over an optional
date window, and render (or stream as CSV) the resulting columns/rows.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.modules.reports.service import ReportService
from app.web.core import humanize, redirect, render

router = APIRouter()


def _columns_meta(result):
    meta = []
    for col in result.columns:
        label = col[:-len("_minor")] if col.endswith("_minor") else col
        meta.append({"col": col, "label": humanize(label), "is_money": col in result.money_columns})
    return meta


@router.get("/reports")
def reports_index(
    request: Request,
    report: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    svc = ReportService(db)
    catalog = svc.catalog()
    df = date.fromisoformat(date_from) if date_from else None
    dt = date.fromisoformat(date_to) if date_to else None

    result = None
    columns_meta: list[dict] = []
    error = None
    if report:
        try:
            result = svc.run(report, date_from=df, date_to=dt)
            columns_meta = _columns_meta(result)
        except AppError as exc:
            error = exc.message

    return render(
        request,
        "reports/index.html",
        catalog=catalog,
        report=report or "",
        date_from=date_from or "",
        date_to=date_to or "",
        result=result,
        columns_meta=columns_meta,
        error=error,
    )


@router.get("/reports/export")
def reports_export(
    request: Request,
    report: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    svc = ReportService(db)
    df = date.fromisoformat(date_from) if date_from else None
    dt = date.fromisoformat(date_to) if date_to else None
    try:
        result = svc.run(report, date_from=df, date_to=dt)
    except AppError:
        return redirect("/reports", err="Unknown report")
    csv = ReportService.to_csv(result)
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{result.key}.csv"'},
    )
