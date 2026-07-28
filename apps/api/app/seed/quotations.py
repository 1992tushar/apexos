"""Part 7 C1's seed section: quotations (R9.15's first half).

Three documents, because the screens need all three states to be worth looking at:

* one **sent** quotation still open — something to convert or expire,
* one **revised** twice, so the version history has more than one row and the "prior version
  readable verbatim" claim is visible rather than merely tested,
* one **converted**, linked to the order it produced at the quoted price.

C2 adds the reservation-holding order and the partial return.

The quoted prices are deliberately BELOW each product's list price, so the converted order
demonstrably carries the quoted figure rather than the list one — if the conversion ever
regressed to re-resolving the price, the demo would show it.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from app.modules.customers.models import Customer
from app.modules.pricing.models import SellingPrice
from app.modules.sales.models import Quotation
from app.modules.sales.quotation import QuotationService
from app.modules.sales.schemas import (
    QuotationCreate,
    QuotationLineCreate,
    QuotationRevise,
)
from app.seed.helpers import SeedContext

# Each quoted price is this fraction of the product's list price — a visible discount, and
# far enough off the list price that a regression to re-resolving would be obvious.
_DISCOUNT = Decimal("0.90")
_REVISED_DISCOUNT = Decimal("0.82")


def seed_quotations(ctx: SeedContext) -> dict | None:
    db = ctx.db
    if db.scalar(select(func.count()).select_from(Quotation)) or 0:
        return None

    customers = list(
        db.scalars(
            select(Customer)
            .where(Customer.deleted_at.is_(None))
            .order_by(Customer.code)
            .limit(3)
        )
    )
    priced = db.execute(
        select(SellingPrice.product_id, SellingPrice.price_minor)
        .where(SellingPrice.deleted_at.is_(None), SellingPrice.price_minor > 0)
        .order_by(SellingPrice.price_minor.desc())
        .limit(3)
    ).all()
    if len(customers) < 2 or len(priced) < 2:
        return None

    svc = QuotationService(db)
    made: dict[str, str | None] = {}

    def quote(customer, rows, note: str):
        return svc.create(
            QuotationCreate(
                customer_id=customer.id,
                note=note,
                lines=[
                    QuotationLineCreate(
                        product_id=product_id,
                        qty=Decimal(qty),
                        unit_price_minor=int(Decimal(price) * _DISCOUNT),
                    )
                    for product_id, price, qty in rows
                ],
            ),
            actor_id=ctx.actor_id,
        )

    # 1. Open, sent, awaiting a decision.
    open_quote = quote(
        customers[0],
        [(priced[0][0], priced[0][1], "20"), (priced[1][0], priced[1][1], "10")],
        "Standard monthly supply — 10% off list",
    )
    svc.send(open_quote.id, actor_id=ctx.actor_id)
    made["open"] = open_quote.quotation_no

    # 2. Revised twice, so the history is non-trivial.
    revised = quote(
        customers[1],
        [(priced[0][0], priced[0][1], "50")],
        "Bulk enquiry",
    )
    svc.send(revised.id, actor_id=ctx.actor_id)
    svc.revise(
        revised.id,
        QuotationRevise(
            reason="Customer asked for a keener price on 50 units",
            lines=[
                QuotationLineCreate(
                    product_id=priced[0][0],
                    qty=Decimal("50"),
                    unit_price_minor=int(Decimal(priced[0][1]) * _REVISED_DISCOUNT),
                )
            ],
        ),
        actor_id=ctx.actor_id,
    )
    made["revised"] = revised.quotation_no

    # 3. Converted — the order it produced carries the quoted price.
    #
    # Deliberately NOT on customers[0]. Conversion creates a sales order in DRAFT, and
    # `references.py` counts draft as OPEN, which would make that customer blocked and
    # undeletable — breaking two Part 1/3 tests that encode "the first customer's work is
    # all closed". Part 6 hit this same edge with a confirmed order; the rule is the one in
    # CODEBASE-MAP: before seeding a document in an open status, ask which tests treat that
    # party as quiet.
    accepted = quote(
        customers[2] if len(customers) > 2 else customers[1],
        [(priced[1][0], priced[1][1], "12")],
        "Accepted on the phone",
    )
    svc.send(accepted.id, actor_id=ctx.actor_id)
    order = svc.convert(accepted.id, actor_id=ctx.actor_id)
    made["converted"] = f"{accepted.quotation_no} -> {order.order_no}"

    db.flush()
    return made
