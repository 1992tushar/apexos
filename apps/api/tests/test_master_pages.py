"""The machinery proven end to end on two masters (R2.11).

`test_listing.py` and `test_list_macros.py` test the machinery in isolation. These
go through the real pages — `/products` and `/customers` — and assert the four
capabilities R2.11 names: list (search + filter + sort + pagination), CSV export
respecting the filters on screen, duplicate rejection as a readable field error,
and change history. Nothing here knows how the query or the table is built; if a
page stopped using the shared machinery these would still pass, so each one also
checks a marker only the shared macros emit.
"""
from __future__ import annotations

import csv
import io
import re
import uuid

import pytest
from sqlalchemy import func, select

from app.modules.activity.models import ActivityLog
from app.modules.config.models import Category, CustomerType
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerCreate, CustomerUpdate
from app.modules.customers.service import CustomerService
from app.modules.products.listing import PRODUCT_LIST
from app.modules.products.models import Product


def _rows(html: str) -> int:
    """Data rows in the one shared table."""
    body = html.split("<tbody>")[1].split("</tbody>")[0] if "<tbody>" in html else ""
    return body.count("<tr>")


def _shown_total(html: str) -> int:
    """The count the shared pagination macro renders."""
    match = re.search(r"of ([\d,]+)\s*</div>", html)
    assert match, "the pagination macro should state the total"
    return int(match.group(1).replace(",", ""))


def _csv_reader(body: str):
    # The export leads with a BOM so Excel opens it as UTF-8; `utf-8-sig` is the
    # reader's half of that contract.
    return io.StringIO(body.encode().decode("utf-8-sig"))


def _csv_rows(body: str) -> list[list[str]]:
    return list(csv.reader(_csv_reader(body)))[1:]


def _category(db, code: str) -> Category:
    return db.scalars(select(Category).where(Category.code == code)).first()


# --- the list (R2.11, R2.1-R2.5) --------------------------------------------

@pytest.mark.parametrize("path", ["/products", "/customers"])
def test_the_list_page_is_the_shared_machinery(client, path):
    html = client.get(path).text
    assert 'class="list-toolbar"' in html      # search + filters, one definition
    assert 'class="th-sort"' in html           # sortable headers from the spec
    assert 'class="pagination"' in html
    assert "<table>" in html
    # No hand-rolled table survived the wiring.
    assert html.count("<tbody>") == 1


@pytest.mark.parametrize("path", ["/products", "/customers"])
def test_pagination_is_real_and_pages_do_not_overlap(client, path):
    first = client.get(path).text
    total = _shown_total(first)
    assert total > 100, "the seed must make pagination real (R2.13)"
    assert _rows(first) == 25, "one page is the spec's page_size"
    assert 'rel="next"' in first
    assert 'rel="prev"' not in first

    second = client.get(f"{path}?page=2").text
    assert _rows(second) == 25
    assert 'rel="prev"' in second
    assert set(re.findall(r'href="[^"]*/([0-9a-f-]{36})"', first)).isdisjoint(
        re.findall(r'href="[^"]*/([0-9a-f-]{36})"', second)
    )


def test_search_narrows_the_product_list_and_survives_paging(client):
    everything = _shown_total(client.get("/products").text)
    html = client.get("/products?q=Garbage").text
    found = _shown_total(html)
    assert 0 < found < everything
    assert "Garbage" in html
    # A page link keeps the search (R2.3).
    link = re.search(r'rel="next" href="([^"]+)"', html)
    if link:
        assert "q=Garbage" in link.group(1)


def test_a_filter_narrows_the_list_and_offers_a_chip_to_remove_it(client, db):
    # "Cleaning Chemicals" rather than a category whose name carries an "&": the chip
    # is HTML-escaped, and this test is about the filter, not about escaping.
    category = _category(db, "CC")
    html = client.get(f"/products?category={category.id}").text
    in_category = db.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.category_id == category.id, Product.deleted_at.is_(None))
    )
    assert _shown_total(html) == in_category
    assert 'class="chip"' in html
    assert category.name in html          # the chip names the value, not the raw id
    assert str(category.id) not in html.split('class="chip"')[1][:200]


def test_sorting_is_whitelisted_and_reversible(client):
    def first_sku(query: str) -> str:
        html = client.get(f"/products?{query}").text
        return re.search(r'<td class="mono">([^<]+)</td>', html).group(1).strip()

    assert first_sku("sort=sku_code&dir=asc") < first_sku("sort=sku_code&dir=desc")
    # An unpublished sort column degrades to the spec's default rather than raising.
    assert first_sku("sort=selling_price_minor") == first_sku("sort=sku_code&dir=asc")


def test_a_stale_filter_value_still_renders_the_list(client):
    assert client.get("/products?category=not-a-uuid&status=nonsense").status_code == 200


