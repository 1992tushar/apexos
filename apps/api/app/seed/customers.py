"""Part 6's seed section: customer depth (R8.14).

What the screens need to be worth looking at: a customer with more than one contact and
more than one ship-to branch, a real credit limit with a **versioned** history behind it,
notes, an order that breaches the limit, and one recorded override.

The breaching order is the interesting one. It is left CONFIRMED-via-override rather than
blocked, because the override is what R8.8 asks to see on screen — a blocked order would
leave nothing behind except a draft nobody can explain.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.modules.customers.credit import CreditPolicyService
from app.modules.customers.models import Customer, CustomerContact
from app.modules.customers.schemas import (
    BranchUpsert,
    ContactUpsert,
    CreditPolicySet,
    NoteCreate,
)
from app.modules.customers.service import CustomerService
from app.seed.helpers import SeedContext

_CONTACTS: tuple[tuple[str, str, bool], ...] = (
    ("Sunita Deshpande", "Proprietor", True),
    ("Ramesh Iyer", "Accounts", False),
    ("Priya Nair", "Stores", False),
)

_BRANCHES: tuple[tuple[str, str, bool], ...] = (
    ("Shop 12, Laxmi Road", "Pune", True),
    ("Warehouse 4, MIDC", "Nashik", False),
)

_NOTES: tuple[str, ...] = (
    "Prefers delivery before noon; the shop shuts 1–4pm.",
    "Asked about slab pricing on tissue rolls — revisit next quarter.",
)

# Two versions, so the history panel has something to show and R8.3 is visible rather than
# merely implemented: opening terms, then a raise with the reason recorded.
_TERMS: tuple[tuple[int, int, str], ...] = (
    (150000, 30, "Opening terms agreed at onboarding"),
    (400000, 45, "Raised after six months of on-time payment"),
)


def seed_customer_depth(ctx: SeedContext) -> dict | None:
    """Give one seeded customer full depth, and leave a recorded credit override."""
    db = ctx.db
    if db.scalar(select(func.count()).select_from(CustomerContact)) or 0:
        return None

    customer = db.scalar(
        select(Customer)
        .where(Customer.deleted_at.is_(None))
        .order_by(Customer.code)
        .limit(1)
    )
    if customer is None:
        return None

    svc = CustomerService(db)
    credit = CreditPolicyService(db)

    for name, designation, primary in _CONTACTS:
        svc.add_contact(
            customer.id,
            ContactUpsert(name=name, designation=designation, is_primary=primary),
            actor_id=ctx.actor_id,
        )
    for line1, city, default in _BRANCHES:
        svc.add_branch(
            customer.id,
            BranchUpsert(line1=line1, city=city, is_default=default),
            actor_id=ctx.actor_id,
        )
    for body in _NOTES:
        svc.add_note(customer.id, NoteCreate(body=body), actor_id=ctx.actor_id)

    for limit, terms, reason in _TERMS:
        credit.set_policy(
            customer.id,
            CreditPolicySet(
                credit_limit_minor=limit, payment_terms_days=terms, reason=reason
            ),
            actor_id=ctx.actor_id,
        )

    # The breach goes on a DIFFERENT customer, for two reasons. The demo reads better —
    # you see one healthy account and one that had to be overridden — and it preserves a
    # seed invariant the rest of the suite relies on: the first customer's work is all
    # CLOSED, so nothing live references it. A confirmed order is "open" (references.py),
    # which would make that customer undeletable and is exactly what two older tests assert
    # is not the case.
    breach_customer = db.scalar(
        select(Customer)
        .where(Customer.deleted_at.is_(None), Customer.id != customer.id)
        .order_by(Customer.code)
        .limit(1)
    )
    override = (
        _seed_breaching_order(ctx, breach_customer) if breach_customer is not None else None
    )

    db.flush()
    return {
        "customer": customer.code,
        "contacts": len(_CONTACTS),
        "branches": len(_BRANCHES),
        "notes": len(_NOTES),
        "credit_versions": len(_TERMS),
        "breach_customer": breach_customer.code if breach_customer else None,
        "override": override,
    }


def _seed_breaching_order(ctx: SeedContext, customer) -> str | None:
    """One order over the limit, confirmed with a recorded override (R8.14).

    Sized off the CURRENT limit so it stays a breach if `_TERMS` is ever edited — a
    hard-coded quantity would quietly stop breaching the moment the limit is raised, and
    that is exactly the kind of seed rot that makes a demo screen go blank.
    """
    from app.modules.products.models import Product
    from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate
    from app.modules.sales.service import SalesOrderService

    db = ctx.db
    credit = CreditPolicyService(db)
    # This customer needs a limit of its own to breach — it is not the one that got the
    # versioned terms above.
    credit.set_policy(
        customer.id,
        CreditPolicySet(
            credit_limit_minor=50000,
            payment_terms_days=15,
            reason="Modest opening limit — new account",
        ),
        actor_id=ctx.actor_id,
    )
    policy = credit.current(customer.id)
    if policy is None or policy.credit_limit_minor <= 0:
        return None

    # The selling price lives in `SellingPrice`, not on `Product` — the dearest current one
    # keeps the breaching quantity small and the order readable.
    from app.modules.pricing.models import SellingPrice

    row = db.execute(
        select(SellingPrice.product_id, SellingPrice.price_minor)
        .where(SellingPrice.deleted_at.is_(None), SellingPrice.price_minor > 0)
        .order_by(SellingPrice.price_minor.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    product_id, unit_price = row
    product = db.get(Product, product_id)
    if product is None:
        return None

    outstanding = credit.repo.outstanding_minor(customer.id)
    headroom = policy.credit_limit_minor - outstanding
    # Enough units to clear the headroom and then some, so it is unambiguously over.
    qty = max(int(headroom // max(int(unit_price), 1)) + 2, 2)

    order = SalesOrderService(db).create(
        SalesOrderCreate(
            customer_id=customer.id,
            lines=[SalesOrderLineCreate(product_id=product.id, qty=Decimal(qty))],
        ),
        actor_id=ctx.actor_id,
    )
    decision = credit.check(customer.id, order.total_minor)
    if decision.allowed:
        # The order did not breach after all — leave it in draft rather than logging an
        # override that never happened.
        return None

    SalesOrderService(db).confirm(
        order.id,
        actor_id=ctx.actor_id,
        credit_override_reason="Founder approved — cheque collected on delivery",
    )
    return order.order_no
