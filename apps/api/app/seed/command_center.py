"""Part 9's seed section: a homepage whose "today" is not three zeros (G14).

Every seeded payment is already dated today — `Payment.paid_at` defaults to `now()` — so
**collections today** has a real figure without help. The two figures that do not are
today's **revenue** and today's **gross margin**, because every seeded invoice is placed
by offset from its due date and the newest lands 30 days ago. A Command Center whose
headline section reads ₹0.00 · ₹0.00 cannot demonstrate anything and, worse, cannot fail
visibly when the arithmetic behind it is wrong — which is exactly what G14 exists to stop.

So: **one invoice dated today, with two lines.**

* Line 1 is on a product with a recorded purchase price, so gross margin is **known** and
  the tile shows a real spread.
* Line 2 is on `SKU-NOBUY-01`, the product Part 8 C3 seeded with a selling price and no
  purchase price at all. `MarginService.gp` reads a missing purchase price as zero and
  would report that line at a **100% margin**, so the margin projection excludes and
  counts it. This line is what makes the homepage's "N lines today have no purchase price
  and are excluded" caveat appear on the demo instead of only in a test.

The invoice is **paid in full today**, which keeps the addition out of every screen it has
no business changing: it never appears in AR ageing, never joins the collections list, and
leaves the receivable untouched. It also makes "collections today" reconstructible by hand
from a single document, which is the whole point of a seeded edge case.

Written directly rather than through the sell loop, and on a customer no other test
asserts about — both for the reasons `app/seed/finance.py` sets out at length.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.modules.config.service import default_business_unit
from app.modules.customers.models import Customer
from app.modules.finance.models import Invoice, InvoiceLine
from app.modules.pricing.models import PurchasePrice, SellingPrice
from app.modules.products.models import Product
from app.seed.finance import _make_invoice, _pay_invoice, _totals
from app.seed.helpers import SeedContext

# Part 8's seed writers, reused deliberately. They are module-private because nothing
# outside the seed should write an invoice this way — but a *second* seed section that
# wrote its own would be a second invoice-writing path in the demo data, and the whole
# reason `_totals` exists is that the tax rounding has to be identical everywhere (G1).

#: Customers to skip before picking a subject. `finance.py` takes four from offset 5 and
#: uses the last of them for its leakage offenders, so offset 9 is the first customer in
#: code order that no other seeded document or test touches.
_CUSTOMER_OFFSET = 9

#: The SKU `finance.py` creates with a selling price and no purchase price.
_NO_COST_SKU = "SKU-NOBUY-01"


def seed_command_center(ctx: SeedContext) -> dict | None:
    """One invoice dated today, settled today (R12.2, G14).

    Guarded on its own marker — an invoice whose `invoice_date` is today and which has no
    `sales_order_id` — so a re-seed on the same day never doubles today's revenue. Runs
    after `seed_finance`, which creates the no-cost product it wants for its second line.
    """
    db = ctx.db
    today = date.today()

    already = db.scalar(
        select(Invoice.id)
        .where(
            Invoice.sales_order_id.is_(None),
            Invoice.invoice_date == today,
            Invoice.deleted_at.is_(None),
        )
        .limit(1)
    )
    if already is not None:
        return None

    bu_id = default_business_unit(db)
    customer = db.scalar(
        select(Customer)
        .where(Customer.deleted_at.is_(None))
        .order_by(Customer.code)
        .offset(_CUSTOMER_OFFSET)
        .limit(1)
    )
    priced = _a_product_with_a_cost(db)
    if customer is None or priced is None:
        return None
    product_id, unit_price = priced

    # Sold at list, so this line adds no leakage: the discount-creep and below-cost
    # indicators must keep firing on exactly the three lines C3 seeded for them, and a
    # fourth offender arriving from Part 9 would quietly weaken those tests.
    invoice = _make_invoice(
        ctx,
        bu_id=bu_id,
        customer_id=customer.id,
        invoice_date=today,
        due_date=today + timedelta(days=30),
        product_id=product_id,
        qty=Decimal("7"),
        unit_price_minor=unit_price,
    )
    no_cost = _add_no_cost_line(ctx, invoice)

    # Paid in full, today. `_pay_invoice` writes the receipt as a Payment plus an
    # allocation and never edits the invoice's money (G4), so the receivable is left
    # exactly as it was before this section ran.
    _pay_invoice(ctx, invoice, 100)
    db.flush()

    return {
        "invoice": f"{invoice.invoice_no} (dated today, settled today)",
        "customer": customer.name,
        "revenue_today_minor": invoice.subtotal_minor,
        "cost_unknown_line": _NO_COST_SKU if no_cost else None,
    }


def _a_product_with_a_cost(db) -> tuple[object, int] | None:
    """The dearest product that has both a list price and a recorded purchase price.

    Both sides are required: without a selling price there is no revenue, and without a
    purchase price the margin would be the very "unknown" case line 2 is here to cover.
    """
    row = db.execute(
        select(SellingPrice.product_id, SellingPrice.price_minor)
        .join(PurchasePrice, PurchasePrice.product_id == SellingPrice.product_id)
        .where(
            SellingPrice.deleted_at.is_(None),
            SellingPrice.price_minor > 0,
            SellingPrice.customer_id.is_(None),
            SellingPrice.customer_type_id.is_(None),
            PurchasePrice.valid_to.is_(None),
            PurchasePrice.deleted_at.is_(None),
            PurchasePrice.price_minor > 0,
        )
        .order_by(SellingPrice.price_minor.desc())
        .limit(1)
    ).first()
    return (row[0], int(row[1])) if row else None


def _add_no_cost_line(ctx: SeedContext, invoice: Invoice) -> bool:
    """Append the cost-unknown line, and re-total the invoice through the ONE step.

    Returns False when `SKU-NOBUY-01` is absent — the invoice is then still worth having
    for its revenue and margin, and the excluded-lines caveat simply does not appear.
    """
    db = ctx.db
    product = db.scalar(
        select(Product).where(
            Product.sku_code == _NO_COST_SKU, Product.deleted_at.is_(None)
        )
    )
    if product is None:
        return False
    price = db.scalar(
        select(SellingPrice.price_minor).where(
            SellingPrice.product_id == product.id,
            SellingPrice.valid_to.is_(None),
            SellingPrice.deleted_at.is_(None),
        )
    )
    if not price:
        return False

    qty = Decimal("2")
    line_sub, line_tax, line_total = _totals(qty, int(price))
    invoice.lines.append(
        InvoiceLine(
            product_id=product.id,
            qty=qty,
            unit_price_minor=int(price),
            tax_rate_bps=invoice.lines[0].tax_rate_bps,
            line_subtotal_minor=line_sub,
            line_tax_minor=line_tax,
            line_total_minor=line_total,
            line_no=len(invoice.lines) + 1,
            created_by=ctx.actor_id,
        )
    )
    invoice.subtotal_minor += line_sub
    invoice.tax_minor += line_tax
    invoice.total_minor += line_total
    db.flush()
    return True
