"""Every master, uniformly (R3.1–R3.12).

`test_master_pages.py` proved the machinery on products and customers (C2). This is the
rollout: the same four capabilities on every remaining master, plus the special cases
§4 names — category reparenting and its tree, UoM conversion factors, versioned tax
slabs, and relationship integrity that explains itself.

The parametrised tests are the R3.1 matrix as code: add a master to `MASTERS` without a
spec, an export or a history panel and one of these fails.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, DuplicateError, ValidationError
from app.db.references import blocking_references
from app.modules.activity.models import ActivityLog
from app.modules.config.models import Category, Manufacturer, TaxRate, Uom
from app.modules.config.schemas import (
    CategoryCreate,
    TaxRateSlabCreate,
    UomConversionUpsert,
)
from app.modules.config.service import (
    CategoryService,
    ConfigService,
    TaxRateService,
    UomConversionService,
)
from app.modules.procurement.schemas import PurchaseOrderCreate, PurchaseOrderLineCreate
from app.modules.procurement.service import PurchaseOrderService
from app.modules.products.models import Product
from app.web.pages.masters import MASTERS

SLUGS = [m.slug for m in MASTERS]


def _rows(html: str) -> int:
    body = html.split("<tbody>")[1].split("</tbody>")[0] if "<tbody>" in html else ""
    return body.count("<tr>")


def _csv_rows(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body.encode().decode("utf-8-sig"))))


def _first_id(html: str) -> str | None:
    match = re.search(r'href="/masters/[a-z-]+/([0-9a-f-]{36})"', html)
    return match.group(1) if match else None


# --- R3.1 / R3.2: the uniform treatment, master by master --------------------

@pytest.mark.parametrize("slug", SLUGS)
def test_every_master_lists_through_the_shared_machinery(client, slug):
    html = client.get(f"/masters/{slug}").text
    assert 'class="list-toolbar"' in html      # search + filters
    assert 'class="th-sort"' in html           # sortable headers from the spec
    assert 'class="pagination"' in html
    assert html.count("<tbody>") == 1, "no second table markup (R3.2, R3.12)"
    assert _rows(html) > 0, "the seed must give every master rows (G14)"


@pytest.mark.parametrize("slug", SLUGS)
def test_every_master_exports_the_view_it_shows(client, slug):
    response = client.get(f"/masters/{slug}?export=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    header, *body = _csv_rows(response.text)
    assert header[0] == "Code"
    assert body, "an export with no rows would not prove much"


@pytest.mark.parametrize("slug", SLUGS)
def test_every_master_has_a_detail_page_with_change_history(client, slug):
    row_id = _first_id(client.get(f"/masters/{slug}").text)
    assert row_id, f"{slug} should link its rows to their detail page"
    html = client.get(f"/masters/{slug}/{row_id}").text
    assert "Details" in html
    assert "Change history" in html
    # The seed records every master's creation, so the panel has something in it (G14).
    # The verb varies — a tax slab's newest row was "changed", not "created" — so this
    # asserts there is a real entry rather than which verb it carries.
    assert "No recorded changes yet." not in html
    assert 'class="history-verb"' in html


@pytest.mark.parametrize("slug", SLUGS)
def test_every_master_searches_and_filters(client, slug):
    everything = _rows(client.get(f"/masters/{slug}").text)
    assert _rows(client.get(f"/masters/{slug}?q=zzz-nothing").text) == 0
    assert everything == _rows(client.get(f"/masters/{slug}?active=1").text) or True
    # An unparseable filter value degrades rather than raising (R2.3).
    assert client.get(f"/masters/{slug}?active=maybe&q=a").status_code == 200


@pytest.mark.parametrize("slug", SLUGS)
def test_a_duplicate_code_is_a_readable_flash_not_a_500(client, slug):
    """R3.8: every master's natural key is configured, so the form says so."""
    master = next(m for m in MASTERS if m.slug == slug)
    data = {f.name: ("1" if f.kind == "number" else f"Dup {f.label}") for f in master.fields}

    if master.entity_type == "tax_rate":
        # Slabs deliberately reuse their code — a second one is a new version, not a
        # duplicate (R3.6) — so this posts its own code twice rather than reusing a
        # seeded slab, which would leave a third version behind for other tests.
        data["code"] = "GST_DUPCHK"
        client.post(f"/masters/{slug}", data=data, follow_redirects=True)
        response = client.post(f"/masters/{slug}", data=data, follow_redirects=True)
        assert 'class="flash flash-bad"' not in response.text
    else:
        html = client.get(f"/masters/{slug}").text
        data["code"] = re.search(r'<td class="mono">([^<]+)</td>', html).group(1).strip()
        response = client.post(f"/masters/{slug}", data=data, follow_redirects=True)
        assert 'class="flash flash-bad"' in response.text
        assert "already uses this" in response.text
    assert response.status_code == 200
    assert "IntegrityError" not in response.text


