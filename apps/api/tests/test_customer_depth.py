"""Part 6 — customer depth: profile, versioned terms, the credit gate, the timeline (R8.x).

Each test builds its own customer so nothing depends on the seed's balances, and the money
assertions are on integer minor units throughout — the credit boundary is an integer
comparison and a float has no business near it (G1/R8.9).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, ValidationError
from app.modules.activity.models import ActivityLog
from app.modules.customers.credit import CreditPolicyService
from app.modules.customers.models import CustomerAddress, CustomerContact
from app.modules.customers.schemas import (
    BranchUpsert,
    ContactUpsert,
    CreditPolicySet,
    CustomerCreate,
    NoteCreate,
)
from app.modules.customers.service import CustomerService
from app.modules.customers.timeline import CustomerTimelineService


@pytest.fixture()
def customer(db):
    """A customer of this test's own, with no credit limit and no history."""
    from app.modules.config.models import CustomerType

    ctype = db.scalar(select(CustomerType).where(CustomerType.deleted_at.is_(None)))
    return CustomerService(db).create(
        CustomerCreate(
            name=f"Depth Co {uuid.uuid4().hex[:6]}",
            customer_type_id=ctype.id,
            city="Pune",
            credit_limit_minor=0,
            payment_terms_days=30,
        ),
        actor_id=None,
    )


def _activity_rows(db, customer_id) -> int:
    return db.scalar(
        select(func.count()).select_from(ActivityLog).where(
            ActivityLog.entity_type == "customer", ActivityLog.entity_id == customer_id
        )
    ) or 0


# --- R8.1 / R8.2 / R8.5: profile depth ---------------------------------------


def test_r8_1_a_customer_supports_multiple_contacts(db, customer):
    svc = CustomerService(db)
    svc.add_contact(customer.id, ContactUpsert(name="Asha Rao", designation="Owner"), actor_id=None)
    svc.add_contact(
        customer.id, ContactUpsert(name="Bharat Shah", designation="Accounts"), actor_id=None
    )

    contacts = svc.contacts(customer.id)
    assert {c.name for c in contacts} == {"Asha Rao", "Bharat Shah"}


def test_r8_1_only_one_contact_is_primary(db, customer):
    """Two "primary" contacts is not a state anyone can act on — the same exclusivity
    R5.1 gave the preferred supplier."""
    svc = CustomerService(db)
    first = svc.add_contact(
        customer.id, ContactUpsert(name="First", is_primary=True), actor_id=None
    )
    svc.add_contact(customer.id, ContactUpsert(name="Second", is_primary=True), actor_id=None)

    primaries = [c for c in svc.contacts(customer.id) if c.is_primary]
    assert len(primaries) == 1
    assert primaries[0].name == "Second"
    db.refresh(first)
    assert not first.is_primary


def test_r8_2_a_customer_supports_multiple_ship_to_branches(db, customer):
    svc = CustomerService(db)
    svc.add_branch(
        customer.id, BranchUpsert(line1="Plot 4", city="Pune", is_default=True), actor_id=None
    )
    svc.add_branch(customer.id, BranchUpsert(line1="Unit 9", city="Nashik"), actor_id=None)

    branches = svc.branches(customer.id)
    assert {b.city for b in branches} == {"Pune", "Nashik"}
    # Default first, which is the order the screen wants.
    assert branches[0].is_default
    # A branch is a SHIP-TO by default; the billing address lives on the customer.
    assert all(b.address_type == "shipping" for b in branches)


def test_r8_2_only_one_branch_is_default(db, customer):
    svc = CustomerService(db)
    svc.add_branch(
        customer.id, BranchUpsert(line1="A", city="Pune", is_default=True), actor_id=None
    )
    svc.add_branch(
        customer.id, BranchUpsert(line1="B", city="Mumbai", is_default=True), actor_id=None
    )

    assert len([b for b in svc.branches(customer.id) if b.is_default]) == 1


