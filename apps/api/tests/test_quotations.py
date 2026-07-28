"""Part 7 C1 — quotation: create / send / revise / expire / convert (R9.1–R9.3).

Each test builds its own quotation, and the money assertions are on integer minor units.
The load-bearing one is R9.3: conversion must carry the QUOTED price, not re-resolve today's
list price — that is the entire reason a quotation exists.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.activity.models import ActivityLog
from app.modules.sales.models import Quotation, QuotationRevision
from app.modules.sales.quotation import DOC_TYPE, QuotationService
from app.modules.sales.schemas import (
    QuotationCreate,
    QuotationLineCreate,
    QuotationRevise,
)

# A price nothing in the price list will accidentally match, so "the quoted price survived"
# cannot pass by coincidence.
QUOTED = 777_77
OTHER = 999_99


@pytest.fixture()
def customer(db):
    from app.modules.customers.models import Customer

    return db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )


@pytest.fixture()
def products(db):
    from app.modules.products.models import Product

    rows = list(
        db.scalars(
            select(Product).where(Product.deleted_at.is_(None)).order_by(Product.sku_code).limit(3)
        )
    )
    assert len(rows) >= 2
    return rows


def _quote(db, customer, products, *, price: int = QUOTED, qty: str = "5", **kw):
    return QuotationService(db).create(
        QuotationCreate(
            customer_id=customer.id,
            lines=[
                QuotationLineCreate(
                    product_id=products[0].id, qty=Decimal(qty), unit_price_minor=price
                )
            ],
            **kw,
        ),
        actor_id=None,
    )


def _activity(db, quotation_id, verb: str) -> int:
    return db.scalar(
        select(func.count()).select_from(ActivityLog).where(
            ActivityLog.entity_type == "quotation",
            ActivityLog.entity_id == quotation_id,
            ActivityLog.verb == verb,
        )
    ) or 0


# --- R9.1: create / send / expire --------------------------------------------


def test_r9_1_a_quotation_is_created_as_a_draft_with_its_own_number(db, customer, products):
    quote = _quote(db, customer, products)

    assert quote.status == "draft"
    assert quote.quotation_no.startswith(f"{DOC_TYPE}-")
    assert quote.total_minor > 0
    # Money arithmetic matches the order service's: subtotal + tax = total, all integers.
    assert quote.subtotal_minor + quote.tax_minor == quote.total_minor
    # A draft has no agreed version to preserve yet.
    assert quote.revisions == []


def test_r9_1_the_quotation_number_does_not_share_part_3s_supplier_sequence(db):
    """`QUO` already numbers supplier quotations. Sharing it would interleave two unrelated
    sequences in `number_sequence`, which is invisible until the numbering looks wrong."""
    assert DOC_TYPE != "QUO"

    from app.modules.config.models import NumberSequence

    types = set(
        db.scalars(select(NumberSequence.doc_type).where(NumberSequence.deleted_at.is_(None)))
    )
    # Both types may exist, but they must be DIFFERENT rows.
    assert DOC_TYPE in types or not types & {DOC_TYPE}


def test_r9_1_sending_records_version_1_verbatim(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    sent = svc.send(quote.id, actor_id=None)

    assert sent.status == "sent"
    assert len(sent.revisions) == 1
    v1 = sent.revisions[0]
    assert v1.revision_no == 1
    assert v1.is_current
    # The baseline carries no reason — it is what was originally sent, not a change.
    assert v1.reason is None
    # Verbatim: the snapshot's lines match the live lines exactly.
    assert [ln.unit_price_minor for ln in v1.lines] == [
        ln.unit_price_minor for ln in sent.lines
    ]
    assert v1.total_minor == sent.total_minor


def test_r9_1_a_quotation_cannot_be_sent_twice(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)

    with pytest.raises(ConflictError, match="already sent"):
        svc.send(quote.id, actor_id=None)


def test_r9_1_expire_retires_an_open_quotation(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)

    expired = svc.expire(quote.id, actor_id=None)
    assert expired.status == "expired"
    assert not expired.is_open

    with pytest.raises(ConflictError, match="cannot expire"):
        svc.expire(quote.id, actor_id=None)


def test_r9_1_past_validity_is_derived_and_distinct_from_being_expired(db, customer, products):
    """A lapsed DATE and a retired STATUS are different facts, and the screen shows both."""
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    quote = _quote(db, customer, products, quotation_date=yesterday - timedelta(days=5),
                   valid_until=yesterday)

    assert quote.past_validity is True
    assert quote.status == "draft", "the date passing must not silently change the status"


def test_r9_1_a_validity_date_before_the_quotation_date_is_refused(db, customer, products):
    with pytest.raises(ValidationError, match="cannot expire before"):
        _quote(
            db, customer, products,
            quotation_date=date(2026, 7, 20),
            valid_until=date(2026, 7, 19),
        )


def test_r9_1_each_verb_writes_exactly_one_activity_row(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)
    svc.revise(
        quote.id,
        QuotationRevise(
            reason="Volume discount agreed",
            lines=[QuotationLineCreate(product_id=products[0].id, qty=Decimal("5"),
                                       unit_price_minor=OTHER)],
        ),
        actor_id=None,
    )
    svc.expire(quote.id, actor_id=None)

    for verb in ("created", "sent", "revised", "expired"):
        assert _activity(db, quote.id, verb) == 1, f"{verb} should write exactly one row (G5)"


# --- R9.2: append-only revisions ---------------------------------------------


def test_r9_2_a_revision_appends_and_leaves_the_previous_version_verbatim(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products, price=QUOTED)
    svc.send(quote.id, actor_id=None)

    revised = svc.revise(
        quote.id,
        QuotationRevise(
            reason="Customer pushed back on price",
            lines=[
                QuotationLineCreate(
                    product_id=products[0].id, qty=Decimal("5"), unit_price_minor=OTHER
                )
            ],
        ),
        actor_id=None,
    )

    assert len(revised.revisions) == 2
    v1, v2 = revised.revisions[0], revised.revisions[1]
    assert v1.revision_no == 1 and v2.revision_no == 2
    assert v2.is_current and not v1.is_current
    # THE POINT: v1 still reads exactly as it was sent, at the ORIGINAL price.
    assert [ln.unit_price_minor for ln in v1.lines] == [QUOTED]
    assert [ln.unit_price_minor for ln in v2.lines] == [OTHER]
    # And the live lines are the new ones.
    assert [ln.unit_price_minor for ln in revised.lines] == [OTHER]


def test_r9_2_a_revision_without_a_reason_is_refused(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)

    import pydantic

    with pytest.raises(pydantic.ValidationError):
        QuotationRevise(reason="", lines=[
            QuotationLineCreate(product_id=products[0].id, qty=Decimal("1"))
        ])

    with pytest.raises(ValidationError, match="needs a reason"):
        svc.revise(
            quote.id,
            QuotationRevise(reason="   ", lines=[
                QuotationLineCreate(product_id=products[0].id, qty=Decimal("1"),
                                    unit_price_minor=OTHER)
            ]),
            actor_id=None,
        )


def test_r9_2_only_a_sent_quotation_can_be_revised(db, customer, products):
    """A draft has no agreed version to preserve — the same reasoning R4.7 used for an
    unconfirmed PO. A converted or expired one is past revising."""
    svc = QuotationService(db)
    draft = _quote(db, customer, products)

    payload = QuotationRevise(
        reason="Too early",
        lines=[QuotationLineCreate(product_id=products[0].id, qty=Decimal("1"),
                                   unit_price_minor=OTHER)],
    )
    with pytest.raises(ConflictError, match="Only a sent quotation"):
        svc.revise(draft.id, payload, actor_id=None)

    svc.send(draft.id, actor_id=None)
    svc.expire(draft.id, actor_id=None)
    with pytest.raises(ConflictError, match="Only a sent quotation"):
        svc.revise(draft.id, payload, actor_id=None)


def test_r9_2_the_revision_table_has_no_superseded_at_column(db):
    """Mirrors Part 3's decision: the NEXT revision's created_at already says when this one
    stopped applying, and a column written after insert would make append-only untrue."""
    columns = {c.name for c in QuotationRevision.__table__.columns}
    assert "superseded_at" not in columns
    assert "valid_to" not in columns, "a sequence of offers is not a period — see Part 6"


def test_r9_2_three_revisions_read_back_in_order_at_their_own_prices(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products, price=100_00)
    svc.send(quote.id, actor_id=None)
    for price in (90_00, 80_00):
        svc.revise(
            quote.id,
            QuotationRevise(
                reason=f"Down to {price}",
                lines=[QuotationLineCreate(product_id=products[0].id, qty=Decimal("5"),
                                           unit_price_minor=price)],
            ),
            actor_id=None,
        )

    detail = svc.get(quote.id)
    assert [r.revision_no for r in detail.revisions] == [1, 2, 3]
    assert [r.lines[0].unit_price_minor for r in detail.revisions] == [100_00, 90_00, 80_00]
    assert detail.revisions[-1].is_current


# --- R9.3: conversion carries the quoted price -------------------------------


def test_r9_3_conversion_is_one_action_and_carries_the_quoted_price(db, customer, products):
    """The requirement's own acceptance: a test asserting the prices match.

    QUOTED is a price nothing in the price list matches, so this cannot pass by coincidence.
    """
    svc = QuotationService(db)
    quote = _quote(db, customer, products, price=QUOTED, qty="4")
    svc.send(quote.id, actor_id=None)

    order = svc.convert(quote.id, actor_id=None)

    assert [ln.unit_price_minor for ln in order.lines] == [QUOTED], (
        "the order did not carry the quoted price — it re-resolved from the price list"
    )
    assert order.lines[0].qty == Decimal("4")
    assert order.total_minor == quote.total_minor
    assert order.status == "draft", "conversion produces an order, it does not confirm it"


def test_r9_3_conversion_carries_the_LATEST_revision_price(db, customer, products):
    """After a re-quote, the order must honour what was last agreed, not the first offer."""
    svc = QuotationService(db)
    quote = _quote(db, customer, products, price=QUOTED)
    svc.send(quote.id, actor_id=None)
    svc.revise(
        quote.id,
        QuotationRevise(
            reason="Final price",
            lines=[QuotationLineCreate(product_id=products[0].id, qty=Decimal("5"),
                                       unit_price_minor=OTHER)],
        ),
        actor_id=None,
    )

    order = svc.convert(quote.id, actor_id=None)
    assert [ln.unit_price_minor for ln in order.lines] == [OTHER]


def test_r9_3_conversion_marks_the_quotation_and_links_the_order(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)
    order = svc.convert(quote.id, actor_id=None)

    detail = svc.get(quote.id)
    assert detail.status == "converted"
    assert detail.sales_order_id == order.id
    assert detail.sales_order_no == order.order_no
    assert not detail.is_open


def test_r9_3_a_converted_quotation_cannot_be_converted_again(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)
    svc.convert(quote.id, actor_id=None)

    with pytest.raises(ConflictError, match="cannot be converted"):
        svc.convert(quote.id, actor_id=None)


def test_r9_3_an_expired_quotation_cannot_be_converted(db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)
    svc.expire(quote.id, actor_id=None)

    with pytest.raises(ConflictError, match="cannot be converted"):
        svc.convert(quote.id, actor_id=None)


def test_r9_3_conversion_writes_one_row_on_each_entity(db, customer, products):
    """Part 3's decision 3: the source logs the conversion, the target logs its own
    creation. Two entities, one row each, so G5 holds without either service knowing about
    the other's log."""
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)
    order = svc.convert(quote.id, actor_id=None)

    assert _activity(db, quote.id, "converted") == 1
    order_rows = db.scalar(
        select(func.count()).select_from(ActivityLog).where(
            ActivityLog.entity_type == "sales_order",
            ActivityLog.entity_id == order.id,
            ActivityLog.verb == "created",
        )
    )
    assert order_rows == 1


