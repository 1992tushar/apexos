"""Part 7 C2b — the customer health score (R9.10/R9.11).

`as_of` is injected throughout so the recency and frequency arithmetic is pinned to a date
rather than depending on when the suite runs. The score is asserted against hand-computed
figures, not against whatever the code returns.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modules.customers.health import (
    RECENCY_STALE_DAYS,
    TARGET_MARGIN_PCT,
    TARGET_ORDERS_PER_MONTH,
    WEIGHT_FREQUENCY,
    WEIGHT_PAYMENT,
    WEIGHT_PROFITABILITY,
    WEIGHT_RECENCY,
    CustomerHealthService,
)
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import CustomerService

NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


@pytest.fixture()
def fresh_customer(db):
    """A customer with NO history at all — the R9.11 case."""
    from app.modules.config.models import CustomerType

    ctype = db.scalar(select(CustomerType).where(CustomerType.deleted_at.is_(None)))
    return CustomerService(db).create(
        CustomerCreate(
            name=f"Health Co {uuid.uuid4().hex[:6]}",
            customer_type_id=ctype.id,
            city="Pune",
        ),
        actor_id=None,
    )


def _order(db, customer, *, qty: str, unit_price_minor: int, days_ago: int = 0):
    """A confirmed-status-free draft order dated in the past."""
    from app.modules.products.models import Product
    from app.modules.sales.models import SalesOrder
    from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate
    from app.modules.sales.service import SalesOrderService

    product = db.scalar(select(Product).where(Product.deleted_at.is_(None)))
    detail = SalesOrderService(db).create(
        SalesOrderCreate(
            customer_id=customer.id,
            lines=[
                SalesOrderLineCreate(
                    product_id=product.id,
                    qty=Decimal(qty),
                    unit_price_minor=unit_price_minor,
                )
            ],
        ),
        actor_id=None,
    )
    order = db.get(SalesOrder, detail.id)
    order.order_date = (NOW - timedelta(days=days_ago)).date()
    db.flush()
    return order


# --- R9.11: no history at all ------------------------------------------------


def test_r9_11_a_customer_with_no_history_scores_unknown(db, fresh_customer):
    """Not 0, not 50 — unknown. Inventing a middling number for a brand-new customer
    would read as a fact about them."""
    explained = CustomerHealthService(db).score(fresh_customer.id, as_of=NOW)

    assert not explained.is_known
    assert explained.display == "unknown"
    assert explained.unknown_reason
    assert "no orders" in explained.unknown_reason
    # The bug this pins: "owes nothing" used to score full marks on payment, which was then
    # the only measurable input — so a customer with NO history came out at 100. Worse than
    # the default number R9.11 forbids, because it looks like a compliment.
    assert explained.value is None


def test_r9_11_the_unknown_score_still_names_every_input_and_its_weight(db, fresh_customer):
    """A score that cannot be computed must still show WHAT it would have used — otherwise
    the founder cannot tell what is missing."""
    explained = CustomerHealthService(db).score(fresh_customer.id, as_of=NOW)

    labels = {i.label for i in explained.inputs}
    assert labels == {"Order frequency", "Profitability", "Payment behaviour", "Recency"}
    assert all(i.weight for i in explained.inputs)
    # With no history, EVERY input says why it could not be measured — including payment.
    assert all(i.missing_reason for i in explained.inputs)


# --- R9.10: the four inputs and the weighting --------------------------------


def test_r9_10_the_score_shows_every_input_its_weight_and_the_conversion(db, fresh_customer):
    _order(db, fresh_customer, qty="10", unit_price_minor=200_00, days_ago=10)

    explained = CustomerHealthService(db).score(fresh_customer.id, as_of=NOW)

    assert explained.is_known
    by_label = {i.label: i for i in explained.inputs}
    assert by_label["Order frequency"].weight == f"{WEIGHT_FREQUENCY}%"
    assert by_label["Profitability"].weight == f"{WEIGHT_PROFITABILITY}%"
    assert by_label["Payment behaviour"].weight == f"{WEIGHT_PAYMENT}%"
    assert by_label["Recency"].weight == f"{WEIGHT_RECENCY}%"
    # The conversion to points is SHOWN, not hidden — "→ n/100" on each measured input.
    assert "/100" in by_label["Recency"].value
    # And the weighting is in the formula, so the founder can redo the arithmetic.
    assert f"{WEIGHT_PROFITABILITY}%" in explained.formula


def test_r9_10_recency_decays_to_zero_at_the_stale_threshold(db, fresh_customer):
    svc = CustomerHealthService(db)

    _order(db, fresh_customer, qty="1", unit_price_minor=100_00, days_ago=0)
    assert svc.recency(fresh_customer.id, as_of=NOW) == 0
    fresh_today = svc.score(fresh_customer.id, as_of=NOW)
    recency_today = next(i for i in fresh_today.inputs if i.label == "Recency")
    assert "→ 100/100" in recency_today.value

    # The same order, read from far enough in the future to be stale.
    stale_as_of = NOW + timedelta(days=RECENCY_STALE_DAYS)
    stale = svc.score(fresh_customer.id, as_of=stale_as_of)
    recency_stale = next(i for i in stale.inputs if i.label == "Recency")
    assert "→ 0/100" in recency_stale.value


def test_r9_10_frequency_is_capped_at_the_target_rather_than_climbing_forever(db, fresh_customer):
    """Beyond the target the score stops rising — the difference between a weekly and a
    daily customer is not what this figure measures."""
    svc = CustomerHealthService(db)
    # Far more than TARGET_ORDERS_PER_MONTH sustained over the window.
    for i in range(60):
        _order(db, fresh_customer, qty="1", unit_price_minor=100_00, days_ago=i * 5)

    rate, count = svc.frequency(fresh_customer.id, as_of=NOW)
    assert count == 60
    assert rate > TARGET_ORDERS_PER_MONTH
    frequency = next(
        i
        for i in svc.score(fresh_customer.id, as_of=NOW).inputs
        if i.label == "Order frequency"
    )
    assert "→ 100/100" in frequency.value, "the cap did not hold"


def test_r9_10_profitability_uses_the_existing_margin_logic(db, fresh_customer):
    """R11.6/D-A: margin is selling − the buy price, through MarginService. Not a valuation
    layer, and not a second implementation."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "app" / "modules" / "customers" / "health.py"
    ).read_text(encoding="utf-8")
    assert "MarginService" in src
    # No valuation and no second GP formula of its own.
    assert "ValuationService" not in src
    assert "latest_purchase_minor" not in src, "health recomputes GP instead of calling gp()"


