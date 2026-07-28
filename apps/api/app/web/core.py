"""Shared Jinja2 plumbing for the web UI: the templates instance, presentation
filters, the nav model, and a small `render` helper.

Page modules import from here (`from app.web.core import templates, render`) so
all pages share one configured environment.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings
from app.core.errors import AppError

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# --- navigation (mirrors the former Next.js nav-config.ts) -------------------
# (label, href, section). Sections render as grouped blocks in the sidebar.
NAV_ITEMS: list[dict[str, str]] = [
    {"label": "Dashboard", "href": "/", "section": "main"},
    {"label": "Sales", "href": "/sales", "section": "work"},
    {"label": "Customers", "href": "/customers", "section": "work"},
    {"label": "Leads", "href": "/leads", "section": "work"},
    {"label": "Products", "href": "/products", "section": "work"},
    {"label": "Categories", "href": "/categories", "section": "work"},
    {"label": "Inventory", "href": "/inventory", "section": "work"},
    {"label": "Warehouse", "href": "/warehouse", "section": "work"},
    {"label": "Procurement", "href": "/procurement", "section": "work"},
    {"label": "Purchase Orders", "href": "/purchase-orders", "section": "work"},
    {"label": "Suppliers", "href": "/suppliers", "section": "work"},
    {"label": "Finance", "href": "/finance", "section": "work"},
    {"label": "Reports", "href": "/reports", "section": "work"},
    {"label": "Analytics", "href": "/analytics", "section": "work"},
    {"label": "Tasks", "href": "/tasks", "section": "system"},
    {"label": "DocKeeper", "href": "/documents", "section": "system"},
    {"label": "Settings", "href": "/settings", "section": "system"},
]
SECTION_LABELS = {"main": None, "work": "Work", "system": "System"}


# --- presentation filters ----------------------------------------------------
def _indian_group(int_str: str) -> str:
    """Group an integer string the Indian way (e.g. 1234567 -> 12,34,567)."""
    neg = int_str.startswith("-")
    if neg:
        int_str = int_str[1:]
    if len(int_str) <= 3:
        grouped = int_str
    else:
        head, tail = int_str[:-3], int_str[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        grouped = ",".join(parts) + "," + tail
    return ("-" + grouped) if neg else grouped


def money(minor: int | None, *, symbol: str = "₹") -> str:
    """Format integer minor units (paise) as INR, e.g. 1234567 -> ₹12,345.67."""
    minor = int(minor or 0)
    neg = minor < 0
    minor = abs(minor)
    rupees, paise = divmod(minor, 100)
    out = f"{symbol}{_indian_group(str(rupees))}.{paise:02d}"
    return ("-" + out) if neg else out


def number(n: int | float | Decimal | None) -> str:
    if n is None:
        return "0"
    if isinstance(n, Decimal):
        # Quantities are Numeric(18,4), so a whole number arrives as "20.0000".
        # Show the significant part: 20, and 1.25 rather than 1.2500.
        if n == n.to_integral_value():
            return _indian_group(str(int(n)))
        return format(n.normalize(), "f")
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    if isinstance(n, int):
        return _indian_group(str(n))
    return str(n)


def _coerce_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def fmt_date(value: Any) -> str:
    dt = _coerce_dt(value)
    if dt is None:
        return "—"
    return dt.strftime("%d %b %Y")


def fmt_datetime(value: Any) -> str:
    dt = _coerce_dt(value)
    if dt is None:
        return "—"
    return dt.strftime("%d %b %Y, %H:%M")


def time_ago(value: Any) -> str:
    dt = _coerce_dt(value)
    if dt is None:
        return ""
    # SQLite hands back naive datetimes (func.now() -> CURRENT_TIMESTAMP is UTC);
    # treat naive values as UTC so the subtraction never mixes naive/aware.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    diff = (now - dt).total_seconds()
    mins = round(diff / 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hrs = round(mins / 60)
    if hrs < 24:
        return f"{hrs}h ago"
    days = round(hrs / 24)
    if days < 30:
        return f"{days}d ago"
    return fmt_date(value)


def status_class(status: Any) -> str:
    """Map a status string to a semantic badge class (see app.css)."""
    s = str(status or "").lower()
    positive = {"active", "paid", "confirmed", "received", "billed", "completed",
                "fulfilled", "invoiced", "won", "done", "success"}
    warning = {"draft", "pending", "partial", "partially_paid", "open", "new",
               "qualified", "proposal", "in_progress", "todo", "sent"}
    negative = {"cancelled", "canceled", "overdue", "lost", "inactive",
                "failed", "rejected", "void"}
    if s in positive:
        return "ok"
    if s in warning:
        return "warn"
    if s in negative:
        return "bad"
    return "muted"


def humanize(value: Any) -> str:
    return str(value or "").replace("_", " ").strip().title()


def filesize(n: int | None) -> str:
    """Human-readable byte size, e.g. 2048 -> '2.0 KB', 0 -> '0 B'."""
    size = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def bps(value: Any) -> str:
    """Integer basis points as a percentage: 1800 → "18%", 250 → "2.5%".

    GST rates are stored as `rate_bps` (integer, G1's no-float rule applies to money
    but the same reasoning keeps rates exact). Integer arithmetic only.
    """
    if value is None:
        return "—"
    whole, fraction = divmod(int(value), 100)
    return f"{whole}%" if not fraction else f"{whole}.{fraction:02d}".rstrip("0") + "%"


templates.env.filters.update(
    money=money,
    number=number,
    bps=bps,
    fmt_date=fmt_date,
    fmt_datetime=fmt_datetime,
    time_ago=time_ago,
    status_class=status_class,
    humanize=humanize,
    filesize=filesize,
)
templates.env.globals.update(
    # Lets the `cell` macro render a column with no `ListView` around it — a detail
    # page shows the same columns as a `<dl>`.
    cell_value=lambda row, key: getattr(row, key, None),
    NAV_ITEMS=NAV_ITEMS,
    SECTION_LABELS=SECTION_LABELS,
    APP_NAME=settings.app_name,
)


def render(
    request: Request, template: str, *, status_code: int = 200, **context: Any
) -> HTMLResponse:
    """Render a template with the request in context (required by Jinja2Templates)."""
    return templates.TemplateResponse(request, template, context, status_code=status_code)


def redirect(path: str, *, ok: str | None = None, err: str | None = None) -> RedirectResponse:
    """303 redirect (Post/Redirect/Get) with an optional flash message in the query string."""
    params = {}
    if ok:
        params["ok"] = ok
    if err:
        params["err"] = err
    if params:
        path = f"{path}{'&' if '?' in path else '?'}{urlencode(params)}"
    return RedirectResponse(path, status_code=303)


# Errors a form POST is expected to surface to the user (vs. crash). A domain
# `AppError` carries a `.message`; Pydantic/ValueError are input problems we show
# with the caller's friendly fallback text.
FORM_ERRORS = (AppError, PydanticValidationError, ValueError)


def form_action(
    db,
    run,
    *,
    back: str,
    success,
    err: str = "Could not complete the action",
) -> RedirectResponse:
    """Run a form's work inside one place that owns the rollback + flash contract.

    `run` is a zero-arg callable doing the payload-build + service call. On a
    `FORM_ERRORS` failure we roll back (the work may have partially flushed) and
    303 back to `back` with an `err` flash. On success we 303 to `success` —
    either a `(path, ok_message)` tuple or a callable `result -> (path, message)`.
    This replaces the per-page `try/except: db.rollback(); redirect(...)` blocks.
    """
    try:
        result = run()
    except FORM_ERRORS as exc:
        db.rollback()
        return redirect(back, err=getattr(exc, "message", None) or err)
    path, ok = success(result) if callable(success) else success
    return redirect(path, ok=ok)


def render_error(request: Request, exc: AppError, *, code: str | None = None) -> HTMLResponse:
    """Render the shared HTML error page from a domain error (for GET handlers)."""
    return render(
        request,
        "error.html",
        status_code=getattr(exc, "status_code", 500),
        code=code or humanize(getattr(exc, "code", "Error")),
        message=getattr(exc, "message", None) or str(exc),
    )