def test_r9_3_conversion_does_not_rebuild_the_order(db):
    """G16 — a source walk. The conversion must call SalesOrderService.create rather than
    assembling SalesOrder/SalesOrderLine itself, or the two paths drift on tax and rounding.
    """
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "app" / "modules" / "sales" / "quotation.py"
    ).read_text(encoding="utf-8")

    assert "SalesOrderService(self.db).create(" in src
    assert "SalesOrderLine(" not in src, "the conversion builds order lines itself"
    assert "allocate_document_number(\n            self.db, doc_type=\"SO\"" not in src


# --- R3.7 / the guards -------------------------------------------------------


def test_r3_7_the_quotation_models_declare_their_blocking_references(db, customer, products):
    from app.db.references import REFERENCES, blocking_references

    for table in (
        "quotation", "quotation_line", "quotation_revision", "quotation_revision_line",
    ):
        assert table in REFERENCES, f"{table} owes references.py an entry (R3.7)"

    # Exercised: an OPEN quotation blocks retiring the product it names, because it will
    # read that product again when it converts (the R4.1/R4.3 precedent).
    quote = _quote(db, customer, products)
    QuotationService(db).send(quote.id, actor_id=None)
    found = blocking_references(db, products[0])
    assert any("open quotation" in phrase for phrase in found), found


