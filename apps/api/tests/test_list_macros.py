"""The one list/table pattern, rendered (R2.1, R2.2, R2.10).

Part 2 stage 1 builds the machinery; stage 2 wires the master pages onto it. So
these render the macros against a real `ListView` over real data rather than
through a page, which keeps the macros under test and not any page's config.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.listing import Column, Filter, ListParams, ListSpec, static_options
from app.modules.activity.history import FieldChange, HistoryEntry
from app.modules.config.models import Category
from app.modules.products.models import Product
from app.web.core import templates
from app.web.listing import list_view

SPEC = ListSpec(
    entity="product",
    model=Product,
    columns=(
        Column("sku_code", "SKU", kind="mono", sort="sku_code"),
        Column("name", "Name", kind="link", sort="name", href="/products/{id}"),
        Column("specification", "Specification"),
        Column("status", "Status", kind="badge", sort="status"),
        Column("reorder_level", "Reorder level", kind="number"),
    ),
    search=("name", "sku_code"),
    filters=(
        Filter(
            "category",
            "Category",
            "category_id",
            coerce="uuid",
            options=lambda db: [
                (str(c.id), c.name)
                for c in db.scalars(select(Category).where(Category.deleted_at.is_(None)))
            ],
        ),
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


def _render(source: str, **context) -> str:
    return templates.env.from_string(source).render(**context)


def _view(db, **params):
    return list_view(db, SPEC, ListParams(**params), path="/products")


TOOLBAR = '{% import "_macros.html" as ui %}{{ ui.list_toolbar(view) }}'
TABLE = '{% import "_macros.html" as ui %}{{ ui.list_table(view) }}'
TABLE_WITH_ACTIONS = (
    '{% import "_macros.html" as ui %}'
    "{% call(row) ui.list_table(view) %}"
    '{{ ui.delete_button("/products/" ~ row.id ~ "/delete", row.name) }}'
    "{% endcall %}"
)
PAGER = '{% import "_macros.html" as ui %}{{ ui.pagination(view) }}'
EMPTY = '{% import "_macros.html" as ui %}{{ ui.list_empty(view, "No products yet.") }}'
HISTORY = '{% import "_macros.html" as ui %}{{ ui.history_panel(entries) }}'


# --- toolbar (R2.1) ---------------------------------------------------------

def test_the_toolbar_renders_a_search_box_and_a_select_per_filter(db):
    html = _render(TOOLBAR, view=_view(db))
    assert 'type="search"' in html and 'name="q"' in html
    assert 'placeholder="Search products"' in html
    assert html.count("<select") == 2  # one per configured filter
    assert 'name="category"' in html and 'name="status"' in html
    assert "Export CSV" in html and "export=csv" in html


def test_the_toolbar_is_a_get_form_so_a_filtered_list_is_a_url(db):
    html = _render(TOOLBAR, view=_view(db))
    assert 'method="get"' in html and 'action="/products"' in html
    assert "<form" in html and 'method="post"' not in html


def test_the_toolbar_reflects_the_current_state(db):
    view = _view(db, q="roll", filters={"status": "active"})
    html = _render(TOOLBAR, view=view)
    assert 'value="roll"' in html
    assert '<option value="active" selected>Active</option>' in html
    assert "Clear" in html


def test_an_unfiltered_toolbar_offers_nothing_to_clear(db):
    html = _render(TOOLBAR, view=_view(db))
    assert ">Clear<" not in html
    assert "filter-chips" not in html


def test_active_filters_render_as_removable_chips(db):
    view = _view(db, q="roll", filters={"status": "active"})
    html = _render(TOOLBAR, view=view)
    assert "filter-chips" in html
    assert html.count('class="chip"') == 2
    assert ">Search<" in html and "roll" in html
    assert ">Status<" in html and "Active" in html


def test_a_search_carries_the_sort_so_filtering_does_not_reset_it(db):
    html = _render(TOOLBAR, view=_view(db, sort="name", dir="desc"))
    assert '<input type="hidden" name="sort" value="name" />' in html
    assert '<input type="hidden" name="dir" value="desc" />' in html


# --- table (R2.1, R2.2) -----------------------------------------------------

def test_headers_come_from_the_spec_and_only_sortable_ones_are_links(db):
    html = _render(TABLE, view=_view(db))
    header_block = html.split("</thead>")[0]
    for column in SPEC.columns:
        assert column.label in header_block
    # Three columns declare `sort=`; Specification and Reorder level do not, so
    # they render as plain text rather than as links.
    assert html.count("th-sort") == 3
    assert "th-sort" not in header_block.split("Specification")[1].split("</th>")[0]


def test_a_quantity_column_shows_the_significant_digits_only(db):
    body = _render(TABLE, view=_view(db)).split("<tbody>")[1]
    assert "20.0000" not in body, "Numeric(18,4) padding must not reach the screen"
    assert ">20<" in body.replace(" ", "").replace("\n", "")


def test_a_sortable_header_links_to_the_query_string_state(db):
    html = _render(TABLE, view=_view(db, q="roll"))
    link = re.search(r'class="th-sort" href="([^"]+)"', html).group(1)
    assert link.startswith("/products?")
    assert "sort=" in link and "dir=" in link and "q=roll" in link


def test_the_active_sort_header_carries_an_arrow(db):
    ascending = _render(TABLE, view=_view(db))
    assert "↑" in ascending and "↓" not in ascending
    descending = _render(TABLE, view=_view(db, sort="sku_code", dir="desc"))
    assert "↓" in descending and "↑" not in descending


def test_every_cell_kind_renders(db):
    html = _render(TABLE, view=_view(db))
    body = html.split("<tbody>")[1]
    assert 'class="mono"' in html  # kind="mono"
    assert 'class="row-link" href="/products/' in body  # kind="link" resolves its href
    assert "badge badge-" in body  # kind="badge"
    assert 'class="num"' in html  # kind="number" right-aligns


def test_the_page_size_bounds_the_rendered_rows(db):
    html = _render(TABLE, view=_view(db))
    assert html.split("<tbody>")[1].count("<tr>") == SPEC.page_size


def test_a_blank_value_renders_an_em_dash_not_the_word_none(db):
    view = _view(db)
    view.rows = [type("R", (), {"id": "x", "sku_code": "S", "name": "N",
                                "specification": None, "status": "active",
                                "reorder_level": 0})()]
    body = _render(TABLE, view=view).split("<tbody>")[1]
    assert "—" in body
    assert "None" not in body


def test_the_actions_column_keeps_its_per_entity_verbs(db):
    """R1.2's delete button survives the generic table (the whole point of the caller)."""
    html = _render(TABLE_WITH_ACTIONS, view=_view(db))
    assert "<th>Actions</th>" in html
    assert 'class="row-actions"' in html
    assert html.count("/delete") == SPEC.page_size
    assert html.count("btn-danger") == SPEC.page_size

    without = _render(TABLE, view=_view(db))
    assert "<th>Actions</th>" not in without


