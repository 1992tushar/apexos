"""Change history derived from `activity_log` — no new table (R2.10, R2.15).

The requirement allows a dedicated history table only if `activity_log` provably
cannot answer "what changed on this record, when, by whom". These tests are that
proof: each of the three questions is answered off the log, including field-level
before/after via the `data` JSON column that already existed.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.db.metadata import Base
from app.modules.activity.history import CHANGES_KEY, field_changes
from app.modules.activity.models import ActivityLog
from app.modules.activity.service import ActivityService
from app.modules.config.service import ConfigService
from app.modules.customers.schemas import CustomerCreate, CustomerUpdate
from app.modules.customers.service import CustomerService
from app.modules.identity.models import User


def _a_customer_type(db):
    return ConfigService(db).customer_types()[0].id


def _a_customer(db, **overrides):
    payload = {
        "name": f"History Co {uuid.uuid4().hex[:6]}",
        "customer_type_id": _a_customer_type(db),
    }
    payload.update(overrides)
    return CustomerService(db).create(CustomerCreate(**payload), actor_id=None)


# --- no new table (R2.10) ---------------------------------------------------

def test_history_uses_the_activity_log_and_nothing_else():
    tables = set(Base.metadata.tables)
    assert "activity_log" in tables
    assert not [
        t
        for t in tables
        if "history" in t or t.endswith("_audit") or t.endswith("_version")
    ]


def test_the_log_can_answer_all_three_questions(db):
    columns = {c.name for c in ActivityLog.__table__.columns}
    assert {"entity_type", "entity_id"} <= columns  # which record
    assert {"verb", "summary", "data"} <= columns  # what changed
    assert "occurred_at" in columns  # when
    assert "actor_id" in columns  # by whom


# --- the diff helper --------------------------------------------------------

def test_field_changes_records_only_what_actually_changed(db):
    customer = CustomerService(db).repo.get(_a_customer(db, name="Before Co", city="Pune").id)
    changes = field_changes(customer, {"name": "After Co", "city": "Pune"})
    assert changes == {"name": {"from": "Before Co", "to": "After Co"}}


def test_field_changes_ignores_names_the_model_does_not_have(db):
    customer = CustomerService(db).repo.get(_a_customer(db).id)
    assert field_changes(customer, {"not_a_column": "x"}) == {}


def test_field_changes_output_is_json_safe(db):
    import json

    customer = CustomerService(db).repo.get(_a_customer(db).id)
    changes = field_changes(
        customer,
        {
            "customer_type_id": uuid.uuid4(),  # UUID
            "created_at": None,  # datetime -> None
            "name": "New Name",
        },
    )
    # The `data` column is JSON; anything not serialisable would fail at flush.
    assert json.loads(json.dumps(changes))
    assert isinstance(changes["customer_type_id"]["to"], str)
    assert isinstance(changes["created_at"]["from"], str)


def test_field_changes_stringifies_decimals_without_losing_precision(db):
    holder = type("H", (), {"qty": Decimal("1.2500")})()
    assert field_changes(holder, {"qty": Decimal("2")}) == {
        "qty": {"from": "1.2500", "to": "2"}
    }


# --- the read side ----------------------------------------------------------

def test_history_reports_the_create_then_the_update_newest_first(db):
    svc = CustomerService(db)
    customer = _a_customer(db, name="Timeline Co", city="Pune")
    svc.update(customer.id, CustomerUpdate(name="Timeline Renamed"), actor_id=None)

    entries = ActivityService(db).history("customer", customer.id)
    assert [e.verb for e in entries] == ["updated", "created"]
    assert "Timeline" in entries[-1].summary


def test_history_carries_field_level_before_and_after(db):
    svc = CustomerService(db)
    customer = _a_customer(db, name="Detail Co", city="Pune")
    svc.update(
        customer.id,
        CustomerUpdate(name="Detail Renamed", city="Mumbai", credit_limit_minor=500000),
        actor_id=None,
    )

    latest = ActivityService(db).history("customer", customer.id)[0]
    changed = {c.field: (c.before, c.after) for c in latest.changes}
    assert changed["name"] == ("Detail Co", "Detail Renamed")
    assert changed["city"] == ("Pune", "Mumbai")
    # A `*_minor` field reads as rupees, not paise, and never via a float (G1).
    assert changed["credit_limit_minor"] == ("0.00", "5000.00")
    labels = {c.field: c.label for c in latest.changes}
    assert labels["credit_limit_minor"] == "Credit limit (₹)"
    assert labels["city"] == "City"


def test_an_update_that_changes_nothing_records_no_field_changes(db):
    svc = CustomerService(db)
    customer = _a_customer(db, name="Idle Co", city="Pune")
    svc.update(customer.id, CustomerUpdate(name="Idle Co", city="Pune"), actor_id=None)

    latest = ActivityService(db).history("customer", customer.id)[0]
    assert latest.verb == "updated"  # the verb still logs (G5)
    assert latest.changes == ()  # but it does not invent a diff


def test_history_names_who_did_it(db):
    founder = db.scalar(select(User).where(User.email == "founder@apexsupply.example"))
    svc = CustomerService(db)
    customer = svc.create(
        CustomerCreate(name=f"Attributed Co {uuid.uuid4().hex[:6]}",
                       customer_type_id=_a_customer_type(db)),
        actor_id=founder.id,
    )
    assert ActivityService(db).history("customer", customer.id)[0].actor == founder.full_name


def test_an_unresolvable_actor_says_so_rather_than_guessing(db):
    svc = CustomerService(db)
    ghost = uuid.uuid4()
    customer = svc.create(
        CustomerCreate(name=f"Ghost Co {uuid.uuid4().hex[:6]}",
                       customer_type_id=_a_customer_type(db)),
        actor_id=ghost,
    )
    entries = ActivityService(db).history("customer", customer.id)
    assert entries[0].actor == "Unknown user"

    unattributed = _a_customer(db)  # actor_id=None
    assert ActivityService(db).history("customer", unattributed.id)[0].actor == "System"


def test_history_of_a_record_with_no_events_is_empty(db):
    assert ActivityService(db).history("customer", uuid.uuid4()) == []


def test_history_is_scoped_to_the_one_record(db):
    a = _a_customer(db, name="Scope A")
    b = _a_customer(db, name="Scope B")
    entries = ActivityService(db).history("customer", a.id)
    assert len(entries) == 1
    assert "Scope A" in entries[0].summary
    assert all("Scope B" not in e.summary for e in entries)
    assert b.id != a.id


def test_reading_history_writes_nothing(db):
    """G15: a projection layer owns no entities and leaves no trace."""
    customer = _a_customer(db)
    before = db.scalar(select(func.count()).select_from(ActivityLog))

    ActivityService(db).history("customer", customer.id)

    assert db.scalar(select(func.count()).select_from(ActivityLog)) == before


def test_the_update_verb_still_writes_exactly_one_row(db):
    """The diff rides on the existing row; it does not add a second one (G5)."""
    svc = CustomerService(db)
    customer = _a_customer(db, name="One Row Co", city="Pune")
    before = db.scalar(
        select(func.count()).select_from(ActivityLog).where(ActivityLog.entity_id == customer.id)
    )

    svc.update(customer.id, CustomerUpdate(name="One Row Renamed"), actor_id=None)

    after = db.scalar(
        select(func.count()).select_from(ActivityLog).where(ActivityLog.entity_id == customer.id)
    )
    assert after - before == 1


def test_the_diff_is_stored_under_its_own_key_in_data(db):
    """`data` stays open to other per-verb payloads."""
    svc = CustomerService(db)
    customer = _a_customer(db, name="Keyed Co")
    svc.update(customer.id, CustomerUpdate(name="Keyed Renamed"), actor_id=None)

    row = db.scalar(
        select(ActivityLog)
        .where(ActivityLog.entity_id == customer.id, ActivityLog.verb == "updated")
        .order_by(ActivityLog.id.desc())
    )
    assert set(row.data) == {CHANGES_KEY}
    assert row.data[CHANGES_KEY]["name"] == {"from": "Keyed Co", "to": "Keyed Renamed"}
