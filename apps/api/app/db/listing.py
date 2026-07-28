"""The one generic paginated / filtered / sorted list query (R2.4, R2.5).

Every list screen in ApexOS — masters now, transactions in parts 3–8 — is the
same four questions: which rows, matching what, in what order, and which page.
This module answers them once. A page declares a `ListSpec` (its columns, its
filters, its default sort) and calls `query_page`; it never writes `ORDER BY`,
`LIMIT` or `OFFSET` itself. R2.4 is explicit that there is exactly one of these,
so a second "search" method on a repository is a bug, not an optimisation.

What the helper guarantees that a hand-rolled query would not:

* **Soft-deleted rows never appear.** Any model carrying `deleted_at` gets the
  `IS NULL` filter automatically (G3, R2.5) — a page cannot forget it.
* **Business-unit scoping composes.** Pass `business_unit_id` and any model with
  the `BusinessUnitMixin` column is scoped; models without it ignore it (R2.5).
* **Sorting is whitelisted.** Only a column that declares `sort=` can be ordered
  by, so `?sort=<anything>` from a URL can neither crash nor reach a column the
  page did not publish.
* **Pagination is stable.** Every order-by gets the primary key appended as a
  tiebreak. Without it, rows sharing a sort value can swap between pages and the
  same row shows twice — or never — as you page through.
* **A stale filter value degrades, never 500s.** A shared URL whose `?category=`
  is no longer a valid UUID drops that filter instead of raising (R2.3).

`ListSpec` is deliberately shared with the presentation layer: `app.web.listing`
builds the query string and URLs from the same object the query reads, and
`_macros.html` renders headers, chips and pagination from it. One definition of
"what this list is" (R2.2) rather than a query config plus a template config that
drift apart.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from math import ceil
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

# A CSV export is "every row matching the filters on screen" (R2.8), which is
# unbounded by definition. This cap keeps one accidental unfiltered export from
# materialising the whole table; `csv_export` reports when it truncates.
EXPORT_ROW_LIMIT = 20_000


@dataclass(frozen=True)
class Column:
    """One column of a list: where the value comes from and how it reads.

    `kind` picks the renderer (`_macros.html:cell`) and the export formatter, so
    adding a column is a config change (R2.2) rather than new markup. `sort` names
    the *model* attribute to order by — omit it and the header is not clickable.
    `key` is read off the row the page renders, which may be a service projection
    rather than the ORM row, so the two are intentionally separate names.
    """

    key: str
    label: str
    kind: str = "text"  # text | mono | money | number | date | datetime | badge | link
    sort: str | None = None
    href: str | None = None  # for kind="link", e.g. "/customers/{id}"
    export: bool = True

    @property
    def css(self) -> str:
        """Cell/header classes implied by `kind` (right-align numbers, mono codes)."""
        if self.kind in ("money", "number"):
            return "num"
        if self.kind == "mono":
            return "mono"
        return ""


@dataclass(frozen=True)
class Filter:
    """One filter chip: a query-string key compared against one model column.

    `options` is a callable rather than a list because most filter dropdowns are
    themselves master data (categories, customer types) and have to be read per
    request. Use `static_options(...)` for a fixed set.
    """

    key: str  # query-string parameter name
    label: str
    column: str  # model attribute to compare against
    coerce: str = "str"  # str | uuid | int | bool
    options: Callable[[Session], Sequence[tuple[str, str]]] | None = None
    all_label: str = "All"


@dataclass(frozen=True)
class ListSpec:
    """The declarative definition of one list (R2.2).

    Held as a module-level constant next to the page that renders it, and passed
    to both the query helper and the macros.
    """

    entity: str  # activity/export name, e.g. "product"
    model: type[Any]
    columns: tuple[Column, ...]
    search: tuple[str, ...] = ()  # model attributes OR'd together for `?q=`
    filters: tuple[Filter, ...] = ()
    sort: str = "created_at"  # default order-by (model attribute)
    dir: str = "desc"
    page_size: int = 25
    search_hint: str = "Search"

    def can_sort(self, key: str) -> bool:
        """Is `key` a sort the page published? The whitelist behind `?sort=`."""
        if not key:
            return False
        return key == self.sort or any(c.sort == key for c in self.columns)


@dataclass(frozen=True)
class ListParams:
    """The list state carried in the query string (R2.3).

    `filters` holds the raw strings as they arrived, already validated as
    coercible, so URL rebuilding and the query read the same values.
    """

    q: str = ""
    sort: str = ""
    dir: str = "asc"
    page: int = 1
    filters: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_filtered(self) -> bool:
        return bool(self.q.strip() or self.filters)


@dataclass(frozen=True)
class ListPage:
    """One page of results plus the counts a pager needs."""

    rows: list[Any]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        if self.page_size <= 0:
            return 1
        return max(1, ceil(self.total / self.page_size))

    @property
    def start(self) -> int:
        """1-based index of the first row on this page (0 when empty)."""
        return 0 if not self.total else (self.page - 1) * self.page_size + 1

    @property
    def end(self) -> int:
        return min(self.total, self.page * self.page_size)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages


def static_options(*pairs: tuple[str, str]) -> Callable[[Session], Sequence[tuple[str, str]]]:
    """A `Filter.options` provider for a fixed set of `(value, label)` choices."""

    def _options(_db: Session) -> Sequence[tuple[str, str]]:
        return pairs

    return _options


def coerce(kind: str, raw: str) -> Any:
    """Turn a query-string value into something comparable to a column.

    Raises `ValueError` on anything malformed; callers treat that as "drop this
    filter" rather than as an error, so a stale shared URL still renders.
    """
    if kind == "uuid":
        return uuid.UUID(raw)
    if kind == "int":
        return int(raw)
    if kind == "bool":
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return raw


def is_valid(kind: str, raw: str) -> bool:
    try:
        coerce(kind, raw)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def build_select(
    spec: ListSpec, params: ListParams, *, business_unit_id: uuid.UUID | None = None
) -> Select:
    """The unordered, unpaginated SELECT for a spec + params.

    Shared by the count, the page and the export so all three see exactly the
    same row set — which is what makes "export respects the filters on screen"
    (R2.8) true by construction rather than by convention.
    """
    model = spec.model
    stmt = select(model)

    if hasattr(model, "deleted_at"):
        stmt = stmt.where(model.deleted_at.is_(None))
    if business_unit_id is not None and hasattr(model, "business_unit_id"):
        stmt = stmt.where(model.business_unit_id == business_unit_id)

    for spec_filter in spec.filters:
        raw = (params.filters or {}).get(spec_filter.key)
        if raw in (None, ""):
            continue
        try:
            value = coerce(spec_filter.coerce, raw)
        except (ValueError, TypeError, AttributeError):
            continue  # a stale URL, not an error (R2.3)
        column = getattr(model, spec_filter.column, None)
        if column is None:
            continue
        stmt = stmt.where(column == value)

    term = (params.q or "").strip()
    if term and spec.search:
        like = f"%{term.lower()}%"
        matches = [
            func.lower(func.coalesce(getattr(model, name), "")).like(like)
            for name in spec.search
            if hasattr(model, name)
        ]
        if matches:
            stmt = stmt.where(or_(*matches))
    return stmt


def effective_sort(spec: ListSpec, params: ListParams) -> tuple[str, str]:
    """The sort actually applied: the request's if published, else the spec's."""
    if spec.can_sort(params.sort):
        direction = params.dir if params.dir in ("asc", "desc") else "asc"
        return params.sort, direction
    return spec.sort, spec.dir


def _ordered(spec: ListSpec, params: ListParams, stmt: Select) -> Select:
    key, direction = effective_sort(spec, params)
    column = getattr(spec.model, key, None)
    if column is None:
        return stmt
    stmt = stmt.order_by(column.desc() if direction == "desc" else column.asc())
    # Stable tiebreak: without it, rows sharing a sort value can move between
    # pages and the same row appears twice — or not at all — while paging.
    pk = getattr(spec.model, "id", None)
    if pk is not None and key != "id":
        stmt = stmt.order_by(pk.asc())
    return stmt


def count_rows(
    db: Session,
    spec: ListSpec,
    params: ListParams,
    *,
    business_unit_id: uuid.UUID | None = None,
) -> int:
    stmt = build_select(spec, params, business_unit_id=business_unit_id)
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def query_page(
    db: Session,
    spec: ListSpec,
    params: ListParams,
    *,
    business_unit_id: uuid.UUID | None = None,
) -> ListPage:
    """One page of `spec`, filtered and sorted per `params`.

    The requested page is clamped into range, so `?page=0` and `?page=9999` both
    land on a real page instead of rendering an empty table.
    """
    total = count_rows(db, spec, params, business_unit_id=business_unit_id)
    size = max(1, spec.page_size)
    pages = max(1, ceil(total / size))
    page = min(max(1, params.page), pages)
    stmt = _ordered(spec, params, build_select(spec, params, business_unit_id=business_unit_id))
    rows = list(db.scalars(stmt.offset((page - 1) * size).limit(size)))
    return ListPage(rows=rows, total=total, page=page, page_size=size)


def query_rows(
    db: Session,
    spec: ListSpec,
    params: ListParams,
    *,
    business_unit_id: uuid.UUID | None = None,
    limit: int = EXPORT_ROW_LIMIT,
) -> list[Any]:
    """Every row matching the same filters, ignoring pagination (the export path)."""
    stmt = _ordered(spec, params, build_select(spec, params, business_unit_id=business_unit_id))
    return list(db.scalars(stmt.limit(limit)))