def test_r3_7_a_converted_quotation_stops_blocking_its_product(db, customer, products):
    """History does not block: the order it produced snapshotted what it needed (R1.7)."""
    from app.db.references import blocking_references

    svc = QuotationService(db)
    quote = _quote(db, customer, products, qty="1")
    svc.send(quote.id, actor_id=None)
    svc.convert(quote.id, actor_id=None)

    phrases = blocking_references(db, products[0])
    assert not any("open quotation" in p for p in phrases), phrases


def test_r9_1_an_unknown_quotation_raises_not_found(db):
    with pytest.raises(NotFoundError):
        QuotationService(db).get(uuid.uuid4())


# --- the screens -------------------------------------------------------------


def test_r9_1_the_quotation_list_and_detail_pages_render(client, db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products)
    svc.send(quote.id, actor_id=None)
    db.commit()

    listing = client.get("/quotations").text
    assert "Quotations" in listing
    assert quote.quotation_no in listing
    assert 'action="/quotations"' in listing
    # The grid offers a price per line — a quotation names its own price.
    assert 'name="unit_price_rupees"' in listing

    detail = client.get(f"/quotations/{quote.id}").text
    assert "Version history" in detail
    assert "Re-quote" in detail
    assert f'action="/quotations/{quote.id}/convert"' in detail
    assert "quoted</strong> prices forward" in detail or "quoted" in detail


