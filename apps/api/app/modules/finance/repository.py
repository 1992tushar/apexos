"""Finance repository."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.customers.models import Customer
from app.modules.finance.models import (
    Bill,
    CreditNote,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentAllocation,
)
from app.modules.suppliers.models import Supplier


class FinanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_payment(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def get(self, invoice_id: uuid.UUID) -> Invoice | None:
        return self.db.scalar(
            select(Invoice)
            .options(selectinload(Invoice.lines))
            .where(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
        )

    def customer_name(self, customer_id: uuid.UUID) -> str | None:
        return self.db.scalar(select(Customer.name).where(Customer.id == customer_id))

    def allocated_minor(self, invoice_id: uuid.UUID) -> int:
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(PaymentAllocation.amount_minor), 0)).where(
                    PaymentAllocation.invoice_id == invoice_id
                )
            )
            or 0
        )

    def credited_minor(self, invoice_id: uuid.UUID) -> int:
        """Σ credit notes raised against one invoice.

        The third term of an invoice's open balance. It was missing from
        `InvoiceService`'s `balance_minor` until Part 8 C1, which meant an invoice reduced
        by a return showed a balance the customer did not owe — and `add_payment` would
        have accepted a payment for it.
        """
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(CreditNote.total_minor), 0)).where(
                    CreditNote.invoice_id == invoice_id, CreditNote.deleted_at.is_(None)
                )
            )
            or 0
        )

    def search(self, *, status: str | None, page: int, page_size: int) -> tuple[list[Invoice], int]:
        base = select(Invoice).where(Invoice.deleted_at.is_(None))
        if status:
            base = base.where(Invoice.status == status)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = list(
            self.db.scalars(
                base.order_by(Invoice.invoice_date.desc(), Invoice.invoice_no.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total

    def next_payment_no(self) -> str:
        n = (
            self.db.scalar(select(func.count()).select_from(Payment)) or 0
        ) + 1
        return f"PAY-{n:05d}"

    def outstanding_total(self) -> int:
        """Σ over non-cancelled invoices of (total − allocated)."""
        invoiced = self.db.scalar(
            select(func.coalesce(func.sum(Invoice.total_minor), 0)).where(
                Invoice.status != "cancelled", Invoice.deleted_at.is_(None)
            )
        ) or 0
        allocated = self.db.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.amount_minor), 0))
            .select_from(PaymentAllocation)
            .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
            .where(Invoice.status != "cancelled")
        ) or 0
        return int(invoiced) - int(allocated)

    # --- bills (buy side) ----------------------------------------------
    def add_bill(self, bill: Bill) -> Bill:
        self.db.add(bill)
        self.db.flush()
        return bill

    def get_bill(self, bill_id: uuid.UUID) -> Bill | None:
        return self.db.scalar(
            select(Bill)
            .options(selectinload(Bill.lines))
            .where(Bill.id == bill_id, Bill.deleted_at.is_(None))
        )

    def supplier_name(self, supplier_id: uuid.UUID) -> str | None:
        return self.db.scalar(select(Supplier.name).where(Supplier.id == supplier_id))

    def bill_allocated_minor(self, bill_id: uuid.UUID) -> int:
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(PaymentAllocation.amount_minor), 0)).where(
                    PaymentAllocation.bill_id == bill_id
                )
            )
            or 0
        )

    def search_bills(
        self, *, status: str | None, page: int, page_size: int
    ) -> tuple[list[Bill], int]:
        base = select(Bill).where(Bill.deleted_at.is_(None))
        if status:
            base = base.where(Bill.status == status)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = list(
            self.db.scalars(
                base.order_by(Bill.bill_date.desc(), Bill.bill_no.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total

    def payable_total(self) -> int:
        """Σ over non-cancelled bills of (total − allocated)."""
        billed = self.db.scalar(
            select(func.coalesce(func.sum(Bill.total_minor), 0)).where(
                Bill.status != "cancelled", Bill.deleted_at.is_(None)
            )
        ) or 0
        allocated = self.db.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.amount_minor), 0))
            .select_from(PaymentAllocation)
            .join(Bill, Bill.id == PaymentAllocation.bill_id)
            .where(Bill.status != "cancelled")
        ) or 0
        return int(billed) - int(allocated)

    # --- Part 8 C1: the grouped reads the projections are built on (R10.x) ----
    #
    # Every method below is GROUPED. An AR ageing screen over hundreds of invoices is a
    # handful of queries, not a `select()` per row — the per-document open balance needs
    # three sums, so they are fetched as three dicts and joined in Python.

    def invoices_with_party(
        self, *, customer_id: uuid.UUID | None = None
    ) -> list[tuple[Invoice, str | None]]:
        """Live, non-cancelled invoices with their customer's name, oldest first.

        The same status/`deleted_at` filters `CustomerRepository.outstanding_minor` puts on
        its invoice term, so the per-invoice breakdown and the party total are talking
        about the same set of documents.
        """
        stmt = (
            select(Invoice, Customer.name)
            .join(Customer, Customer.id == Invoice.customer_id)
            .where(Invoice.status != "cancelled", Invoice.deleted_at.is_(None))
            .order_by(Invoice.invoice_date, Invoice.invoice_no)
        )
        if customer_id is not None:
            stmt = stmt.where(Invoice.customer_id == customer_id)
        return [(inv, name) for inv, name in self.db.execute(stmt).all()]

    def bills_with_party(
        self, *, supplier_id: uuid.UUID | None = None
    ) -> list[tuple[Bill, str | None]]:
        """Live, non-cancelled bills with their supplier's name, oldest first."""
        stmt = (
            select(Bill, Supplier.name)
            .join(Supplier, Supplier.id == Bill.supplier_id)
            .where(Bill.status != "cancelled", Bill.deleted_at.is_(None))
            .order_by(Bill.bill_date, Bill.bill_no)
        )
        if supplier_id is not None:
            stmt = stmt.where(Bill.supplier_id == supplier_id)
        return [(bill, name) for bill, name in self.db.execute(stmt).all()]

    def allocated_by_invoice(self) -> dict[uuid.UUID, int]:
        rows = self.db.execute(
            select(
                PaymentAllocation.invoice_id,
                func.coalesce(func.sum(PaymentAllocation.amount_minor), 0),
            )
            .where(PaymentAllocation.invoice_id.is_not(None))
            .group_by(PaymentAllocation.invoice_id)
        ).all()
        return {invoice_id: int(amount or 0) for invoice_id, amount in rows}

    def allocated_by_bill(self) -> dict[uuid.UUID, int]:
        rows = self.db.execute(
            select(
                PaymentAllocation.bill_id,
                func.coalesce(func.sum(PaymentAllocation.amount_minor), 0),
            )
            .where(PaymentAllocation.bill_id.is_not(None))
            .group_by(PaymentAllocation.bill_id)
        ).all()
        return {bill_id: int(amount or 0) for bill_id, amount in rows}

    def credited_by_invoice(self) -> dict[uuid.UUID, int]:
        rows = self.db.execute(
            select(CreditNote.invoice_id, func.coalesce(func.sum(CreditNote.total_minor), 0))
            .where(CreditNote.deleted_at.is_(None))
            .group_by(CreditNote.invoice_id)
        ).all()
        return {invoice_id: int(amount or 0) for invoice_id, amount in rows}

    # --- statement sources (R10.4 — all four document types) -----------------

    def credit_notes_for_customer(self, customer_id: uuid.UUID) -> list[CreditNote]:
        return list(
            self.db.scalars(
                select(CreditNote)
                .where(CreditNote.customer_id == customer_id, CreditNote.deleted_at.is_(None))
                .order_by(CreditNote.note_date, CreditNote.credit_note_no)
            )
        )

    def credit_notes_for_invoice(self, invoice_id: uuid.UUID) -> list[CreditNote]:
        """The credits applied to one invoice — R10.3's drill-through target.

        Before Part 8 a credit note rendered only on the customer page, so an invoice
        whose balance had been reduced by one gave no way to see why.
        """
        return list(
            self.db.scalars(
                select(CreditNote)
                .where(CreditNote.invoice_id == invoice_id, CreditNote.deleted_at.is_(None))
                .order_by(CreditNote.note_date, CreditNote.credit_note_no)
            )
        )

    def customer_allocations(
        self, customer_id: uuid.UUID
    ) -> list[tuple[PaymentAllocation, Payment, str]]:
        """Every allocation against this customer's invoices, with its payment and the
        invoice number it landed on.

        No `Invoice.status` or `deleted_at` filter, matching `outstanding_minor`'s
        allocation term exactly — so the statement's closing balance is that method's
        figure and not an approximation of it.
        """
        rows = self.db.execute(
            select(PaymentAllocation, Payment, Invoice.invoice_no)
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
            .where(Invoice.customer_id == customer_id)
            .order_by(Payment.paid_at, Payment.payment_no, Invoice.invoice_no)
        ).all()
        return [(alloc, payment, invoice_no) for alloc, payment, invoice_no in rows]

    def supplier_allocations(
        self, supplier_id: uuid.UUID
    ) -> list[tuple[PaymentAllocation, Payment, str]]:
        rows = self.db.execute(
            select(PaymentAllocation, Payment, Bill.bill_no)
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .join(Bill, Bill.id == PaymentAllocation.bill_id)
            .where(Bill.supplier_id == supplier_id)
            .order_by(Payment.paid_at, Payment.payment_no, Bill.bill_no)
        ).all()
        return [(alloc, payment, bill_no) for alloc, payment, bill_no in rows]

    def allocations_for_invoice(
        self, invoice_id: uuid.UUID
    ) -> list[tuple[PaymentAllocation, Payment]]:
        """The payments applied to one invoice — R10.3's other drill-through gap.

        Payments have no page of their own, so "what was applied to this invoice" belongs
        on the invoice, which is where the founder is already standing.
        """
        rows = self.db.execute(
            select(PaymentAllocation, Payment)
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .where(PaymentAllocation.invoice_id == invoice_id)
            .order_by(Payment.paid_at, Payment.payment_no)
        ).all()
        return [(alloc, payment) for alloc, payment in rows]

    def allocations_for_bill(self, bill_id: uuid.UUID) -> list[tuple[PaymentAllocation, Payment]]:
        rows = self.db.execute(
            select(PaymentAllocation, Payment)
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .where(PaymentAllocation.bill_id == bill_id)
            .order_by(Payment.paid_at, Payment.payment_no)
        ).all()
        return [(alloc, payment) for alloc, payment in rows]

    # --- Part 8 C2: the flow reads (R11.1–R11.4) -----------------------------
    #
    # C1's reads are point-in-time ("what is open now"); these are WINDOWED ("what moved
    # between two dates"). `func.date(...)` on the datetime column is the house pattern —
    # `ReportService._stock_ledger` does the same, and it keeps the comparison a date
    # comparison rather than depending on how the driver stores a timezone.

    def payments_between(
        self, date_from: date, date_to: date
    ) -> list[tuple[str, date, int]]:
        """(direction, paid-on date, amount) for every payment in the window.

        **Payments are the only actual cash movement in the system.** There is no bank
        ledger, so "cash in" is what was received and "cash out" is what was paid — not an
        accrual, and the screens say so.
        """
        rows = self.db.execute(
            select(Payment.direction, func.date(Payment.paid_at), Payment.amount_minor)
            .where(
                func.date(Payment.paid_at) >= date_from,
                func.date(Payment.paid_at) <= date_to,
                Payment.deleted_at.is_(None),
            )
            .order_by(func.date(Payment.paid_at), Payment.payment_no)
        ).all()
        out: list[tuple[str, date, int]] = []
        for direction, paid_on, amount in rows:
            # SQLite's `date()` hands back text; Postgres hands back a `date`.
            stamp = paid_on if isinstance(paid_on, date) else date.fromisoformat(str(paid_on))
            out.append((str(direction), stamp, int(amount or 0)))
        return out

    def invoiced_between(self, date_from: date, date_to: date) -> tuple[int, int]:
        """(subtotal, total) invoiced in the window — DSO's revenue denominator.

        Subtotal as well as total because margin works on the tax-exclusive figure: GST is
        collected on the customer's behalf, not earned, so it has no place in COGS or in a
        margin ratio.
        """
        row = self.db.execute(
            select(
                func.coalesce(func.sum(Invoice.subtotal_minor), 0),
                func.coalesce(func.sum(Invoice.total_minor), 0),
            ).where(
                Invoice.invoice_date >= date_from,
                Invoice.invoice_date <= date_to,
                Invoice.status != "cancelled",
                Invoice.deleted_at.is_(None),
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    def billed_between(self, date_from: date, date_to: date) -> tuple[int, int]:
        """(subtotal, total) billed in the window — DPO's purchases denominator."""
        row = self.db.execute(
            select(
                func.coalesce(func.sum(Bill.subtotal_minor), 0),
                func.coalesce(func.sum(Bill.total_minor), 0),
            ).where(
                Bill.bill_date >= date_from,
                Bill.bill_date <= date_to,
                Bill.status != "cancelled",
                Bill.deleted_at.is_(None),
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    def invoice_lines_between(self, date_from: date, date_to: date) -> list[InvoiceLine]:
        """The lines behind the window's revenue — COGS is derived from these.

        One query with the join, not a query per invoice.
        """
        return list(
            self.db.scalars(
                select(InvoiceLine)
                .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
                .where(
                    Invoice.invoice_date >= date_from,
                    Invoice.invoice_date <= date_to,
                    Invoice.status != "cancelled",
                    Invoice.deleted_at.is_(None),
                    InvoiceLine.deleted_at.is_(None),
                )
            )
        )

    def margin_lines_between(
        self, date_from: date, date_to: date
    ) -> list[tuple[InvoiceLine, Invoice, str, str, uuid.UUID, str | None]]:
        """Every live invoice line in the window with what the four dimensions need.

        ONE query with the joins rather than a lookup per line: `(line, invoice, product
        name, sku, category_id, customer name)`. The category comes off the product because
        that is where it lives; the customer and business unit come off the invoice.
        """
        from app.modules.products.models import Product

        rows = self.db.execute(
            select(
                InvoiceLine,
                Invoice,
                Product.name,
                Product.sku_code,
                Product.category_id,
                Customer.name,
            )
            .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
            .join(Product, Product.id == InvoiceLine.product_id)
            .outerjoin(Customer, Customer.id == Invoice.customer_id)
            .where(
                Invoice.invoice_date >= date_from,
                Invoice.invoice_date <= date_to,
                Invoice.status != "cancelled",
                Invoice.deleted_at.is_(None),
                InvoiceLine.deleted_at.is_(None),
            )
            .order_by(Invoice.invoice_date, Invoice.invoice_no, InvoiceLine.line_no)
        ).all()
        return [tuple(row) for row in rows]

    def category_names(self) -> dict[uuid.UUID, str]:
        from app.modules.config.models import Category

        rows = self.db.execute(select(Category.id, Category.name)).all()
        return {row[0]: row[1] for row in rows}

    def business_unit_names(self) -> dict[uuid.UUID, str]:
        from app.modules.config.models import BusinessUnit

        rows = self.db.execute(select(BusinessUnit.id, BusinessUnit.name)).all()
        return {row[0]: row[1] for row in rows}

    def list_prices(self) -> dict[uuid.UUID, int]:
        """`{product_id: list price}` — the CURRENT row with no customer and no segment.

        The baseline discount creep is measured against (R11.7). There is no discount column
        anywhere in the schema, so "how much was given away" can only be the gap between what
        was charged and the price the product is listed at. A product with no such row has an
        UNKNOWN discount, not a zero one, and is therefore absent from this map rather than
        present with a zero.
        """
        from app.modules.pricing.models import SellingPrice

        rows = self.db.execute(
            select(SellingPrice.product_id, SellingPrice.price_minor)
            .where(
                SellingPrice.customer_id.is_(None),
                SellingPrice.customer_type_id.is_(None),
                SellingPrice.valid_to.is_(None),
                SellingPrice.deleted_at.is_(None),
            )
            .order_by(SellingPrice.product_id, SellingPrice.valid_from.desc())
        ).all()
        out: dict[uuid.UUID, int] = {}
        for product_id, price in rows:
            out.setdefault(product_id, int(price))
        return out

    def purchase_prices_by_product(self) -> dict[uuid.UUID, int]:
        """`{product_id: current buy price}`. **A bare delegation — not a second query.**

        Part 8 built this query here because finance was its only consumer. Part 10's R13.1
        audit found three consumers in three modules, so the implementation moved to
        `PricingRepository`, which owns `PurchasePrice`. This name survives because Part 8's
        callers and tests use it, and a delegation costs nothing (R13.2, R13.6's precedent).

        Prefer `MarginService.gp_costed`, which applies the map rather than handing it to you.
        """
        from app.modules.pricing.repository import PricingRepository

        return PricingRepository(self.db).purchase_prices_by_product()

    def invoice_tax_rows_between(
        self, date_from: date, date_to: date
    ) -> list[tuple[date, int, int]]:
        """(invoice date, subtotal, tax) for the GST summary's output side (R11.9)."""
        rows = self.db.execute(
            select(Invoice.invoice_date, Invoice.subtotal_minor, Invoice.tax_minor).where(
                Invoice.invoice_date >= date_from,
                Invoice.invoice_date <= date_to,
                Invoice.status != "cancelled",
                Invoice.deleted_at.is_(None),
            )
        ).all()
        return [(row[0], int(row[1] or 0), int(row[2] or 0)) for row in rows]

    def bill_tax_rows_between(self, date_from: date, date_to: date) -> list[tuple[date, int, int]]:
        """(bill date, subtotal, tax) for the GST summary's input side (R11.9)."""
        rows = self.db.execute(
            select(Bill.bill_date, Bill.subtotal_minor, Bill.tax_minor).where(
                Bill.bill_date >= date_from,
                Bill.bill_date <= date_to,
                Bill.status != "cancelled",
                Bill.deleted_at.is_(None),
            )
        ).all()
        return [(row[0], int(row[1] or 0), int(row[2] or 0)) for row in rows]

    def sales_pipeline(self) -> tuple[int, int]:
        """(count, total) of orders confirmed but NOT yet invoiced.

        Money we expect to receive but cannot date: an order carries no due date, and one is
        only created when it is invoiced. That is exactly why R11.2's committed figure
        excludes this and reports it separately — see `cash.py`.
        """
        from app.modules.sales.models import SalesOrder

        row = self.db.execute(
            select(func.count(), func.coalesce(func.sum(SalesOrder.total_minor), 0)).where(
                SalesOrder.status.in_(("confirmed", "partially_fulfilled", "fulfilled")),
                SalesOrder.deleted_at.is_(None),
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    def purchase_pipeline(self) -> tuple[int, int]:
        """(count, total) of purchase orders confirmed but NOT yet billed."""
        from app.modules.procurement.models import PurchaseOrder

        row = self.db.execute(
            select(func.count(), func.coalesce(func.sum(PurchaseOrder.total_minor), 0)).where(
                PurchaseOrder.status.in_(
                    ("confirmed", "partially_received", "received")
                ),
                PurchaseOrder.deleted_at.is_(None),
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    def customers_with_activity(self) -> list[tuple[uuid.UUID, str]]:
        """(id, name) for every customer that has at least one live invoice.

        The ledger picker's option list: a customer who has never been invoiced has an
        empty statement, and offering all 268 of them buries the handful that matter.
        """
        rows = self.db.execute(
            select(Customer.id, Customer.name)
            .join(Invoice, Invoice.customer_id == Customer.id)
            .where(Invoice.deleted_at.is_(None), Customer.deleted_at.is_(None))
            .group_by(Customer.id, Customer.name)
            .order_by(Customer.name)
        ).all()
        return [(row[0], row[1]) for row in rows]

    def suppliers_with_activity(self) -> list[tuple[uuid.UUID, str]]:
        rows = self.db.execute(
            select(Supplier.id, Supplier.name)
            .join(Bill, Bill.supplier_id == Supplier.id)
            .where(Bill.deleted_at.is_(None), Supplier.deleted_at.is_(None))
            .group_by(Supplier.id, Supplier.name)
            .order_by(Supplier.name)
        ).all()
        return [(row[0], row[1]) for row in rows]