def test_r8_13_contacts_and_branches_retire_through_the_one_soft_delete_helper(db, customer):
    svc = CustomerService(db)
    contact = svc.add_contact(customer.id, ContactUpsert(name="Gone"), actor_id=None)
    branch = svc.add_branch(customer.id, BranchUpsert(line1="X", city="Pune"), actor_id=None)

    svc.delete_contact(contact.id, actor_id=None)
    svc.delete_branch(branch.id, actor_id=None)

    assert contact.id not in {c.id for c in svc.contacts(customer.id)}
    assert branch.id not in {b.id for b in svc.branches(customer.id)}
    # Soft, not hard: the row is still there, just filtered out (R1.1).
    assert db.get(CustomerContact, contact.id).deleted_at is not None
    assert db.get(CustomerAddress, branch.id).deleted_at is not None


def test_r8_5_notes_are_recordable_against_a_customer(db, customer):
    svc = CustomerService(db)
    svc.add_note(customer.id, NoteCreate(body="Prefers delivery before noon"), actor_id=None)
    svc.add_note(customer.id, NoteCreate(body="Asked about bulk pricing"), actor_id=None)

    notes = svc.notes(customer.id)
    assert len(notes) == 2
    # Newest first, and deterministic despite both rows sharing a func.now() timestamp.
    assert notes[0].body == "Asked about bulk pricing"


def test_r8_5_an_empty_note_is_refused(db, customer):
    with pytest.raises(ValidationError, match="needs something in it"):
        CustomerService(db).add_note(customer.id, NoteCreate(body="   "), actor_id=None)


def test_r8_4_documents_attach_through_the_existing_module(db, customer):
    """R8.4 — no second upload path. `Document` already keys on (entity_type, entity_id)."""
    from app.modules.documents.models import Document

    assert CustomerService(db).documents(customer.id) == []

    from app.modules.config.models import BusinessUnit

    bu = db.scalar(select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)))
    doc = Document(
        entity_type="customer",
        entity_id=customer.id,
        filename="agreement.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        category="contract",
        storage_backend="local",
        storage_key=f"customers/{customer.id}/agreement.pdf",
        business_unit_id=bu,
    )
    db.add(doc)
    db.flush()

    assert [d.id for d in CustomerService(db).documents(customer.id)] == [doc.id]


# --- R8.3: versioned credit terms --------------------------------------------


def test_r8_3_changing_credit_terms_appends_a_version_and_keeps_the_old_one(db, customer):
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id,
        CreditPolicySet(credit_limit_minor=500000, reason="Opening terms"),
        actor_id=None,
    )
    svc.set_policy(
        customer.id,
        CreditPolicySet(credit_limit_minor=800000, reason="Raised after 6 clean months"),
        actor_id=None,
    )

    history = svc.history(customer.id)
    assert len(history) == 3, "create wrote one version; two changes appended two more"
    # Newest first, exactly one current.
    assert history[0].credit_limit_minor == 800000
    assert history[0].is_current
    assert sum(1 for h in history if h.is_current) == 1
    # THE POINT OF VERSIONING: the prior limit is still readable (R8.3).
    assert history[1].credit_limit_minor == 500000
    assert history[1].valid_to is not None
    assert history[1].reason == "Opening terms"


def test_r8_3_a_version_carries_forward_what_the_caller_did_not_name(db, customer):
    """Setting a limit must not silently reset the payment terms to zero."""
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id,
        CreditPolicySet(credit_limit_minor=100000, payment_terms_days=45, reason="Agreed"),
        actor_id=None,
    )
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=200000, reason="Raised"), actor_id=None
    )

    current = svc.history(customer.id)[0]
    assert current.credit_limit_minor == 200000
    assert current.payment_terms_days == 45, "payment terms were lost on the new version"


def test_r8_3_a_terms_change_without_a_reason_is_refused(db, customer):
    with pytest.raises(ValidationError, match="needs a reason"):
        CreditPolicyService(db).set_policy(
            customer.id, CreditPolicySet(credit_limit_minor=1, reason="   "), actor_id=None
        )