def test_soft_deleted_rows_never_reach_the_page(client, db):
    from app.db.soft_delete import soft_delete

    product = db.scalars(
        select(Product).where(Product.deleted_at.is_(None), Product.name.like("Eco %"))
    ).first()
    assert product is not None
    before = _shown_total(client.get("/products").text)
    assert product.sku_code in client.get(f"/products?q={product.sku_code}").text
    soft_delete(db, product, actor_id=None, label="Product")
    db.commit()
    try:
        # Searching its own SKU now finds nothing (the search box still echoes the
        # term, so this asserts on the table body rather than the whole page).
        html = client.get(f"/products?q={product.sku_code}").text
        assert _rows(html) == 0
        assert "No rows match these filters." in html
        assert _shown_total(client.get("/products").text) == before - 1
    finally:
        product.deleted_at = None
        db.commit()


def test_reading_a_list_or_a_detail_page_writes_no_activity(client, db):
    product = db.scalars(select(Product).where(Product.deleted_at.is_(None))).first()
    before = db.scalar(select(func.count()).select_from(ActivityLog))
    client.get("/products?q=Bag&sort=name")
    client.get(f"/products/{product.id}")
    client.get("/customers?page=3")
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(ActivityLog)) == before


# --- the export (R2.8, R2.11) -----------------------------------------------

@pytest.mark.parametrize(
    ("path", "first_header"), [("/products", "SKU"), ("/customers", "Code")]
)
def test_the_export_is_the_same_view_as_a_file(client, path, first_header):
    response = client.get(f"{path}?export=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    header = next(csv.reader(_csv_reader(response.text)))
    assert header[0] == first_header


def test_a_filtered_export_matches_the_count_on_screen(client, db):
    category = _category(db, "GB")
    query = f"category={category.id}&q=Bag"
    on_screen = _shown_total(client.get(f"/products?{query}").text)
    exported = _csv_rows(client.get(f"/products?{query}&export=csv").text)
    assert len(exported) == on_screen
    assert len(exported) < len(_csv_rows(client.get("/products?export=csv").text))


def test_the_export_carries_projected_columns_not_just_model_ones(client):
    """`category_name` and `stock_on_hand` exist only on the projection."""
    reader = csv.DictReader(_csv_reader(client.get("/products?q=Garbage&export=csv").text))
    row = next(reader)
    assert row["Category"] == "Garbage Bags & Waste Management"
    # A quantity carries its number, not the column's scale ("40", not "40.0000").
    assert row["Stock"] != "" and not row["Stock"].endswith("0000")


# --- duplicate rejection, through the form (R2.9, R2.11) --------------------

def test_a_duplicate_product_comes_back_as_a_readable_flash(client, db):
    existing = db.scalars(
        select(Product).where(Product.sku_code == "AUR-TIS-001")
    ).first()
    response = client.post(
        "/products",
        data={
            "name": existing.name,
            "specification": existing.specification,
            "category_id": str(existing.category_id),
            "brand_id": str(existing.brand_id),
            "uom_id": str(existing.uom_id),
            "reorder_level": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert 'class="flash flash-bad"' in response.text
    assert "already uses this" in response.text
    assert "IntegrityError" not in response.text


def test_a_duplicate_customer_comes_back_as_a_readable_flash(client, db):
    existing = db.scalars(
        select(Customer).where(Customer.code == "CUST-0001")
    ).first()
    ctype = db.scalars(select(CustomerType)).first()
    response = client.post(
        "/customers",
        data={
            "name": existing.name,
            "customer_type_id": str(ctype.id),
            "city": existing.city,
            "credit_limit_rupees": "0",
            "payment_terms_days": "30",
        },
        follow_redirects=True,
    )
    assert 'class="flash flash-bad"' in response.text
    assert "already uses this name and city" in response.text


# --- change history (R2.10, R2.11) ------------------------------------------

def test_the_product_detail_page_shows_its_history(client, db):
    product = db.scalars(
        select(Product).where(Product.sku_code == "AUR-TIS-001")
    ).first()
    html = client.get(f"/products/{product.id}").text
    assert "Change history" in html
    assert "Created" in html
    assert product.name in html


def test_a_customers_history_names_the_fields_that_changed(client, db):
    service = CustomerService(db)
    customer = service.create(
        CustomerCreate(
            name="History Check Traders",
            customer_type_id=db.scalars(select(CustomerType)).first().id,
            city="Nagpur",
            credit_limit_minor=100000,
            payment_terms_days=30,
        ),
        actor_id=None,
    )
    service.update(
        customer.id,
        CustomerUpdate(city="Raipur", payment_terms_days=45),
        actor_id=None,
    )
    db.commit()

    html = client.get(f"/customers/{customer.id}").text
    assert "Change history" in html
    assert "Updated" in html and "Created" in html
    assert "Nagpur" in html and "Raipur" in html   # before → after
    assert "45" in html


def test_an_unknown_product_id_renders_the_error_page(client):
    response = client.get(f"/products/{uuid.uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.text.lower()


# --- the spec is configuration, not markup (R2.2) --------------------------

def test_adding_a_column_is_a_config_change(client):
    """Every column on screen comes from the spec, so the spec is the contract."""
    html = client.get("/products").text
    for column in PRODUCT_LIST.columns:
        assert column.label in html
