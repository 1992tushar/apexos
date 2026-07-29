"""Part 8 C1's seed section: an ageing screen worth looking at (G14).

Before this, the demo data held **one** invoice, **one** bill and **one** credit note. An
AR ageing screen over one part-paid invoice shows one row in one bucket, which cannot
demonstrate anything and — worse — cannot fail visibly when the bucket arithmetic is
wrong. G14 asks for edge cases, not a happy row, so the documents below are placed by
*offset from the report date* to land one in every bucket, including the two edges that
R10.6 turns on:

* an invoice due **exactly today** — `days_overdue == 0`, which is NOT overdue, and
* an invoice with **no due date at all**, aged from its invoice date instead.

Also seeded: a fully-settled invoice (so the screens must exclude it), a part-paid one
(so "paid" and "open" are visibly different numbers), and a customer whose only invoice
is not yet due (so the collections list must leave them off).

**Invoices are written DIRECTLY**, not through the sell loop. `sales_order_id` is
nullable, and going through confirm → fulfil → invoice would need stock, reservations and
a credit policy per customer, and would leave OPEN sales orders behind — the trap that has
broken the same two Part 1/3 tests three times. The customers used are chosen from the
middle of the bulk-generated list for the same reason: the first few are the subjects other
tests assert are quiet.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.money import round_minor
from app.modules.config.service import allocate_document_number, default_business_unit
from app.modules.customers.models import Customer
from app.modules.finance.models import (
    Bill,
    BillLine,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentAllocation,
)
from app.modules.pricing.models import SellingPrice
from app.modules.suppliers.models import Supplier
from app.seed.helpers import SeedContext

#: One tax rate for the seeded documents. Integer basis points, and the tax is computed
#: through `round_minor` — the ONE rounding step (G1) — never through a float.
_TAX_BPS = 1800

#: Customers to skip before picking subjects. The first few carry the spine sales order
#: and the Part 6/7 demo documents, and several tests assert their work is all closed.
_CUSTOMER_OFFSET = 5

#: (label, days until due, qty, paid fraction in percent, has_due_date)
#:
#: Negative "days until due" is in the past, so the document is overdue by that many days.
#: The offsets are chosen to sit well inside each bucket rather than on its edge — except
#: `due today`, which IS the edge R10.6 is about.
_INVOICE_PLAN: tuple[tuple[str, int, str, int, bool], ...] = (
    ("Overdue 120 days — the oldest thing on the books", -120, "12", 0, True),
    ("Overdue 75 days — part paid, so open < total", -75, "20", 40, True),
    ("Overdue 45 days", -45, "8", 0, True),
    ("Overdue 10 days", -10, "15", 0, True),
    ("Due exactly today — the R10.6 boundary, NOT overdue", 0, "10", 0, True),
    ("Due in 20 days — not yet due, so not a collection", 20, "25", 0, True),
    ("No due date recorded — aged from the invoice date", -40, "6", 0, False),
    ("Settled in full — must not appear on any ageing screen", -60, "5", 100, True),
)

#: (label, days until due, qty, paid fraction in percent)
_BILL_PLAN: tuple[tuple[str, int, str, int], ...] = (
    ("Overdue 50 days — the one to pay first", -50, "30", 0),
    ("Due exactly today", 0, "18", 0),
    ("Due in 15 days — part paid", 15, "22", 50),
)


def seed_finance(ctx: SeedContext) -> dict | None:
    """Invoices and bills spread across every ageing bucket (R10.5, R10.6, G14).

    Guarded on its own emptiness check — the marker is a direct invoice, one with no
    `sales_order_id`, so re-running never doubles the demo set.
    """
    db = ctx.db
    already = db.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.sales_order_id.is_(None))
    ) or 0
    if already:
        return None

    bu_id = default_business_unit(db)
    today = date.today()

    customers = list(
        db.scalars(
            select(Customer)
            .where(Customer.deleted_at.is_(None))
            .order_by(Customer.code)
            .offset(_CUSTOMER_OFFSET)
            .limit(4)
        )
    )
    priced = db.execute(
        select(SellingPrice.product_id, SellingPrice.price_minor)
        .where(SellingPrice.deleted_at.is_(None), SellingPrice.price_minor > 0)
        .order_by(SellingPrice.price_minor.desc())
        .limit(4)
    ).all()
    suppliers = list(
        db.scalars(
            select(Supplier)
            .where(Supplier.deleted_at.is_(None))
            .order_by(Supplier.code)
            .limit(2)
        )
    )
    if len(customers) < 3 or len(priced) < 2 or not suppliers:
        return None

    made: dict[str, str | int | None] = {}
    invoice_nos: list[str] = []

    for index, (label, days, qty, paid_pct, has_due) in enumerate(_INVOICE_PLAN):
        customer = customers[index % len(customers)]
        product_id, unit_price = priced[index % len(priced)]
        due = today + timedelta(days=days)
        # Issued 30 days before it fell due, which is what any real terms would produce.
        issued = due - timedelta(days=30)

        invoice = _make_invoice(
            ctx,
            bu_id=bu_id,
            customer_id=customer.id,
            invoice_date=issued,
            due_date=due if has_due else None,
            product_id=product_id,
            qty=Decimal(qty),
            unit_price_minor=int(unit_price),
        )
        if paid_pct:
            _pay_invoice(ctx, invoice, paid_pct)
        invoice_nos.append(f"{invoice.invoice_no} ({label})")

    bill_nos: list[str] = []
    for index, (label, days, qty, paid_pct) in enumerate(_BILL_PLAN):
        supplier = suppliers[index % len(suppliers)]
        product_id, unit_price = priced[index % len(priced)]
        due = today + timedelta(days=days)
        bill = _make_bill(
            ctx,
            bu_id=bu_id,
            supplier_id=supplier.id,
            bill_date=due - timedelta(days=30),
            due_date=due,
            product_id=product_id,
            # Bought below the selling price, so C3's margin work has a real spread.
            unit_price_minor=int(Decimal(unit_price) * Decimal("0.7")),
            qty=Decimal(qty),
        )
        if paid_pct:
            _pay_bill(ctx, bill, paid_pct)
        bill_nos.append(f"{bill.bill_no} ({label})")

    db.flush()
    made["invoices"] = "; ".join(invoice_nos)
    made["bills"] = "; ".join(bill_nos)
    return made


def _totals(qty: Decimal, unit_price_minor: int) -> tuple[int, int, int]:
    """Subtotal, tax and total in integer minor units, rounded through the ONE step."""
    subtotal = round_minor(qty * Decimal(unit_price_minor))
    tax = round_minor(Decimal(subtotal) * Decimal(_TAX_BPS) / Decimal(10000))
    return subtotal, tax, subtotal + tax


def _make_invoice(
    ctx: SeedContext,
    *,
    bu_id,
    customer_id,
    invoice_date: date,
    due_date: date | None,
    product_id,
    qty: Decimal,
    unit_price_minor: int,
) -> Invoice:
    subtotal, tax, total = _totals(qty, unit_price_minor)
    invoice = Invoice(
        customer_id=customer_id,
        sales_order_id=None,
        invoice_no=allocate_document_number(
            ctx.db, doc_type="INV", business_unit_id=bu_id, on_date=invoice_date
        ),
        invoice_date=invoice_date,
        due_date=due_date,
        status="issued",
        subtotal_minor=subtotal,
        tax_minor=tax,
        total_minor=total,
        business_unit_id=bu_id,
        created_by=ctx.actor_id,
    )
    invoice.lines.append(
        InvoiceLine(
            product_id=product_id,
            qty=qty,
            unit_price_minor=unit_price_minor,
            tax_rate_bps=_TAX_BPS,
            line_subtotal_minor=subtotal,
            line_tax_minor=tax,
            line_total_minor=total,
            line_no=1,
            created_by=ctx.actor_id,
        )
    )
    ctx.db.add(invoice)
    ctx.db.flush()
    return invoice


def _make_bill(
    ctx: SeedContext,
    *,
    bu_id,
    supplier_id,
    bill_date: date,
    due_date: date,
    product_id,
    qty: Decimal,
    unit_price_minor: int,
) -> Bill:
    subtotal, tax, total = _totals(qty, unit_price_minor)
    bill = Bill(
        supplier_id=supplier_id,
        purchase_order_id=None,
        bill_no=allocate_document_number(
            ctx.db, doc_type="BILL", business_unit_id=bu_id, on_date=bill_date
        ),
        bill_date=bill_date,
        due_date=due_date,
        status="issued",
        subtotal_minor=subtotal,
        tax_minor=tax,
        total_minor=total,
        business_unit_id=bu_id,
        created_by=ctx.actor_id,
    )
    bill.lines.append(
        BillLine(
            product_id=product_id,
            qty=qty,
            unit_price_minor=unit_price_minor,
            tax_rate_bps=_TAX_BPS,
            line_subtotal_minor=subtotal,
            line_tax_minor=tax,
            line_total_minor=total,
            line_no=1,
            created_by=ctx.actor_id,
        )
    )
    ctx.db.add(bill)
    ctx.db.flush()
    return bill


def _payment_no(ctx: SeedContext) -> str:
    n = (ctx.db.scalar(select(func.count()).select_from(Payment)) or 0) + 1
    return f"PAY-{n:05d}"


def _pay_invoice(ctx: SeedContext, invoice: Invoice, percent: int) -> None:
    """Apply `percent` of the invoice as a receipt — integer arithmetic (G1).

    Written as a `Payment` + `PaymentAllocation`, which is the only way money is ever
    applied: the invoice is not edited (G4) and its `status` is the documented cache of the
    derived balance, nothing more.
    """
    amount = invoice.total_minor * percent // 100
    if amount <= 0:
        return
    payment = Payment(
        direction="in",
        customer_id=invoice.customer_id,
        payment_no=_payment_no(ctx),
        amount_minor=amount,
        method="bank",
        created_by=ctx.actor_id,
    )
    payment.allocations.append(
        PaymentAllocation(invoice_id=invoice.id, amount_minor=amount, created_by=ctx.actor_id)
    )
    ctx.db.add(payment)
    invoice.status = "paid" if amount >= invoice.total_minor else "part_paid"
    ctx.db.flush()


def _pay_bill(ctx: SeedContext, bill: Bill, percent: int) -> None:
    amount = bill.total_minor * percent // 100
    if amount <= 0:
        return
    payment = Payment(
        direction="out",
        supplier_id=bill.supplier_id,
        payment_no=_payment_no(ctx),
        amount_minor=amount,
        method="bank",
        created_by=ctx.actor_id,
    )
    payment.allocations.append(
        PaymentAllocation(bill_id=bill.id, amount_minor=amount, created_by=ctx.actor_id)
    )
    ctx.db.add(payment)
    bill.status = "paid" if amount >= bill.total_minor else "part_paid"
    ctx.db.flush()