# --- R8.6 / R8.7 / R8.9: the credit gate -------------------------------------


def test_r8_9_at_the_credit_limit_is_allowed(db, customer):
    """The boundary, exactly. Integer minor units, no float involved (G1)."""
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=100000, reason="Agreed"), actor_id=None
    )

    decision = svc.check(customer.id, 100000)
    assert decision.allowed
    assert decision.exposure_minor == 100000
    assert decision.shortfall_minor == 0


def test_r8_9_one_minor_unit_over_the_credit_limit_is_blocked(db, customer):
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=100000, reason="Agreed"), actor_id=None
    )

    decision = svc.check(customer.id, 100001)
    assert not decision.allowed
    assert decision.shortfall_minor == 1, "one paisa over must be short by exactly one paisa"


def test_r8_6_a_limit_of_zero_means_no_limit_not_refuse_everything(db, customer):
    """A customer with no terms recorded is cash-and-carry, not banned. Blocking every
    order for them would be a worse failure than allowing it."""
    decision = CreditPolicyService(db).check(customer.id, 99_999_999)
    assert decision.allowed
    assert decision.unlimited
    assert decision.shortfall_minor == 0


def test_r8_7_the_refusal_states_every_number(db, customer):
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=50000, reason="Agreed"), actor_id=None
    )
    decision = svc.check(customer.id, 70000)
    message = svc.refusal_message(decision)

    # R8.7's four numbers: limit, outstanding, this order, shortfall.
    assert "500.00" in message      # the limit
    assert "700.00" in message      # this order
    assert "200.00" in message      # short by
    assert "outstanding" in message
    # And it says what to do about it, rather than only that it failed.
    assert "override" in message.lower()


def test_r8_7_the_decision_renders_through_the_one_explanation_shape(db, customer):
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=50000, reason="Agreed"), actor_id=None
    )
    explained = svc.explain(svc.check(customer.id, 70000))

    assert explained.value == "over limit"
    labels = {i.label for i in explained.inputs}
    assert {"Credit limit", "Currently outstanding", "This order", "Short by"} <= labels
    assert explained.records[0].href == f"/customers/{customer.id}"


# --- R8.8: the override ------------------------------------------------------


def test_r8_8_an_override_without_a_reason_is_refused(db, customer):
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=1000, reason="Agreed"), actor_id=None
    )

    with pytest.raises(ConflictError, match="over their credit limit"):
        svc.enforce(customer.id, 5000, override_reason=None)
    with pytest.raises(ConflictError):
        svc.enforce(customer.id, 5000, override_reason="   ")


def test_r8_8_an_override_with_a_reason_writes_exactly_one_activity_row(db, customer):
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=1000, reason="Agreed"), actor_id=None
    )
    before = _activity_rows(db, customer.id)

    decision = svc.enforce(
        customer.id, 5000, override_reason="Long-standing customer, cheque in hand"
    )

    assert decision.overridden
    assert _activity_rows(db, customer.id) == before + 1, "exactly one row (G5)"

    latest = db.scalar(
        select(ActivityLog)
        .where(ActivityLog.entity_type == "customer", ActivityLog.entity_id == customer.id)
        .order_by(ActivityLog.occurred_at.desc(), ActivityLog.id.desc())
    )
    assert latest.verb == "overrode"
    # R8.8: who, when, by how much, and why.
    assert latest.data["over_by_minor"] == 4000
    assert latest.data["reason"] == "Long-standing customer, cheque in hand"
    assert "40.00" in latest.summary


def test_r8_8_a_passing_check_logs_nothing(db, customer):
    """Only an override is an event. A normal confirm must not litter the history."""
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=100000, reason="Agreed"), actor_id=None
    )
    before = _activity_rows(db, customer.id)

    svc.enforce(customer.id, 5000)
    assert _activity_rows(db, customer.id) == before


