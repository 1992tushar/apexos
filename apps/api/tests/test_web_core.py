"""`app.web.core.form_action` — the one shared POST-handling helper every web form
uses. A single behaviour is under test: what message reaches the flash on failure.

Found by reproducing a real bug report: submitting a sales-order line with an explicit
`qty=0` (not blank — the blank-row filter only skips *empty* fields) fails
`SalesOrderLineCreate`'s `Field(gt=0)`, raising a bare `pydantic.ValidationError`.
`pydantic.ValidationError` has no `.message` attribute (only `AppError` does), so
`form_action` fell back to its generic `err=` text for every Pydantic failure on every
form in the app — the founder saw "Could not create order" with no hint which field or
row was wrong, and nothing was logged server-side either.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.errors import ValidationError
from app.web.core import form_action


class _Line(BaseModel):
    qty: int = Field(gt=0)


class _FakeDb:
    def rollback(self) -> None:
        pass


_FALLBACK = "Could not create order"


def _location(response) -> str:
    return response.headers["location"]


def test_a_pydantic_validation_failure_names_the_field_instead_of_the_generic_fallback():
    def work():
        _Line(qty=0)

    resp = form_action(_FakeDb(), work, back="/sales/new", success=("/x", "ok"), err=_FALLBACK)
    location = _location(resp)
    assert "Could+not+create+order" not in location
    assert "qty" in location


def test_an_app_error_still_surfaces_its_own_message_unchanged():
    def work():
        raise ValidationError("No selling price for product SKU-1")

    resp = form_action(_FakeDb(), work, back="/sales/new", success=("/x", "ok"), err="fallback")
    assert "No+selling+price+for+product+SKU-1" in _location(resp)


def test_a_bare_value_error_still_falls_back_to_the_caller_supplied_message():
    def work():
        raise ValueError("some internal parsing detail")

    resp = form_action(_FakeDb(), work, back="/sales/new", success=("/x", "ok"), err=_FALLBACK)
    assert "Could+not+create+order" in _location(resp)


def test_qty_zero_on_a_sales_order_line_names_the_row_not_a_generic_failure(client):
    """End to end: the exact reported symptom, reproduced through the real route."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.modules.customers.models import Customer
    from app.modules.products.models import Product

    db = SessionLocal()
    try:
        customer = db.scalar(select(Customer).where(Customer.deleted_at.is_(None)).limit(1))
        product = db.scalar(select(Product).where(Product.deleted_at.is_(None)).limit(1))
        customer_id, sku = str(customer.id), product.sku_code
    finally:
        db.close()

    resp = client.post(
        "/sales",
        data={
            "customer_id": customer_id,
            "order_date": "",
            "product_code": [sku],
            "qty": ["0"],
            "unit_price_rupees": [""],
        },
        follow_redirects=False,
    )
    location = resp.headers["location"]
    assert "Could+not+create+order" not in location, (
        "the generic fallback gives the founder no way to know qty=0 was the problem"
    )
    assert "qty" in location.lower()
