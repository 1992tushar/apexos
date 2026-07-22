"""Reports router — catalog + run (JSON or CSV download). Read-only."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.reports.service import ReportService

router = APIRouter(tags=["reports"])


@router.get("/reports")
def list_reports(db: Session = Depends(get_db)):
    """Catalog of available reports (key + title)."""
    return ReportService(db).catalog()


@router.get("/reports/{report_key}")
def run_report(
    report_key: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Run a report; returns JSON `{key,title,columns,rows,money_columns}` or a CSV file."""
    result = ReportService(db).run(report_key, date_from=date_from, date_to=date_to)
    if format == "csv":
        csv_text = ReportService.to_csv(result)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{result.key}.csv"'},
        )
    return {
        "key": result.key,
        "title": result.title,
        "columns": result.columns,
        "rows": result.rows,
        "money_columns": sorted(result.money_columns),
    }