# --- R8.6 at the real call site: sales-order confirm --------------------------


def _an_order(db, customer_id, *, qty: str = "1"):
    from app.modules.products.models import Product
    from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate
    from app.modules.sales.service import SalesOrderService

    product = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    return SalesOrderService(db).create(
        SalesOrderCreate(
            customer_id=customer_id,
            lines=[SalesOrderLineCreate(product_id=product.id, qty=Decimal(qty))],
        ),
        actor_id=None,
    )


def test_r8_6_confirming_over_the_limit_is_blocked_and_leaves_the_order_in_draft(db, customer):
    from app.modules.sales.service import SalesOrderService

    order = _an_order(db, customer.id)
    CreditPolicyService(db).set_policy(
        customer.id,
        CreditPolicySet(credit_limit_minor=1, reason="Deliberately tiny for the test"),
        actor_id=None,
    )

    with pytest.raises(ConflictError, match="over their credit limit"):
        SalesOrderService(db).confirm(order.id, actor_id=None)

    # A refused confirm must not leave a half-changed order behind.
    from app.modules.sales.models import SalesOrder

    assert db.get(SalesOrder, order.id).status == "draft"


def test_r8_6_confirming_within_the_limit_still_works(db, customer):
    from app.modules.sales.service import SalesOrderService

    order = _an_order(db, customer.id)
    CreditPolicyService(db).set_policy(
        customer.id,
        CreditPolicySet(credit_limit_minor=99_000_000, reason="Generous"),
        actor_id=None,
    )

    detail = SalesOrderService(db).confirm(order.id, actor_id=None)
    assert detail.status == "confirmed"


def test_r8_8_confirming_with_an_override_reason_succeeds_and_is_logged(db, customer):
    from app.modules.sales.service import SalesOrderService

    order = _an_order(db, customer.id)
    CreditPolicyService(db).set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=1, reason="Tiny"), actor_id=None
    )
    before = _activity_rows(db, customer.id)

    detail = SalesOrderService(db).confirm(
        order.id, actor_id=None, credit_override_reason="Founder approved on the phone"
    )

    assert detail.status == "confirmed"
    # One row for the override, and it names the order it was for.
    assert _activity_rows(db, customer.id) == before + 1
    latest = db.scalar(
        select(ActivityLog)
        .where(ActivityLog.entity_type == "customer", ActivityLog.entity_id == customer.id)
        .order_by(ActivityLog.occurred_at.desc(), ActivityLog.id.desc())
    )
    assert order.order_no in latest.summary


# --- R8.10 / R8.11: the timeline ---------------------------------------------


def test_r8_11_a_customer_with_no_history_renders_an_empty_timeline(db, customer):
    """Empty, not an error and not a crash (R8.11)."""
    events = CustomerTimelineService(db).events(customer.id)
    # `create` logged one activity row, so the only entries are that — no orders, no money.
    assert all(e.kind == "activity" for e in events)
    assert not [e for e in events if e.kind in ("order", "invoice", "payment")]


def test_r8_10_the_timeline_gathers_every_source_type(db, customer):
    from app.modules.sales.service import SalesOrderService

    CreditPolicyService(db).set_policy(
        customer.id,
        CreditPolicySet(credit_limit_minor=99_000_000, reason="Generous"),
        actor_id=None,
    )
    order = _an_order(db, customer.id)
    SalesOrderService(db).confirm(order.id, actor_id=None)
    CustomerService(db).add_note(
        customer.id, NoteCreate(body="Called about delivery"), actor_id=None
    )

    events = CustomerTimelineService(db).events(customer.id)
    kinds = {e.kind for e in events}

    assert "order" in kinds, "the order is missing from the timeline"
    assert "note" in kinds, "the note is missing from the timeline"
    assert "activity" in kinds, "state changes are missing from the timeline"
    # The order carries its money and links back to itself.
    order_event = next(e for e in events if e.kind == "order")
    assert order_event.amount_minor == order.total_minor
    assert order_event.href == f"/sales/{order.id}"


