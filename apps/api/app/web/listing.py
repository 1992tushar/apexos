"""The presentation half of the list machinery: URLs, and the one CSV export.

`app.db.listing` answers "which rows"; this answers "what does the page link to".
Both read the same `ListSpec`, so a column that can be sorted in the query is
clickable in the header, and a filter the query understands is a chip the user can
remove — they cannot disagree.

List state lives entirely in the query string (`?q=&sort=&dir=&page=&<filter>=`,
R2.3). Nothing is kept in a session or a cookie, so a filtered list is a URL:
copy it into another tab and you get the same view, and the back button walks
back through the filters you applied. Every URL a `ListView` builds is the current
state with one thing changed, which is why sorting does not silently drop your
search and changing a filter does not leave you on page 7 of a shorter list.

The CSV export (R2.8) runs the same `build_select` as the screen with pagination
removed, so "export respects the filters currently on screen" is structural rather
than something each page has to remember to pass through.
"""
from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.money import minor_to_text
from app.db.listing import (
    Column,
    ListPage,
    ListParams,
    ListSpec,
    effective_sort,
    is_valid,
    query_page,
    query_rows,
)

Projector = Callable[[Sequence[Any]], list[Any]]


class _RowFields(Mapping):
    """A row's attributes as a mapping, so `Column.href` can be a format string."""

    def __init__(self, row: Any) -> None:
        self._row = row

    def __getitem__(self, key: str) -> Any:
        return value_of(self._row, key)

    def __iter__(self):  # pragma: no cover - Mapping protocol, unused
        return iter(())

    def __len__(self) -> int:  # pragma: no cover - Mapping protocol, unused
        return 0


def value_of(row: Any, key: str) -> Any:
    """Read `key` off a row, whether it is an ORM object, a projection or a dict."""
    if isinstance(row, Mapping):
        return row.get(key)
    return getattr(row, key, None)


def params_from_request(request: Request, spec: ListSpec) -> ListParams:
    """Parse `?q=&sort=&dir=&page=&<filter>=` against what the spec publishes.

    Everything unrecognised is dropped rather than rejected: an unpublished sort
    key falls back to the spec's default, an uncoercible filter value is ignored,
    a non-numeric page becomes page 1. A stale bookmark renders the list, never an
    error page.
    """
    qp = request.query_params

    filters = {}
    for spec_filter in spec.filters:
        raw = (qp.get(spec_filter.key) or "").strip()
        if raw and is_valid(spec_filter.coerce, raw):
            filters[spec_filter.key] = raw

    sort = (qp.get("sort") or "").strip()
    if not spec.can_sort(sort):
        sort = ""
    direction = (qp.get("dir") or "").strip().lower()
    if direction not in ("asc", "desc"):
        direction = "asc" if sort else spec.dir

    try:
        page = max(1, int(qp.get("page") or 1))
    except (TypeError, ValueError):
        page = 1

    return ListParams(
        q=(qp.get("q") or "").strip(), sort=sort, dir=direction, page=page, filters=filters
    )


@dataclass
class ListView:
    """Everything a list template needs: the rows, the state, and the links.

    `rows` are what the table renders — the ORM rows, or a service projection of
    them when the page needs derived values (a customer's outstanding, a product's
    stock). `result` keeps the underlying page for the counts.
    """

    spec: ListSpec
    params: ListParams
    result: ListPage
    rows: list[Any]
    path: str
    options: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    # --- counts (delegated, so templates read `view.total` not `view.result.total`)
    @property
    def total(self) -> int:
        return self.result.total

    @property
    def page_no(self) -> int:
        return self.result.page

    @property
    def pages(self) -> int:
        return self.result.pages

    @property
    def start(self) -> int:
        return self.result.start

    @property
    def end(self) -> int:
        return self.result.end

    @property
    def has_prev(self) -> bool:
        return self.result.has_prev

    @property
    def has_next(self) -> bool:
        return self.result.has_next

    @property
    def is_filtered(self) -> bool:
        return self.params.is_filtered

    # --- URLs -----------------------------------------------------------
    def url(self, **overrides: Any) -> str:
        """The current list URL with some state replaced.

        Pass `None` to drop a key. Defaults (page 1, no search, the spec's own
        sort) are omitted so the URLs stay short and the unfiltered list has one
        canonical address rather than several spellings of it.
        """
        state: dict[str, Any] = {
            "q": self.params.q,
            "sort": self.params.sort,
            "dir": self.params.dir if self.params.sort else "",
            "page": self.params.page,
            **self.params.filters,
        }
        state.update(overrides)
        query = {
            key: str(value)
            for key, value in state.items()
            if value not in (None, "", 0) and not (key == "page" and int(value or 1) <= 1)
        }
        return f"{self.path}?{urlencode(query)}" if query else self.path

    def sort_url(self, column: Column) -> str:
        """Link for a sortable header: sort by it, or flip if it is already the sort."""
        key, direction = effective_sort(self.spec, self.params)
        flipped = "desc" if direction == "asc" else "asc"
        return self.url(sort=column.sort, dir=flipped if column.sort == key else "asc", page=1)

    def sort_glyph(self, column: Column) -> str:
        """The arrow on a header — empty unless this column is the active sort."""
        key, direction = effective_sort(self.spec, self.params)
        if column.sort != key:
            return ""
        return "↑" if direction == "asc" else "↓"

    def page_url(self, page: int) -> str:
        return self.url(page=page)

    def clear_url(self) -> str:
        """Drop the search and every filter, keep the sort."""
        cleared = dict.fromkeys(self.params.filters, None)
        return self.url(q=None, page=1, **cleared)

    def export_url(self) -> str:
        """Same state, CSV instead of HTML (R2.8)."""
        return self.url(export="csv")

    def chips(self) -> list[dict[str, str]]:
        """The active filters, each with a link that removes just that one."""
        out: list[dict[str, str]] = []
        if self.params.q:
            out.append(
                {"label": "Search", "value": self.params.q, "remove_url": self.url(q=None, page=1)}
            )
        for spec_filter in self.spec.filters:
            raw = self.params.filters.get(spec_filter.key)
            if not raw:
                continue
            labels = dict(self.options.get(spec_filter.key, []))
            out.append(
                {
                    "label": spec_filter.label,
                    "value": labels.get(raw, raw),
                    "remove_url": self.url(page=1, **{spec_filter.key: None}),
                }
            )
        return out

    # --- cells ----------------------------------------------------------
    def value(self, row: Any, column: Column) -> Any:
        return value_of(row, column.key)

    def href(self, column: Column, row: Any) -> str:
        """`Column.href` resolved against the row, e.g. `/customers/{id}`."""
        if not column.href:
            return ""
        try:
            return column.href.format_map(_RowFields(row))
        except (KeyError, IndexError, ValueError):
            return ""