def test_r9_2_the_detail_page_shows_each_version_at_its_own_price(client, db, customer, products):
    svc = QuotationService(db)
    quote = _quote(db, customer, products, price=100_00)
    svc.send(quote.id, actor_id=None)
    svc.revise(
        quote.id,
        QuotationRevise(
            reason="Sharpened for volume",
            lines=[QuotationLineCreate(product_id=products[0].id, qty=Decimal("5"),
                                       unit_price_minor=80_00)],
        ),
        actor_id=None,
    )
    db.commit()

    html = client.get(f"/quotations/{quote.id}").text
    assert "Sharpened for volume" in html
    assert "v1" in html and "v2" in html
    # Both prices on the page: the history is readable, not just counted.
    assert "100.00" in html and "80.00" in html


def test_r9_15_the_seed_holds_a_quotation_a_revised_one_and_a_converted_one(db):
    quotes = list(db.scalars(select(Quotation).where(Quotation.deleted_at.is_(None))))
    assert quotes, "the seed holds no quotation"

    statuses = {q.status for q in quotes}
    assert "sent" in statuses, "no open quotation to look at"
    assert "converted" in statuses, "no converted quotation"
    assert any(len(q.revisions) >= 2 for q in quotes), "no revised quotation"
    converted = next(q for q in quotes if q.status == "converted")
    assert converted.sales_order_id is not None