def test_r8_10_the_timeline_is_strictly_chronological_and_deterministic(db, customer):
    from app.modules.sales.service import SalesOrderService

    CreditPolicyService(db).set_policy(
        customer.id,
        CreditPolicySet(credit_limit_minor=99_000_000, reason="Generous"),
        actor_id=None,
    )
    order = _an_order(db, customer.id)
    SalesOrderService(db).confirm(order.id, actor_id=None)
    CustomerService(db).add_note(customer.id, NoteCreate(body="A note"), actor_id=None)

    events = CustomerTimelineService(db).events(customer.id)
    stamps = [e.at for e in events]
    assert stamps == sorted(stamps, reverse=True), "the timeline is not newest-first"

    # Deterministic: several of these rows share a func.now() timestamp, so a sort on the
    # timestamp alone would be free to reorder them between calls.
    again = [(e.kind, e.summary) for e in CustomerTimelineService(db).events(customer.id)]
    assert again == [(e.kind, e.summary) for e in events]


def test_r8_10_the_timeline_adds_no_events_table(db):
    """The requirement forbids making this easier with a stored event log."""
    from app.modules.customers.models import Customer

    tables = set(Customer.metadata.tables)
    for forbidden in ("customer_event", "customer_timeline", "timeline_event", "event_log"):
        assert forbidden not in tables, f"R8.10 forbids {forbidden}"


def test_r8_10_a_credit_override_shows_up_on_the_timeline(db, customer):
    """Why R8.8 logs against the CUSTOMER: "we went over their limit" is a fact about the
    relationship, and the founder should meet it when reading their history."""
    svc = CreditPolicyService(db)
    svc.set_policy(
        customer.id, CreditPolicySet(credit_limit_minor=1000, reason="Tiny"), actor_id=None
    )
    svc.enforce(customer.id, 9000, override_reason="Approved, cheque in hand")

    summaries = [e.summary for e in CustomerTimelineService(db).events(customer.id)]
    assert any("overridden" in s for s in summaries)


# --- R3.7 / R8.12 -------------------------------------------------------------


def test_r8_14_the_seed_gives_one_customer_full_depth(db):
    from app.modules.customers.models import Customer

    svc = CustomerService(db)
    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    assert len(svc.contacts(seeded.id)) >= 2, "R8.14 wants multiple contacts"
    assert len(svc.branches(seeded.id)) >= 2, "R8.14 wants multiple ship-to branches"
    assert svc.notes(seeded.id), "R8.14 wants notes"

    history = CreditPolicyService(db).history(seeded.id)
    assert len(history) >= 2, "R8.3's history panel needs more than one version to show"
    assert sum(1 for h in history if h.is_current) == 1
    assert all(h.reason for h in history[:-1]), "every change should record why"


def test_r8_14_the_seed_holds_a_breaching_order_and_a_recorded_override(db):
    """On a DIFFERENT customer than the depth one, so the demo shows a healthy account and
    an overridden one — and so the first customer's work stays closed, which older tests
    assert."""
    overrides = db.scalars(
        select(ActivityLog).where(
            ActivityLog.entity_type == "customer", ActivityLog.verb == "overrode"
        )
    ).all()
    assert overrides, "the seed records no credit override"
    row = overrides[0]
    assert row.data["over_by_minor"] > 0
    assert row.data["reason"]


def test_r8_1_r8_2_the_detail_page_shows_contacts_branches_and_the_forms(client, db):
    from app.modules.customers.models import Customer

    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    html = client.get(f"/customers/{seeded.id}").text

    assert "Contacts" in html and "Ship-to branches" in html
    for contact in CustomerService(db).contacts(seeded.id)[:2]:
        assert contact.name in html
    for branch in CustomerService(db).branches(seeded.id)[:2]:
        assert branch.city in html
    assert f'action="/customers/{seeded.id}/contacts"' in html
    assert f'action="/customers/{seeded.id}/branches"' in html


