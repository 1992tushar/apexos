"""The one duplicate-prevention mechanism (R2.9, R2.15).

The requirement is specific about the failure mode it exists to prevent: a
duplicate must come back as a clean field-level error, not an `IntegrityError`
and not a 500. So these assert on the *shape* of the refusal — which field it
blames, what it says — as much as on the fact of it.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError, DuplicateError
from app.db.duplicates import NATURAL_KEYS, ensure_unique, find_duplicate, natural_keys_for
from app.db.soft_delete import soft_delete
from app.modules.config.service import ConfigService
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import CustomerService
from app.modules.products.models import Product
from app.modules.products.schemas import ProductCreate
from app.modules.products.service import ProductService


def _a_customer_type(db):
    return ConfigService(db).customer_types()[0].id


def _product_payload(db, **overrides) -> ProductCreate:
    cfg = ConfigService(db)
    base = {
        "name": "Unique Mop",
        "category_id": cfg.categories()[0].id,
        "brand_id": cfg.brands()[0].id,
        "uom_id": cfg.uoms()[0].id,
    }
    base.update(overrides)
    return ProductCreate(**base)


# --- the mechanism ----------------------------------------------------------

def test_natural_keys_are_configuration_not_code(db):
    # R2.9: "applied per entity via configuration". Adding a master is a dict entry.
    assert natural_keys_for(Product), "product must declare a natural key"
    assert natural_keys_for(Customer), "customer must declare a natural key"
    assert all(key.fields for keys in NATURAL_KEYS.values() for key in keys)


def test_a_free_key_passes_silently(db):
    ensure_unique(db, Product, {"sku_code": f"SKU-FREE-{uuid.uuid4().hex[:8]}"})


def test_an_incomplete_composite_key_cannot_collide(db):
    # Two products with no specification are not thereby duplicates of each other.
    existing = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    ensure_unique(
        db,
        Product,
        {
            "sku_code": f"SKU-FREE-{uuid.uuid4().hex[:8]}",
            "name": existing.name,
            "specification": None,
            "brand_id": existing.brand_id,
        },
    )


def test_a_row_is_not_a_duplicate_of_itself(db):
    existing = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    values = {
        "sku_code": existing.sku_code,
        "name": existing.name,
        "specification": existing.specification,
        "brand_id": existing.brand_id,
    }
    with pytest.raises(DuplicateError):
        ensure_unique(db, Product, values)
    ensure_unique(db, Product, values, exclude_id=existing.id)  # the update case


def test_the_error_blames_a_field_and_reads_like_a_sentence(db):
    existing = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    with pytest.raises(DuplicateError) as exc:
        ensure_unique(db, Product, {"sku_code": existing.sku_code})

    err = exc.value
    assert err.field == "sku_code"
    assert err.details == {"field": "sku_code", "value": existing.sku_code}
    assert err.code == "duplicate"
    assert err.status_code == 409
    assert existing.sku_code in err.message
    assert err.message.endswith(".")
    assert "IntegrityError" not in err.message and "UNIQUE" not in err.message


def test_a_duplicate_error_is_still_a_conflict(db):
    # Existing callers catch ConflictError; DuplicateError must not escape them.
    existing = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    with pytest.raises(ConflictError):
        ensure_unique(db, Product, {"sku_code": existing.sku_code})


def test_matching_is_case_insensitive(db):
    existing = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    with pytest.raises(DuplicateError):
        ensure_unique(db, Product, {"sku_code": existing.sku_code.lower()})


def test_a_composite_key_needs_every_field_to_match(db):
    existing = db.scalar(select(Product).where(Product.name == "Toilet Roll"))
    same = {
        "name": existing.name,
        "specification": existing.specification,
        "brand_id": existing.brand_id,
    }
    with pytest.raises(DuplicateError) as exc:
        ensure_unique(db, Product, same)
    assert exc.value.field == "name"  # the composite key blames the field a form has

    ensure_unique(db, Product, {**same, "specification": "A Spec Nobody Used"})


# --- the soft-delete interaction (the bug this design exists to avoid) ------

def test_a_db_backed_key_still_collides_with_a_deleted_row(db):
    """A UNIQUE column outlives the row's deletion, so the check must see it.

    If `ensure_unique` filtered deleted rows out here it would pass, and the flush
    would then raise the IntegrityError R2.9 forbids.
    """
    victim = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    sku = victim.sku_code
    soft_delete(db, victim, actor_id=None, label="Product")

    with pytest.raises(DuplicateError) as exc:
        ensure_unique(db, Product, {"sku_code": sku})
    assert "deleted" in exc.value.message.lower()
    assert sku in exc.value.message


def test_a_key_with_no_constraint_ignores_deleted_rows(db):
    """The composite key promises nothing about deleted rows, so it frees them."""
    victim = db.scalar(select(Product).where(Product.name == "Toilet Roll"))
    values = {
        "name": victim.name,
        "specification": victim.specification,
        "brand_id": victim.brand_id,
    }
    # Two rows share the name; delete both so nothing live holds the key.
    for row in db.scalars(
        select(Product).where(
            Product.name == values["name"],
            Product.specification == values["specification"],
            Product.brand_id == values["brand_id"],
            Product.deleted_at.is_(None),
        )
    ).all():
        soft_delete(db, row, actor_id=None, label="Product")

    assert find_duplicate(db, Product, values) is None


# --- through the services (the real call sites) -----------------------------

def test_product_create_rejects_a_duplicate_sku_without_an_integrity_error(db):
    existing = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    with pytest.raises(DuplicateError) as exc:
        ProductService(db).create(
            _product_payload(db, sku_code=existing.sku_code), actor_id=None
        )
    assert exc.value.field == "sku_code"


def test_product_create_rejects_the_same_thing_twice(db):
    svc = ProductService(db)
    payload = _product_payload(db, name="Mop Of Record", specification="Wide")
    svc.create(payload, actor_id=None)
    with pytest.raises(DuplicateError) as exc:
        svc.create(_product_payload(db, name="Mop Of Record", specification="Wide"), actor_id=None)
    assert exc.value.field == "name"


def test_a_generated_sku_survives_a_deletion(db):
    """The generator counts every row ever created, so a delete cannot recycle a code."""
    svc = ProductService(db)
    first = svc.create(_product_payload(db, name="Generated One"), actor_id=None)
    svc.delete(first.id, actor_id=None)
    second = svc.create(_product_payload(db, name="Generated Two"), actor_id=None)
    assert second.sku_code != first.sku_code


def test_customer_create_rejects_a_duplicate_code(db):
    svc = CustomerService(db)
    ct = _a_customer_type(db)
    first = svc.create(CustomerCreate(name="Original Co", customer_type_id=ct), actor_id=None)
    with pytest.raises(DuplicateError) as exc:
        svc.create(
            CustomerCreate(code=first.code, name="Impostor Co", customer_type_id=ct),
            actor_id=None,
        )
    assert exc.value.field == "code"


def test_customer_create_rejects_the_same_name_in_the_same_city(db):
    svc = CustomerService(db)
    ct = _a_customer_type(db)
    svc.create(
        CustomerCreate(name="Twin Cafe", customer_type_id=ct, city="Pune"), actor_id=None
    )
    with pytest.raises(DuplicateError) as exc:
        svc.create(
            CustomerCreate(name="twin cafe", customer_type_id=ct, city="pune"), actor_id=None
        )
    assert exc.value.field == "name"

    # The same name in another city is a different branch, not a duplicate.
    svc.create(
        CustomerCreate(name="Twin Cafe", customer_type_id=ct, city="Mumbai"), actor_id=None
    )


def test_customer_update_cannot_rename_onto_another_record(db):
    from app.modules.customers.schemas import CustomerUpdate

    svc = CustomerService(db)
    ct = _a_customer_type(db)
    svc.create(CustomerCreate(name="Alpha Ltd", customer_type_id=ct, city="Nashik"), actor_id=None)
    beta = svc.create(
        CustomerCreate(name="Beta Ltd", customer_type_id=ct, city="Nashik"), actor_id=None
    )

    with pytest.raises(DuplicateError):
        svc.update(beta.id, CustomerUpdate(name="Alpha Ltd"), actor_id=None)

    # Editing something else on the same record is unaffected (no self-collision).
    assert svc.update(beta.id, CustomerUpdate(phone="9999999999"), actor_id=None).name == "Beta Ltd"


def test_no_duplicate_reaches_the_database_as_an_integrity_error(db):
    """The pre-save check fires first, so a flush never sees the collision."""
    existing = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    try:
        ProductService(db).create(_product_payload(db, sku_code=existing.sku_code), actor_id=None)
    except DuplicateError:
        pass
    except IntegrityError:  # pragma: no cover - the failure this test exists to catch
        pytest.fail("the duplicate reached the database instead of the pre-save check")