def list_view(
    db: Session,
    spec: ListSpec,
    params: ListParams,
    *,
    path: str,
    business_unit_id: uuid.UUID | None = None,
    project: Projector | None = None,
) -> ListView:
    """Run a list and package it for a template."""
    result = query_page(db, spec, params, business_unit_id=business_unit_id)
    rows = list(project(result.rows)) if project else list(result.rows)
    options = {
        spec_filter.key: list(spec_filter.options(db))
        for spec_filter in spec.filters
        if spec_filter.options is not None
    }
    return ListView(spec=spec, params=params, result=result, rows=rows, path=path, options=options)


def view_from_request(
    request: Request,
    db: Session,
    spec: ListSpec,
    *,
    business_unit_id: uuid.UUID | None = None,
    project: Projector | None = None,
) -> ListView:
    """The one call a GET list route makes."""
    return list_view(
        db,
        spec,
        params_from_request(request, spec),
        path=request.url.path,
        business_unit_id=business_unit_id,
        project=project,
    )


def wants_csv(request: Request) -> bool:
    """Is this the export of the current view rather than the view itself?"""
    return (request.query_params.get("export") or "").lower() == "csv"


# --- CSV export -------------------------------------------------------------

def export_text(column: Column, row: Any) -> str:
    """One cell as CSV text: machine-readable, no currency symbols, no em dashes."""
    raw = value_of(row, column.key)
    if raw is None:
        return ""
    if column.kind == "money":
        return minor_to_text(raw)
    if column.kind == "bool":
        return "active" if raw else "inactive"
    if column.kind == "bps":
        # Basis points as a plain decimal percentage, integer arithmetic (1800 → 18.00).
        return f"{int(raw) // 100}.{int(raw) % 100:02d}"
    if isinstance(raw, Decimal):
        # A `Numeric(18,4)` quantity arrives as "40.0000"; the file should carry the
        # number, not the column's scale. No grouping — this cell is parsed, not read.
        return str(int(raw)) if raw == raw.to_integral_value() else format(raw.normalize(), "f")
    if isinstance(raw, datetime):
        return raw.isoformat(sep=" ", timespec="seconds")
    if isinstance(raw, date):
        return raw.isoformat()
    return str(raw)


def csv_text(spec: ListSpec, rows: Sequence[Any]) -> str:
    """The CSV body for a set of rows, using the spec's exportable columns."""
    columns = [c for c in spec.columns if c.export]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([c.label for c in columns])
    for row in rows:
        writer.writerow([export_text(c, row) for c in columns])
    return buffer.getvalue()


def csv_rows_response(spec: ListSpec, rows: Sequence[Any]) -> Response:
    """A CSV download of rows already in hand, using the spec's exportable columns.

    Split out of `csv_response` for the Part 8 projections (R10.12): an ageing or
    collections view has no `ListSpec.model` to run `query_rows` against — its rows are a
    service projection, filtered by an as-of date rather than by a query string. `csv_text`
    only ever needed the spec for its columns, so the export path is the same one Part 2
    built and there is no second CSV writer.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    filename = f"{spec.entity}-{stamp}.csv"
    # utf-8-sig: Excel reads a BOM-less UTF-8 CSV as the local codepage and mangles
    # the first non-ASCII name it meets.
    return Response(
        content=csv_text(spec, rows).encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def csv_response(
    db: Session,
    spec: ListSpec,
    params: ListParams,
    *,
    business_unit_id: uuid.UUID | None = None,
    project: Projector | None = None,
) -> Response:
    """Export every row matching the filters on screen, ignoring pagination (R2.8)."""
    rows = query_rows(db, spec, params, business_unit_id=business_unit_id)
    if project:
        rows = list(project(rows))
    return csv_rows_response(spec, rows)


def csv_response_from_request(
    request: Request,
    db: Session,
    spec: ListSpec,
    *,
    business_unit_id: uuid.UUID | None = None,
    project: Projector | None = None,
) -> Response:
    return csv_response(
        db,
        spec,
        params_from_request(request, spec),
        business_unit_id=business_unit_id,
        project=project,
    )