def test_r8_3_the_detail_page_shows_the_versioned_terms_with_reasons(client, db):
    from app.modules.customers.models import Customer

    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    html = client.get(f"/customers/{seeded.id}").text

    assert "Credit terms" in html
    assert "Why it changed" in html
    # The reason a version exists must reach the page, or the history is just numbers.
    # The NEWEST version, not the oldest — the oldest is the row `create` wrote alongside
    # the customer, which predates versioning and legitimately has no reason.
    versions = CreditPolicyService(db).history(seeded.id)
    assert versions[0].reason
    assert versions[0].reason in html
    assert "Nothing is edited in place" in html


def test_r8_7_r8_10_the_detail_page_explains_credit_and_renders_the_timeline(client, db):
    from app.modules.customers.models import Customer

    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    html = client.get(f"/customers/{seeded.id}").text

    assert "Credit position" in html
    assert "Currently outstanding" in html
    assert "Timeline" in html
    # R8.10's sources are named on screen so the founder knows what they are looking at.
    assert "Orders, invoices, payments, tasks, notes" in html


def test_r8_1_adding_and_removing_a_contact_works_through_the_screen(client, db):
    from app.modules.customers.models import Customer

    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    added = client.post(
        f"/customers/{seeded.id}/contacts",
        data={"name": "Screen Contact", "designation": "Tester"},
        follow_redirects=False,
    )
    assert added.status_code == 303
    assert "Screen Contact" in client.get(f"/customers/{seeded.id}").text

    contact = next(
        c for c in CustomerService(db).contacts(seeded.id) if c.name == "Screen Contact"
    )
    removed = client.post(
        f"/customer-contacts/{contact.id}/delete",
        data={"customer_id": str(seeded.id)},
        follow_redirects=False,
    )
    assert removed.status_code == 303

    # Gone from the contact list — but NOT from the page, because the timeline correctly
    # still records that it was once added. Asserting on the whole page would be asserting
    # that history forgets, which is the opposite of what this build does.
    assert contact.id not in {c.id for c in CustomerService(db).contacts(seeded.id)}
    after = client.get(f"/customers/{seeded.id}").text
    assert f"/customer-contacts/{contact.id}/delete" not in after


def test_r8_3_the_credit_form_refuses_a_blank_reason(client, db):
    from app.modules.customers.models import Customer

    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    before = len(CreditPolicyService(db).history(seeded.id))

    response = client.post(
        f"/customers/{seeded.id}/credit",
        data={"credit_limit_rupees": "9999", "payment_terms_days": "30", "reason": "   "},
        follow_redirects=False,
    )
    # Post/Redirect/Get holds for refusals: back to the page with a flash, not a dead body.
    assert response.status_code == 303
    assert len(CreditPolicyService(db).history(seeded.id)) == before, (
        "a refused change still wrote a version"
    )


def test_r3_7_every_new_part_6_model_declares_its_blocking_references(db, customer):
    from app.db.references import REFERENCES, blocking_references

    for table in (
        "customer_contact", "customer_address", "customer_credit_policy", "customer_note",
    ):
        assert table in REFERENCES, f"{table} owes references.py an entry (R3.7)"

    # Exercised, not merely present: a Reference names its column by STRING, so a wrong
    # one raises AttributeError at check time rather than import time.
    note = CustomerService(db).add_note(customer.id, NoteCreate(body="x"), actor_id=None)
    assert blocking_references(db, note) == []


def test_r8_12_part_6_did_not_build_part_7s_work(db):
    """Scope fence: health score, quotations and returns belong to Part 7."""
    from app.modules.customers.models import Customer

    tables = set(Customer.metadata.tables)
    for forbidden in ("quotation", "quotation_line", "sales_return", "credit_note"):
        assert forbidden not in tables, f"{forbidden} is Part 7's work, not Part 6's (R8.12)"