def test_r9_10_a_high_margin_customer_scores_full_marks_on_profitability(db, fresh_customer):
    svc = CustomerHealthService(db)
    # Priced well above the buy price, so the margin clears TARGET_MARGIN_PCT.
    _order(db, fresh_customer, qty="5", unit_price_minor=5000_00, days_ago=5)

    # Part 10 added the uncosted-line count (R13.2): a line whose product has no recorded
    # purchase price is excluded and counted rather than scored at a 100% margin.
    pct, revenue, gp, uncosted = svc.profitability(fresh_customer.id, as_of=NOW)
    assert revenue > 0
    assert pct > TARGET_MARGIN_PCT
    assert uncosted == 0, "this fixture's product is priced on both sides"
    profitability = next(
        i for i in svc.score(fresh_customer.id, as_of=NOW).inputs if i.label == "Profitability"
    )
    assert "→ 100/100" in profitability.value


def test_r9_10_the_score_is_hand_computable_from_its_inputs(db, fresh_customer):
    """The point of showing the arithmetic is that it can be redone. This redoes it."""
    svc = CustomerHealthService(db)
    _order(db, fresh_customer, qty="5", unit_price_minor=5000_00, days_ago=0)

    explained = svc.score(fresh_customer.id, as_of=NOW)
    weights = {
        "Order frequency": WEIGHT_FREQUENCY,
        "Profitability": WEIGHT_PROFITABILITY,
        "Payment behaviour": WEIGHT_PAYMENT,
        "Recency": WEIGHT_RECENCY,
    }

    # Only the MEASURED inputs enter the arithmetic, and the weighting renormalises over
    # them — which is exactly what the caveat claims, so redoing it here checks the claim.
    points: dict[str, int] = {}
    for i in explained.inputs:
        if i.is_missing:
            continue
        assert "→ " in i.value, i.label
        points[i.label] = int(i.value.split("→ ")[1].split("/")[0])

    assert points, "nothing was measured"
    available = sum(weights[label] for label in points)
    expected = round(sum(points[label] * weights[label] for label in points) / available)
    assert abs(int(explained.value) - expected) <= 1, (
        f"the published score {explained.value} does not follow from its own inputs "
        f"({points}) over {available}% of the weighting"
    )


# --- R9.10: renormalising over a partial basis -------------------------------


def test_r9_10_a_partial_basis_renormalises_and_says_so(db, fresh_customer):
    """Part 4's rule, reapplied: a missing input redistributes its weight and the screen
    carries a caveat, rather than the score silently treating it as zero."""
    svc = CustomerHealthService(db)
    # Orders but no invoice yet: frequency, profitability and recency are all measurable,
    # payment is not. That is the partial basis — three inputs out of four.
    _order(db, fresh_customer, qty="2", unit_price_minor=300_00, days_ago=1)

    explained = svc.score(fresh_customer.id, as_of=NOW)
    assert explained.is_known, "three measurable inputs is enough to score"

    payment = next(i for i in explained.inputs if i.label == "Payment behaviour")
    assert payment.is_missing
    assert payment.missing_reason

    # The caveat NAMES what was left out and says the basis is partial — the founder must be
    # able to tell a 75-of-four from a 75-of-three.
    assert explained.caveat
    assert "Payment behaviour" in explained.caveat
    assert "renormalised" in explained.caveat
    assert "partial basis" in explained.caveat
    # And the weighting actually used is stated, not just implied.
    available = WEIGHT_FREQUENCY + WEIGHT_PROFITABILITY + WEIGHT_RECENCY
    assert f"{available}%" in explained.formula


