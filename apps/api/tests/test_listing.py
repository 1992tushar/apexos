"""The one list query helper + the one CSV export (R2.4, R2.5, R2.8, R2.15).

These exercise the machinery directly rather than through a page: part 2 stage 1
builds it, stage 2 proves it on real masters. The spec below is a throwaway over
`Product`, so what is under test is the helper, not any screen's configuration.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.db.listing import (
    Column,
    Filter,
    ListParams,
    ListSpec,
    build_select,
    count_rows,
    query_page,
    query_rows,
    static_options,
)
from app.db.soft_delete import soft_delete
from app.modules.config.models import BusinessUnit, Category
from app.modules.products.models import Product
from app.web.listing import (
    ListView,
    csv_text,
    list_view,
    params_from_request,
)


def _categories(db):
    return [
        (str(c.id), c.name)
        for c in db.scalars(select(Category).where(Category.deleted_at.is_(None)))
    ]


SPEC = ListSpec(
    entity="product",
    model=Product,
    columns=(
        Column("sku_code", "SKU", kind="mono", sort="sku_code"),
        Column("name", "Name", kind="link", sort="name", href="/products/{id}"),
        Column("specification", "Specification"),
        Column("status", "Status", kind="badge", sort="status"),
        Column("reorder_level", "Reorder level", kind="number", sort="reorder_level"),
        Column("created_at", "Created", kind="datetime", sort="created_at", export=False),
    ),
    search=("name", "sku_code", "specification"),
    filters=(
        Filter("category", "Category", "category_id", coerce="uuid", options=_categories),
        Filter(
            "status",
            "Status",
            "status",
            options=static_options(("active", "Active"), ("draft", "Draft")),
        ),
    ),
    sort="sku_code",
    dir="asc",
    page_size=5,
    search_hint="Search products",
)


class _FakeRequest:
    """Just enough of a Request for `params_from_request` / `view_from_request`."""

    def __init__(self, path: str, query: dict[str, str]) -> None:
        self.query_params = query
        self.url = type("U", (), {"path": path})()


def _params(**query) -> ListParams:
    return params_from_request(_FakeRequest("/products", query), SPEC)


def _view(db, **query) -> ListView:
    return list_view(db, SPEC, _params(**query), path="/products")


# --- pagination -------------------------------------------------------------

def test_pagination_walks_every_row_exactly_once(db):
    total = count_rows(db, SPEC, ListParams())
    assert total > SPEC.page_size, "seed must have more rows than one page"

    seen: list[uuid.UUID] = []
    pages = (total + SPEC.page_size - 1) // SPEC.page_size
    for n in range(1, pages + 1):
        page = query_page(db, SPEC, ListParams(page=n))
        assert page.page == n
        seen.extend(r.id for r in page.rows)

    assert len(seen) == total
    assert len(set(seen)) == total, "a row appeared on two pages"


def test_page_boundaries_are_clamped_not_empty(db):
    total = count_rows(db, SPEC, ListParams())
    last = (total + SPEC.page_size - 1) // SPEC.page_size

    first = query_page(db, SPEC, ListParams(page=1))
    assert first.start == 1
    assert first.end == SPEC.page_size
    assert first.has_next and not first.has_prev

    beyond = query_page(db, SPEC, ListParams(page=9999))
    assert beyond.page == last
    assert beyond.rows, "a page past the end must clamp to the last real page"
    assert beyond.has_prev and not beyond.has_next

    below = query_page(db, SPEC, ListParams(page=0))
    assert below.page == 1


def test_pages_and_counts_agree_with_total(db):
    page = query_page(db, SPEC, ListParams(page=2))
    assert page.pages == (page.total + page.page_size - 1) // page.page_size
    assert page.start == page.page_size + 1
    assert page.end == min(page.total, 2 * page.page_size)


# --- sorting ----------------------------------------------------------------

def test_sort_ascending_and_descending_are_mirror_images(db):
    asc = query_page(db, SPEC, ListParams(sort="sku_code", dir="asc"))
    desc_all = query_rows(db, SPEC, ListParams(sort="sku_code", dir="desc"))
    assert [r.sku_code for r in asc.rows] == sorted(r.sku_code for r in asc.rows)
    assert [r.sku_code for r in desc_all[: len(asc.rows)]] == sorted(
        (r.sku_code for r in desc_all), reverse=True
    )[: len(asc.rows)]


def test_unpublished_sort_key_falls_back_to_the_spec_default(db):
    # `?sort=` is user input; anything the spec did not publish must not reach SQL.
    for hostile in ("business_unit_id", "id; drop table product", ""):
        rows = query_page(db, SPEC, ListParams(sort=hostile, dir="asc")).rows
        assert [r.sku_code for r in rows] == sorted(r.sku_code for r in rows)


# --- filters + search -------------------------------------------------------

def test_filter_narrows_the_result_set(db):
    category_id = db.scalar(
        select(Product.category_id).where(Product.deleted_at.is_(None)).limit(1)
    )
    filtered = query_rows(db, SPEC, ListParams(filters={"category": str(category_id)}))
    assert filtered
    assert all(r.category_id == category_id for r in filtered)
    assert len(filtered) < count_rows(db, SPEC, ListParams())


def test_search_matches_any_configured_column(db):
    by_name = query_rows(db, SPEC, ListParams(q="toilet roll"))
    assert by_name and all("toilet roll" in r.name.lower() for r in by_name)

    one = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    by_sku = query_rows(db, SPEC, ListParams(q=one.sku_code.lower()))
    assert one.id in {r.id for r in by_sku}


def test_search_and_filter_compose(db):
    category_id = db.scalar(select(Product.category_id).where(Product.name == "Toilet Roll"))
    rows = query_rows(
        db, SPEC, ListParams(q="toilet", filters={"category": str(category_id)})
    )
    assert rows
    assert all(r.category_id == category_id and "toilet" in r.name.lower() for r in rows)


def test_a_stale_filter_value_is_ignored_not_an_error(db):
    # A shared/bookmarked URL whose value no longer parses must still render (R2.3).
    params = _params(category="not-a-uuid")
    assert "category" not in params.filters
    assert count_rows(db, SPEC, params) == count_rows(db, SPEC, ListParams())

    # And a value that parses but matches nothing simply returns nothing.
    empty = query_page(db, SPEC, ListParams(filters={"category": str(uuid.uuid4())}))
    assert empty.total == 0
    assert empty.rows == []


# --- soft delete + business unit (R2.5) -------------------------------------

def test_soft_deleted_rows_never_appear(db):
    victim = db.scalar(
        select(Product).where(Product.deleted_at.is_(None)).order_by(Product.sku_code)
    )
    before = count_rows(db, SPEC, ListParams())

    soft_delete(db, victim, actor_id=None, label="Product")

    assert count_rows(db, SPEC, ListParams()) == before - 1
    assert victim.id not in {r.id for r in query_rows(db, SPEC, ListParams())}
    assert victim.id not in {r.id for r in query_rows(db, SPEC, ListParams(q=victim.name))}


def test_business_unit_scoping_composes_with_the_filters(db):
    real_bu = db.scalar(select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)))
    assert count_rows(db, SPEC, ListParams(), business_unit_id=real_bu) > 0
    # A business unit with no products sees none of anybody else's.
    assert count_rows(db, SPEC, ListParams(), business_unit_id=uuid.uuid4()) == 0


def test_a_model_without_business_unit_ignores_the_scope(db):
    spec = ListSpec(
        entity="category",
        model=Category,
        columns=(Column("code", "Code", sort="code"), Column("name", "Name")),
        sort="code",
        dir="asc",
    )
    # `category` has a business_unit_id, so use one that genuinely lacks the column.
    bu_spec = ListSpec(
        entity="business_unit",
        model=BusinessUnit,
        columns=(Column("code", "Code", sort="code"),),
        sort="code",
        dir="asc",
    )
    assert count_rows(db, spec, ListParams(), business_unit_id=uuid.uuid4()) == 0
    assert count_rows(db, bu_spec, ListParams(), business_unit_id=uuid.uuid4()) > 0


def test_the_helper_is_the_only_place_that_paginates(db):
    # The same statement backs the count, the page and the export (R2.8), so all
    # three see one row set. If they diverged this would be the first symptom.
    params = ListParams(q="roll")
    stmt = build_select(SPEC, params)
    direct = db.scalar(select(func.count()).select_from(stmt.subquery()))
    assert direct == count_rows(db, SPEC, params) == len(query_rows(db, SPEC, params))


# --- query-string parsing (R2.3) -------------------------------------------

def test_params_come_from_the_query_string(db):
    params = _params(q="  roll  ", sort="name", dir="DESC", page="3", status="active")
    assert params.q == "roll"
    assert params.sort == "name"
    assert params.dir == "desc"
    assert params.page == 3
    assert params.filters == {"status": "active"}


def test_junk_query_string_values_degrade_to_defaults(db):
    params = _params(sort="nope", dir="sideways", page="banana")
    assert params.sort == ""  # not published -> the spec's default sort is used
    assert params.dir == SPEC.dir
    assert params.page == 1


# --- URL building -----------------------------------------------------------

def test_urls_carry_the_current_state_with_one_thing_changed(db):
    view = _view(db, q="roll", status="active")
    name_col = next(c for c in SPEC.columns if c.key == "name")

    sort_url = view.sort_url(name_col)
    assert "q=roll" in sort_url and "status=active" in sort_url
    assert "sort=name" in sort_url and "dir=asc" in sort_url
    assert "page=" not in sort_url  # a new sort starts at page 1

    assert "page=2" in view.page_url(2)
    assert "export=csv" in view.export_url()

    cleared = view.clear_url()
    assert "q=" not in cleared and "status=" not in cleared


def test_clicking_the_active_sort_header_flips_the_direction(db):
    sku_col = next(c for c in SPEC.columns if c.key == "sku_code")
    # The spec's own default sort counts as active even with no ?sort= present.
    assert _view(db).sort_glyph(sku_col) == "↑"
    assert "dir=desc" in _view(db).sort_url(sku_col)
    assert "dir=asc" in _view(db, sort="sku_code", dir="desc").sort_url(sku_col)
    assert _view(db, sort="sku_code", dir="desc").sort_glyph(sku_col) == "↓"


def test_an_inactive_header_shows_no_arrow(db):
    name_col = next(c for c in SPEC.columns if c.key == "name")
    assert _view(db).sort_glyph(name_col) == ""


def test_chips_describe_the_active_filters_and_link_to_removing_one(db):
    view = _view(db, q="roll", status="active")
    chips = {c["label"]: c for c in view.chips()}
    assert chips["Search"]["value"] == "roll"
    assert chips["Status"]["value"] == "Active"  # the option's label, not its value
    # Removing one filter keeps the other.
    assert "status=active" in chips["Search"]["remove_url"]
    assert "q=roll" in chips["Status"]["remove_url"]
    assert "status=" not in chips["Status"]["remove_url"]
    assert not _view(db).chips()


def test_link_columns_resolve_their_href_against_the_row(db):
    view = _view(db)
    name_col = next(c for c in SPEC.columns if c.key == "name")
    row = view.rows[0]
    assert view.href(name_col, row) == f"/products/{row.id}"


# --- CSV export (R2.8) -----------------------------------------------------

def test_export_respects_the_filters_on_screen(db):
    params = ListParams(q="toilet")
    on_screen = count_rows(db, SPEC, params)
    exported = csv_text(SPEC, query_rows(db, SPEC, params))

    body = [line for line in exported.splitlines() if line]
    assert len(body) - 1 == on_screen  # minus the header row
    assert "toilet" in exported.lower()

    unfiltered = csv_text(SPEC, query_rows(db, SPEC, ListParams()))
    assert len(unfiltered.splitlines()) > len(body), "an export must not ignore the filter"


def test_export_ignores_pagination_but_not_filters(db):
    # The largest category, so the filtered set is provably more than one page.
    category_id = db.scalar(
        select(Product.category_id)
        .where(Product.deleted_at.is_(None))
        .group_by(Product.category_id)
        .order_by(func.count().desc())
        .limit(1)
    )
    params = ListParams(filters={"category": str(category_id)}, page=2)
    rows = query_rows(db, SPEC, params)
    assert len(rows) == count_rows(db, SPEC, params) > SPEC.page_size


def test_export_header_and_columns_come_from_the_spec(db):
    exported = csv_text(SPEC, query_rows(db, SPEC, ListParams(page=1)))
    header = exported.splitlines()[0]
    exportable = [c for c in SPEC.columns if c.export]
    assert header.split(",")[: len(exportable)] == [c.label for c in exportable]
    assert "Created" not in header, "export=False columns must be left out"


def test_money_exports_as_a_plain_decimal_never_a_float():
    from app.web.listing import export_text

    money_col = Column("amount_minor", "Amount", kind="money")
    assert export_text(money_col, type("R", (), {"amount_minor": 123456})()) == "1234.56"
    assert export_text(money_col, type("R", (), {"amount_minor": -50})()) == "-0.50"
    assert export_text(money_col, type("R", (), {"amount_minor": 0})()) == "0.00"
    assert export_text(money_col, type("R", (), {"amount_minor": None})()) == ""


def test_export_endpoint_detection(db):
    from app.web.listing import wants_csv

    assert wants_csv(_FakeRequest("/products", {"export": "csv"}))
    assert wants_csv(_FakeRequest("/products", {"export": "CSV"}))
    assert not wants_csv(_FakeRequest("/products", {}))
    assert not wants_csv(_FakeRequest("/products", {"export": "pdf"}))


# --- projection -------------------------------------------------------------

def test_a_view_can_render_a_projection_instead_of_the_orm_rows(db):
    view = list_view(
        db,
        SPEC,
        ListParams(),
        path="/products",
        project=lambda rows: [{"sku_code": r.sku_code, "name": r.name.upper()} for r in rows],
    )
    assert view.total > 0
    assert all(isinstance(r, dict) for r in view.rows)
    name_col = next(c for c in SPEC.columns if c.key == "name")
    assert view.value(view.rows[0], name_col).isupper()


@pytest.mark.parametrize("page_size", [1, 3, 7])
def test_page_size_does_not_change_the_row_set(db, page_size):
    spec = ListSpec(
        entity="product",
        model=Product,
        columns=SPEC.columns,
        sort="sku_code",
        dir="asc",
        page_size=page_size,
    )
    total = count_rows(db, spec, ListParams())
    collected = []
    for n in range(1, (total + page_size - 1) // page_size + 1):
        collected.extend(r.id for r in query_page(db, spec, ListParams(page=n)).rows)
    assert len(set(collected)) == total