# --- pagination -------------------------------------------------------------

def test_the_pager_states_the_range_and_the_total(db):
    view = _view(db)
    html = _render(PAGER, view=view)
    assert f"of {view.total}" in html.replace(",", "")
    assert f"Page 1 of {view.pages}" in html
    assert "1–5" in html


def test_the_first_page_cannot_go_back_and_the_last_cannot_go_forward(db):
    first = _render(PAGER, view=_view(db, page=1))
    assert 'rel="next"' in first
    assert 'rel="prev"' not in first
    assert first.count("btn-disabled") == 1

    last = _render(PAGER, view=_view(db, page=9999))
    assert 'rel="prev"' in last
    assert 'rel="next"' not in last


def test_page_links_preserve_the_filters(db):
    html = _render(PAGER, view=_view(db, q="a"))
    link = re.search(r'rel="next" href="([^"]+)"', html)
    if link:  # only if "a" matches more than one page
        assert "q=a" in link.group(1)


def test_a_single_page_shows_the_count_without_controls(db):
    # A full SKU rather than a product name: the seeded catalogue is now hundreds of
    # rows (R2.13), and any name fragment spans several pages.
    view = _view(db, q="AUR-TIS-001")
    html = _render(PAGER, view=view)
    assert view.pages == 1
    assert "pagination-controls" not in html
    assert "of 1" in html


def test_an_empty_filtered_list_offers_a_way_out(db):
    filtered = _render(EMPTY, view=_view(db, q="nothing-matches-this"))
    assert "No rows match these filters." in filtered
    assert "Clear filters" in filtered

    unfiltered = _render(EMPTY, view=_view(db))
    assert "No products yet." in unfiltered
    assert "Clear filters" not in unfiltered


# --- change history (R2.10) -------------------------------------------------

def test_the_history_panel_renders_entries_with_their_field_changes():
    entries = [
        HistoryEntry(
            occurred_at=datetime(2026, 7, 20, 9, 30, tzinfo=UTC),
            verb="updated",
            summary="Customer Blue Fig updated",
            actor="Apex Founder",
            changes=(
                FieldChange("city", "City", "Pune", "Mumbai"),
                FieldChange("credit_limit_minor", "Credit limit (₹)", "0.00", "5000.00"),
            ),
        ),
        HistoryEntry(
            occurred_at=datetime(2026, 7, 19, 9, 30, tzinfo=UTC),
            verb="created",
            summary="Customer Blue Fig created",
            actor="System",
        ),
    ]
    html = _render(HISTORY, entries=entries)
    assert "Change history" in html
    assert "Updated" in html and "Created" in html
    assert "Apex Founder" in html and "System" in html
    assert "Pune" in html and "Mumbai" in html
    assert "Credit limit (₹)" in html
    assert "20 Jul 2026" in html  # the exact timestamp is the hover title


def test_an_entry_with_no_diff_shows_only_its_summary():
    entry = HistoryEntry(
        occurred_at=datetime(2026, 7, 20, tzinfo=UTC),
        verb="created",
        summary="Customer Blue Fig created",
        actor="System",
    )
    html = _render(HISTORY, entries=[entry])
    assert "history-changes" not in html
    assert "Customer Blue Fig created" in html


def test_a_record_with_no_history_says_so_rather_than_rendering_an_empty_list():
    html = _render(HISTORY, entries=[])
    assert "No recorded changes yet." in html
    assert "<ol" not in html