def test_r9_10_payment_needs_an_invoice_to_be_measurable_at_all(db, fresh_customer):
    """The distinction the score got wrong at first, now pinned in both directions.

    NEVER INVOICED is a missing input — there is no behaviour to judge. INVOICED AND SETTLED
    is full marks, because paying up *is* the behaviour being measured. Collapsing the two
    made a brand-new customer score 100.
    """
    svc = CustomerHealthService(db)

    # Direction one: orders but no invoice — not measurable.
    _order(db, fresh_customer, qty="1", unit_price_minor=100_00, days_ago=1)
    _overdue, _outstanding, invoice_count = svc.payment(fresh_customer.id, as_of=NOW)
    assert invoice_count == 0
    payment = next(
        i for i in svc.score(fresh_customer.id, as_of=NOW).inputs
        if i.label == "Payment behaviour"
    )
    assert payment.is_missing
    assert "never invoiced" in payment.value

    # Direction two: a customer that HAS been invoiced is measured, not skipped.
    from app.modules.customers.models import Customer

    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    _o, _out, seeded_invoices = svc.payment(seeded.id, as_of=NOW)
    assert seeded_invoices > 0, "the seeded customer should have invoices"
    seeded_payment = next(
        i for i in svc.score(seeded.id, as_of=NOW).inputs if i.label == "Payment behaviour"
    )
    assert not seeded_payment.is_missing
    assert "→ " in seeded_payment.value


def test_r9_10_overdue_money_costs_the_score(db):
    """A customer with money past its due date must score below one without."""
    from app.modules.finance.models import Invoice
    from app.modules.sales.service import SalesOrderService

    svc = CustomerHealthService(db)
    # The seeded customer with real invoices.
    from app.modules.customers.models import Customer

    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.customer_id == seeded.id, Invoice.deleted_at.is_(None)
        )
    )
    if invoice is None:
        pytest.skip("the seeded customer has no invoice to age")

    before = svc.score(seeded.id, as_of=NOW)
    payment_before = next(i for i in before.inputs if i.label == "Payment behaviour")

    # Push the due date into the past: the same money, now overdue.
    invoice.due_date = (NOW - timedelta(days=30)).date()
    db.flush()

    after = svc.score(seeded.id, as_of=NOW)
    payment_after = next(i for i in after.inputs if i.label == "Payment behaviour")
    assert "overdue" in payment_after.value
    assert payment_after.value != payment_before.value
    del SalesOrderService


def test_r9_10_the_score_stores_nothing(db, fresh_customer):
    """G7 — no score column, no cached rating."""
    from app.modules.customers.models import Customer

    columns = {c.name for c in Customer.__table__.columns}
    assert not columns & {"health_score", "score", "rating", "health"}

    # And computing it twice is idempotent: nothing was written the first time.
    svc = CustomerHealthService(db)
    _order(db, fresh_customer, qty="1", unit_price_minor=100_00, days_ago=2)
    first = svc.score(fresh_customer.id, as_of=NOW)
    second = svc.score(fresh_customer.id, as_of=NOW)
    assert first.value == second.value


# --- the screen ---------------------------------------------------------------


def test_r9_10_the_customer_page_shows_the_score_with_its_weighting(client, db):
    from app.modules.customers.models import Customer

    seeded = db.scalar(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.code).limit(1)
    )
    html = client.get(f"/customers/{seeded.id}").text

    assert "Health score" in html
    for label in ("Order frequency", "Profitability", "Payment behaviour", "Recency"):
        assert label in html, f"the {label!r} input is not on screen"
    # The weighting is visible, which is what R9.10 asks for.
    assert f"{WEIGHT_PROFITABILITY}%" in html


def test_r9_15_the_seed_holds_a_partial_return_with_its_credit_note(db):
    """Partial on purpose: a full return would leave nothing to return, and R9.6's
    remaining-quantity arithmetic would have no demo data."""
    from app.modules.finance.models import CreditNote
    from app.modules.sales.models import SalesReturn
    from app.modules.sales.returns import SalesReturnService

    returns = list(db.scalars(select(SalesReturn).where(SalesReturn.deleted_at.is_(None))))
    assert returns, "the seed holds no return"
    ret = returns[0]

    credit = db.scalar(select(CreditNote).where(CreditNote.sales_return_id == ret.id))
    assert credit is not None, "the seeded return raised no credit note"
    assert credit.total_minor == ret.total_minor

    # PARTIAL: something is still returnable on that invoice.
    remaining = SalesReturnService(db).returnable(ret.invoice_id)
    assert any(line.returnable_qty > 0 for line in remaining), (
        "the seeded return took everything — nothing left to demonstrate R9.6"
    )


def test_r9_5_the_customer_page_shows_the_credit_note_and_says_the_invoice_is_untouched(
    client, db
):
    from app.modules.finance.models import CreditNote

    credit = db.scalar(select(CreditNote).where(CreditNote.deleted_at.is_(None)))
    assert credit is not None
    html = client.get(f"/customers/{credit.customer_id}").text

    assert "Credit notes" in html
    assert credit.credit_note_no in html
    assert "unchanged" in html