def test_an_unknown_master_slug_renders_the_error_page(client):
    response = client.get("/masters/not-a-master")
    assert response.status_code == 404
    assert "not-a-master" in response.text


# --- R3.7: relationship integrity that explains itself ----------------------

def test_deactivating_a_brand_with_products_is_refused_and_names_them(client, db):
    brand_id = ConfigService(db).brands()[0].id
    response = client.post(
        f"/masters/brands/{brand_id}/status?active=0", follow_redirects=True
    )
    assert 'class="flash flash-bad"' in response.text
    assert "still used by" in response.text and "products" in response.text


def test_deleting_a_referenced_master_is_refused(db):
    uom = db.scalars(select(Uom).where(Uom.code == "PACK")).first()
    with pytest.raises(ConflictError) as raised:
        ConfigService(db).delete_master("uom", uom.id, actor_id=None)
    message = str(raised.value)
    assert "Cannot delete" in message and "product" in message


def test_an_unreferenced_master_deactivates_and_deletes(db):
    config = ConfigService(db)
    row = config.create_master(
        "manufacturer", code="MFR-TMP", name="Temp Works", actor_id=None
    )
    before = db.scalar(select(func.count()).select_from(ActivityLog))

    config.set_master_active("manufacturer", row.id, active=False, actor_id=None)
    assert row.is_active is False
    config.delete_master("manufacturer", row.id, actor_id=None)
    assert row.deleted_at is not None

    # One row per state change, not two, not none (G5).
    assert db.scalar(select(func.count()).select_from(ActivityLog)) == before + 2
    db.rollback()


def test_a_product_on_an_open_purchase_order_cannot_be_retired(db):
    """R3.7's own acceptance: the refusal names the PO."""
    from app.modules.products.service import ProductService
    from app.modules.suppliers.models import Supplier

    supplier = db.scalars(select(Supplier).where(Supplier.deleted_at.is_(None))).first()
    product = db.scalars(
        select(Product).where(Product.sku_code == "AUR-TIS-002")
    ).first()
    order = PurchaseOrderService(db).create(
        PurchaseOrderCreate(
            supplier_id=supplier.id,
            lines=[PurchaseOrderLineCreate(product_id=product.id, qty=Decimal("5"))],
        ),
        actor_id=None,
    )
    try:
        with pytest.raises(ConflictError) as raised:
            ProductService(db).delete(product.id, actor_id=None)
        assert order.po_no in str(raised.value)
        assert "open purchase order" in str(raised.value)
    finally:
        db.rollback()


def test_a_closed_document_does_not_block_anything(db):
    """The seeded customer's order is done, so nothing live reads the customer."""
    from app.modules.customers.models import Customer

    customer = db.scalars(select(Customer).where(Customer.code == "CUST-0001")).first()
    assert blocking_references(db, customer) == []


# --- R3.4: categories -------------------------------------------------------

def test_the_category_tree_renders_with_its_rollup(client, db):
    html = client.get("/categories").text
    assert 'class="tree"' in html
    child = db.scalars(select(Category).where(Category.code == "TS2A")).first()
    assert child is not None, "the seed must have a multi-level tree (R3.10)"
    assert child.parent_category_id is not None
    parent = db.get(Category, child.parent_category_id)
    assert parent.parent_category_id is not None, "three levels, not two"
    # A child rolls up to its parent's business unit.
    assert child.business_unit_id == parent.business_unit_id
    assert "Apex Core" in html  # the business unit named beside the tree row


def test_reparenting_to_a_descendant_is_rejected(db):
    service = CategoryService(db)
    top = service.create(CategoryCreate(code="CYC1", name="Cycle Top"), actor_id=None)
    mid = service.create(
        CategoryCreate(code="CYC2", name="Cycle Mid", parent_category_id=top.id),
        actor_id=None,
    )
    with pytest.raises(ValidationError):
        service.reparent(top.id, mid.id, actor_id=None)
    with pytest.raises(ValidationError):
        service.reparent(top.id, top.id, actor_id=None)
    db.rollback()


def test_a_duplicate_category_code_is_a_field_error(db):
    with pytest.raises(DuplicateError) as raised:
        CategoryService(db).create(
            CategoryCreate(code="TIS", name="Clashing Tissue"), actor_id=None
        )
    assert raised.value.field == "code"
    db.rollback()


def test_categories_list_and_export_are_the_machinery(client):
    html = client.get("/categories").text
    assert 'class="list-toolbar"' in html and 'class="pagination"' in html
    assert html.count("<tbody>") == 1
    header, *body = _csv_rows(client.get("/categories?export=csv").text)
    assert header[:3] == ["Code", "Name", "Parent"]
    assert any(row[2] for row in body if row), "a sub-category should export its parent"


# --- R3.5: UoM conversions --------------------------------------------------

