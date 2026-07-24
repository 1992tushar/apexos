"""Service-level tests for CustomerService: create, read projection, update, conflict."""
from __future__ import annotations

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.modules.config.service import ConfigService
from app.modules.customers.schemas import CustomerCreate, CustomerUpdate
from app.modules.customers.service import CustomerService


def _a_customer_type_id(db):
    return ConfigService(db).customer_types()[0].id


def test_create_autogenerates_code_and_sets_defaults(db):
    svc = CustomerService(db)
    c = svc.create(
        CustomerCreate(name="Test Diner", customer_type_id=_a_customer_type_id(db),
                       credit_limit_minor=500000, payment_terms_days=15),
        actor_id=None,
    )
    assert c.code.startswith("CUST-")
    assert c.status == "active"
    assert c.credit_limit_minor == 500000
    assert c.outstanding_minor == 0  # brand-new customer owes nothing


def test_duplicate_code_raises_conflict(db):
    svc = CustomerService(db)
    ct = _a_customer_type_id(db)
    first = svc.create(CustomerCreate(name="Dup Co", customer_type_id=ct), actor_id=None)
    with pytest.raises(ConflictError):
        svc.create(
            CustomerCreate(code=first.code, name="Dup Co 2", customer_type_id=ct), actor_id=None
        )


def test_update_changes_fields_and_credit_policy(db):
    svc = CustomerService(db)
    c = svc.create(
        CustomerCreate(name="Before", customer_type_id=_a_customer_type_id(db)), actor_id=None
    )
    updated = svc.update(
        c.id, CustomerUpdate(name="After", credit_limit_minor=999900), actor_id=None
    )
    assert updated.name == "After"
    assert updated.credit_limit_minor == 999900


def test_get_missing_raises_not_found(db):
    import uuid

    with pytest.raises(NotFoundError):
        CustomerService(db).get(uuid.uuid4())
