"""Shared Jinja2 plumbing for the web UI: the templates instance, presentation
filters, the nav model, and a small `render` helper.

Page modules import from here (`from app.web.core import templates, render`) so
all pages share one configured environment.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings

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
    {"label": "Documents", "href": "/documents", "section": "system"},
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


def number(n: int | float | None) -> str:
    if n is None:
        return "0"
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
    now = datetime.now(dt.tzinfo or timezone.utc)
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


templates.env.filters.update(
    money=money,
    number=number,
    fmt_date=fmt_date,
    fmt_datetime=fmt_datetime,
    time_ago=time_ago,
    status_class=status_class,
    humanize=humanize,
)
templates.env.globals.update(
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