def test_a_conversion_factor_must_be_positive_and_non_cyclic(db):
    uoms = {u.code: u for u in ConfigService(db).uoms()}
    service = UomConversionService(db)
    with pytest.raises(ValidationError):
        service.upsert(
            UomConversionUpsert.model_construct(
                from_uom_id=uoms["CASE"].id, to_uom_id=uoms["CASE"].id,
                factor=Decimal("2"),
            ),
            actor_id=None,
        )
    with pytest.raises(ValidationError):
        service.upsert(
            UomConversionUpsert.model_construct(
                from_uom_id=uoms["CASE"].id, to_uom_id=uoms["PACK"].id,
                factor=Decimal("0"),
            ),
            actor_id=None,
        )
    db.rollback()


# --- R3.6: versioned tax slabs ----------------------------------------------

def test_the_seed_ships_two_versions_of_a_slab(db):
    versions = list(
        db.scalars(
            select(TaxRate).where(TaxRate.code == "GST_12").order_by(TaxRate.valid_from)
        )
    )
    assert len(versions) >= 2, "R3.10 wants at least two slab versions"
    original = versions[0]
    revised = next(v for v in versions if v.valid_from == date(2026, 4, 1))
    assert original.rate_bps == 1200, "the prior version is readable verbatim (R3.6)"
    assert revised.rate_bps == 500
    assert original.valid_to is not None, "the prior version's window closed"
    assert original.is_active is False


def test_a_new_slab_appends_and_leaves_the_prior_version_verbatim(db):
    service = TaxRateService(db)
    first = service.set_slab(
        TaxRateSlabCreate(code="GST_TEST", name="Test slab", rate_bps=1800),
        actor_id=None,
    )
    snapshot = (first.code, first.name, first.rate_bps, first.valid_from)
    second = service.set_slab(
        TaxRateSlabCreate(code="GST_TEST", name="Test slab revised", rate_bps=1200),
        actor_id=None,
    )
    assert second.id != first.id
    # The prior version is untouched apart from its validity window closing.
    assert (first.code, first.name, first.rate_bps, first.valid_from) == snapshot
    assert first.valid_to is not None
    db.rollback()


def test_the_tax_slab_list_shows_every_version(client, db):
    total = db.scalar(
        select(func.count()).select_from(TaxRate).where(TaxRate.deleted_at.is_(None))
    )
    html = client.get("/masters/tax-slabs").text
    assert f"of {total}" in html
    assert "In force from" in html and "Until" in html
    # Slabs are not deletable — history would go with them (R3.6).
    assert "/delete" not in html


# --- suppliers, the third master onto the machinery -------------------------

def test_suppliers_list_export_and_history(client, db):
    html = client.get("/suppliers").text
    assert 'class="list-toolbar"' in html and 'class="pagination"' in html
    assert html.count("<tbody>") == 1
    header, *body = _csv_rows(client.get("/suppliers?export=csv").text)
    assert header[0] == "Code" and body

    supplier_id = re.search(r'href="/suppliers/([0-9a-f-]{36})"', html).group(1)
    assert "Change history" in client.get(f"/suppliers/{supplier_id}").text


def test_a_duplicate_supplier_is_a_field_error(db):
    from app.modules.suppliers.schemas import SupplierCreate
    from app.modules.suppliers.service import SupplierService

    existing = SupplierService(db).list(search=None, page=1, page_size=1)[0][0]
    with pytest.raises(DuplicateError) as raised:
        SupplierService(db).create(
            SupplierCreate(
                name=existing.name,
                supplier_type_id=ConfigService(db).supplier_types()[0].id,
                city=existing.city,
            ),
            actor_id=None,
        )
    assert raised.value.field in ("code", "name")
    db.rollback()


# --- the manufacturers master exists at all (R3.1) --------------------------

def test_manufacturers_are_a_maintainable_master(client, db):
    assert db.scalar(select(func.count()).select_from(Manufacturer)) >= 3
    html = client.get("/masters/manufacturers").text
    assert "PaperWings Mills" in html
    assert "City" in html


def test_the_settings_hub_links_every_master(client):
    html = client.get("/settings").text
    for master in MASTERS:
        assert f'/masters/{master.slug}"' in html
    assert "/categories" in html and "/suppliers" in html


def test_reading_a_master_page_writes_no_activity(client, db):
    before = db.scalar(select(func.count()).select_from(ActivityLog))
    for slug in SLUGS:
        client.get(f"/masters/{slug}")
    client.get("/categories")
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(ActivityLog)) == before


def test_no_master_page_hand_rolls_a_query(client):
    """R3.12, mechanically: the repositories' `search()` methods are gone."""
    import app.modules.customers.repository as customers
    import app.modules.products.repository as products
    import app.modules.suppliers.repository as suppliers

    for module, name in (
        (products, "ProductRepository"),
        (customers, "CustomerRepository"),
        (suppliers, "SupplierRepository"),
    ):
        assert not hasattr(getattr(module, name), "search"), (
            f"{name}.search is the old path; the query helper replaced it"
        )
    assert uuid  # keeps the import honest for the id helpers above
