"""Part 7 C2c — fast order entry (R9.12–R9.14).

R9.12's acceptance is a manual walkthrough, so these test the things a walkthrough cannot
check reliably: that the picker really carries price and AVAILABLE stock, that reorder-from-
last-order reproduces the right lines at the right prices, that the SKU grid resolves through
the ONE shared resolver, and that the form is reachable by keyboard without tabbing the nav.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.sales.fast_entry import FastEntryService


@pytest.fixture()
def customer_with_history(db):
    """A customer the seed has already given an order. READ-ONLY uses only."""
    from app.modules.customers.models import Customer

    repeatable = FastEntryService(db).customers_with_history()
    assert repeatable, "the seed has no customer with an order"
    customer_id = next(iter(repeatable))
    return db.get(Customer, customer_id)


@pytest.fixture()
def spare_customer(db):
    """A customer no other test makes assertions about — for tests that POST.

    **A `client.post` commits through the app's own session, so the rows it writes OUTLIVE
    the test**; the `db` fixture's rollback does not touch them. Creating a draft order on
    the first customer therefore leaves it permanently "open", which breaks the Part 1/3
    tests asserting that customer's work is all closed. This picks one from the far end of
    the list instead. The same trap caught Parts 6 and 7 C1 through the seed.
    """
    from app.modules.customers.models import Customer

    return db.scalar(
        select(Customer)
        .where(Customer.deleted_at.is_(None))
        .order_by(Customer.code.desc())
        .limit(1)
    )


# --- R9.12: the picker carries price and availability ------------------------


def test_r9_12_the_picker_hints_show_price_and_available_stock(db):
    from app.modules.products.service import ProductService

    products, _ = ProductService(db).list(
        search=None, category_id=None, page=1, page_size=40
    )
    hints = FastEntryService(db).picker_hints(products)

    assert hints, "no hints produced"
    assert set(hints) <= {p.sku_code for p in products}
    # Every hint names availability, and a priced product names its price.
    assert all("available" in h for h in hints.values())
    priced = [h for h in hints.values() if "no price" not in h]
    assert priced, "no product carried a price"
    assert any("." in h for h in priced), "prices are not rendered as money"


def test_r9_12_the_hint_reports_available_not_on_hand(db):
    """Now that confirming an order reserves stock, the two differ — and offering on-hand
    would promise stock already committed to somebody else."""
    from app.modules.inventory.schemas import ReservationCreate
    from app.modules.inventory.service import InventoryService, ReservationService

    inventory = InventoryService(db)
    stocked = next(r for r in inventory.stock() if r.qty_on_hand >= 20)

    fast = FastEntryService(db)
    before = fast.available_by_product()[stocked.product_id]

    ReservationService(db).reserve(
        ReservationCreate(
            product_id=stocked.product_id,
            warehouse_id=stocked.warehouse_id,
            qty=Decimal("7"),
        ),
        actor_id=None,
    )

    after = fast.available_by_product()[stocked.product_id]
    assert after == before - Decimal("7"), (
        "the picker's availability ignored a reservation — it is reporting on-hand"
    )


def test_r9_12_a_product_with_nothing_available_says_so_rather_than_showing_blank(db):
    from app.modules.products.models import Product

    # A product the seed never stocked has nothing available.
    never_stocked = db.scalars(
        select(Product).where(Product.deleted_at.is_(None)).order_by(Product.sku_code)
    ).all()
    hints = FastEntryService(db).picker_hints(never_stocked[:60])
    assert any("none available" in h for h in hints.values()), (
        "a product with no stock should say so, not render an empty hint"
    )


def test_r9_12_the_hints_are_bulk_reads_not_one_query_per_product(db):
    """300 products on the form; a per-product query would be 300 round trips to render ONE
    page — the failure CODEBASE-MAP warns about under "a select() per row in a projector".

    This COUNTS the statements rather than grepping the source. A text match cannot tell a
    call from a mention, and the first version of this test failed on its own docstring.
    """
    from sqlalchemy import event

    from app.modules.products.service import ProductService

    products, _ = ProductService(db).list(
        search=None, category_id=None, page=1, page_size=120
    )
    assert len(products) >= 100, "too few products for this to prove anything"

    statements: list[str] = []

    def record(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        hints = FastEntryService(db).picker_hints(products)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)

    assert len(hints) == len(products)
    # A handful of grouped reads, nowhere near one per product.
    assert len(statements) < 10, (
        f"{len(statements)} queries for {len(products)} products — this is per-row"
    )


# --- R9.12: reorder from last order -----------------------------------------


def test_r9_12_last_order_lines_reproduce_the_previous_order(db, customer_with_history):
    fast = FastEntryService(db)
    lines = fast.last_order_lines(customer_with_history.id)

    assert lines, "the customer has an order but no lines came back"
    for sku, qty, price in lines:
        assert isinstance(sku, str) and sku
        assert qty > 0
        assert price > 0


def test_r9_12_last_order_uses_the_most_recent_order(db, customer_with_history):
    """And deterministically: several seeded orders share a date, and uuid7 cannot break a
    same-millisecond tie, so the ordering carries `id` as a second key."""
    from app.modules.products.models import Product
    from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate
    from app.modules.sales.service import SalesOrderService

    product = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    SalesOrderService(db).create(
        SalesOrderCreate(
            customer_id=customer_with_history.id,
            lines=[
                SalesOrderLineCreate(
                    product_id=product.id, qty=Decimal("9"), unit_price_minor=1234_00
                )
            ],
        ),
        actor_id=None,
    )

    fast = FastEntryService(db)
    lines = fast.last_order_lines(customer_with_history.id)
    assert lines == [(product.sku_code, Decimal("9"), 1234_00)]
    # Same answer twice: the ordering is not left to the query planner.
    assert fast.last_order_lines(customer_with_history.id) == lines


def test_r9_12_a_cancelled_order_is_not_what_last_order_means(db, customer_with_history):
    from app.modules.products.models import Product
    from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate
    from app.modules.sales.service import SalesOrderService

    svc = SalesOrderService(db)
    fast = FastEntryService(db)
    before = fast.last_order_lines(customer_with_history.id)

    product = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    cancelled = svc.create(
        SalesOrderCreate(
            customer_id=customer_with_history.id,
            lines=[
                SalesOrderLineCreate(
                    product_id=product.id, qty=Decimal("99"), unit_price_minor=1_00
                )
            ],
        ),
        actor_id=None,
    )
    svc.cancel(cancelled.id, reason="Called off", actor_id=None)

    assert fast.last_order_lines(customer_with_history.id) == before, (
        "repeating a cancelled order is not what 'last order' means"
    )


def test_r9_12_a_customer_with_no_orders_has_nothing_to_repeat(db):
    from app.modules.config.models import CustomerType
    from app.modules.customers.schemas import CustomerCreate
    from app.modules.customers.service import CustomerService

    ctype = db.scalar(select(CustomerType).where(CustomerType.deleted_at.is_(None)))
    fresh = CustomerService(db).create(
        CustomerCreate(
            name=f"No History {uuid.uuid4().hex[:6]}", customer_type_id=ctype.id, city="Pune"
        ),
        actor_id=None,
    )

    fast = FastEntryService(db)
    assert fast.last_order_lines(fresh.id) == []
    assert fresh.id not in fast.customers_with_history()


# --- the screen --------------------------------------------------------------


def test_r9_12_the_form_is_keyboard_first(client):
    html = client.get("/sales/new").text

    # AUTOFOCUS is the single biggest saving: without it the founder tabs past 19 sidebar
    # links before reaching the first field.
    assert "autofocus" in html
    # The 311-option <select> per row is gone, replaced by the typed picker.
    assert 'list="product-options"' in html
    assert '<datalist id="product-options">' in html
    assert 'name="product_code"' in html
    assert 'name="product_id"' not in html, "the untypable per-row select is still there"


def test_r9_12_the_form_shows_price_and_availability_in_the_picker(client):
    html = client.get("/sales/new").text
    assert "available" in html
    # And it says which figure it is showing, because on-hand and available now differ.
    assert "Available, not on hand" in html or "available to sell" in html


def test_r9_14_the_form_offers_several_blank_rows(client):
    html = client.get("/sales/new").text
    assert html.count('name="product_code"') >= 8, "bulk entry needs several rows"
    assert "Leave rows blank to skip them" in html


def test_r9_12_the_repeat_action_prefills_the_previous_order(client, db, customer_with_history):
    lines = FastEntryService(db).last_order_lines(customer_with_history.id)
    assert lines

    html = client.get(
        f"/sales/new?customer_id={customer_with_history.id}&repeat=1"
    ).text

    # Each SKU from the last order is prefilled into a row.
    for sku, _qty, _price in lines:
        assert f'value="{sku}"' in html, f"{sku} was not prefilled"
    assert "loaded from their last order" in html
    # And the customer is preselected, so the founder does not re-pick them.
    assert f'value="{customer_with_history.id}" selected' in html


def test_r9_12_repeatable_customers_are_marked_in_the_one_picker(client, db):
    """ONE customer field, not two. A second picker for "repeat" would be a second thing to
    keep in step, and the founder would have to know which one they were in."""
    html = client.get("/sales/new").text

    assert html.count('name="customer_id"') == 1, "there should be exactly one customer field"
    assert "marks a customer with a previous order" in html
    # The repeat action reuses the SAME form, submitted as a GET.
    assert 'formmethod="get"' in html
    assert 'formaction="/sales/new"' in html

    repeatable = FastEntryService(db).customers_with_history()
    assert repeatable
    assert html.count("↺") >= len(repeatable), "repeatable customers are not marked"


def test_r9_12_an_order_can_be_created_through_the_typed_grid(client, db, spare_customer):
    """The whole point: SKUs typed, not picked from a 311-option select."""
    from app.modules.products.models import Product

    product = db.scalar(select(Product).where(Product.deleted_at.is_(None)))

    created = client.post(
        "/sales",
        data={
            "customer_id": str(spare_customer.id),
            "product_code": [product.sku_code, "", ""],
            "qty": ["3", "", ""],
            "unit_price_rupees": ["150.50", "", ""],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert "/sales/" in created.headers["location"]


def test_r9_12_an_unknown_sku_is_named_back_rather_than_dropped(client, spare_customer):
    """The one failure a free-text picker must not have. Part 3's resolver already does
    this; reusing it means the sales form inherits the behaviour rather than re-earning it."""
    response = client.post(
        "/sales",
        data={
            "customer_id": str(spare_customer.id),
            "product_code": ["NOT-A-REAL-SKU"],
            "qty": ["1"],
            "unit_price_rupees": [""],
        },
        follow_redirects=False,
    )
    # Post/Redirect/Get with a flash, not a silently smaller order.
    assert response.status_code == 303
    assert "/sales/new" in response.headers["location"]


def test_r9_12_blank_rows_do_not_shift_the_prices(client, db, spare_customer):
    """A blank row in the MIDDLE must not slide every following price up a line — the
    resolver skips blanks, so the price list has to be indexed against the rows it kept."""
    from app.modules.products.models import Product
    from app.modules.sales.models import SalesOrder

    products = db.scalars(
        select(Product).where(Product.deleted_at.is_(None)).order_by(Product.sku_code).limit(2)
    ).all()

    created = client.post(
        "/sales",
        data={
            "customer_id": str(spare_customer.id),
            # blank row deliberately between the two real ones
            "product_code": [products[0].sku_code, "", products[1].sku_code],
            "qty": ["2", "", "5"],
            "unit_price_rupees": ["100.00", "", "300.00"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    order_id = created.headers["location"].split("/sales/")[1].split("?")[0]
    order = db.get(SalesOrder, uuid.UUID(order_id))

    by_product = {ln.product_id: ln.unit_price_minor for ln in order.lines}
    assert by_product[products[0].id] == 100_00
    assert by_product[products[1].id] == 300_00, (
        "the blank row shifted the price onto the wrong line"
    )


def test_r9_12_no_second_sku_resolver_was_written(db):
    """G16 — the sales form reuses Part 3's `_lines`, it does not reimplement SKU lookup."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "app" / "web" / "pages" / "sales.py"
    ).read_text(encoding="utf-8")
    assert "resolve_sku_lines" in src
    assert "from app.web.pages.preorder import _lines" in src
    # No local SKU->id query of its own.
    assert "Product.sku_code ==" not in src
