"""Invoice / payment service. Receivable is derived; invoice.status is a cached
convenience transitioning issued → part_paid → paid."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.activity.service import ActivityService
from app.modules.finance.models import Bill, Invoice, Payment, PaymentAllocation
from app.modules.finance.repository import FinanceRepository
from app.modules.finance.schemas import (
    BillDetail,
    BillLineRead,
    BillListRow,
    BillPaymentCreate,
    BillPaymentResult,
    InvoiceDetail,
    InvoiceLineRead,
    InvoiceListRow,
    PaymentCreate,
    PaymentResult,
)
from app.modules.products.models import Product


class InvoiceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FinanceRepository(db)
        self.activity = ActivityService(db)

    def list(self, *, status: str | None, page: int, page_size: int):
        rows, total = self.repo.search(status=status, page=page, page_size=page_size)
        # Two grouped reads rather than two queries per row — the same dicts the Part 8
        # projections are built on, so this page and the ageing screen agree by sharing
        # their arithmetic instead of each doing it.
        allocated = self.repo.allocated_by_invoice()
        credited = self.repo.credited_by_invoice()
        items = []
        for inv in rows:
            paid = allocated.get(inv.id, 0)
            credit = credited.get(inv.id, 0)
            items.append(
                InvoiceListRow(
                    id=inv.id,
                    invoice_no=inv.invoice_no,
                    customer_name=self.repo.customer_name(inv.customer_id),
                    total_minor=inv.total_minor,
                    paid_minor=paid,
                    credited_minor=credit,
                    balance_minor=inv.total_minor - paid - credit,
                    status=inv.status,
                    invoice_date=inv.invoice_date,
                    due_date=inv.due_date,
                )
            )
        return items, total

    def _to_detail(self, inv: Invoice) -> InvoiceDetail:
        paid = self.repo.allocated_minor(inv.id)
        credited = self.repo.credited_minor(inv.id)
        lines = []
        for ln in inv.lines:
            product = self.db.get(Product, ln.product_id)
            lines.append(
                InvoiceLineRead(
                    id=ln.id,
                    product_id=ln.product_id,
                    product_name=product.name if product else None,
                    qty=ln.qty,
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                )
            )
        return InvoiceDetail(
            id=inv.id,
            invoice_no=inv.invoice_no,
            customer_id=inv.customer_id,
            customer_name=self.repo.customer_name(inv.customer_id),
            sales_order_id=inv.sales_order_id,
            status=inv.status,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            subtotal_minor=inv.subtotal_minor,
            tax_minor=inv.tax_minor,
            total_minor=inv.total_minor,
            paid_minor=paid,
            credited_minor=credited,
            balance_minor=inv.total_minor - paid - credited,
            lines=lines,
        )

    def get(self, invoice_id: uuid.UUID) -> InvoiceDetail:
        inv = self.repo.get(invoice_id)
        if inv is None:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        return self._to_detail(inv)

    def add_payment(
        self, invoice_id: uuid.UUID, payload: PaymentCreate, *, actor_id: uuid.UUID | None
    ) -> PaymentResult:
        inv = self.repo.get(invoice_id)
        if inv is None:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        if inv.status == "paid":
            raise ConflictError(f"Invoice {inv.invoice_no} is already fully paid")

        already = self.repo.allocated_minor(inv.id)
        # The credit-note term (R10.4): an invoice reduced by a return owes less than
        # `total − paid`, and accepting a payment for the difference would collect money
        # the customer does not owe. One definition of an invoice's open balance.
        credited = self.repo.credited_minor(inv.id)
        balance = inv.total_minor - already - credited
        if payload.amount_minor > balance:
            raise ValidationError(
                f"Payment {payload.amount_minor} exceeds outstanding balance {balance}"
            )

        payment = Payment(
            direction="in",
            customer_id=inv.customer_id,
            payment_no=self.repo.next_payment_no(),
            amount_minor=payload.amount_minor,
            method=payload.method,
            created_by=actor_id,
        )
        payment.allocations.append(
            PaymentAllocation(
                invoice_id=inv.id, amount_minor=payload.amount_minor, created_by=actor_id
            )
        )
        self.repo.add_payment(payment)

        new_paid = already + payload.amount_minor
        inv.status = "paid" if new_paid >= inv.total_minor - credited else "part_paid"
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="payment_received",
            entity_type="invoice",
            entity_id=inv.id,
            summary=f"Payment {payment.payment_no} of {payload.amount_minor} minor on {inv.invoice_no}",
            data={"amount_minor": payload.amount_minor, "invoice_status": inv.status},
        )
        return PaymentResult(
            payment_id=payment.id,
            payment_no=payment.payment_no,
            invoice_id=inv.id,
            amount_minor=payload.amount_minor,
            invoice_status=inv.status,
            balance_minor=inv.total_minor - new_paid - credited,
        )


class BillService:
    """Supplier-bill reads + outbound payments — the buy-side mirror of
    InvoiceService. Payable is derived; `bill.status` caches issued → part_paid →
    paid. Bills are issued from a purchase order by `PurchaseOrderService.bill`."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = FinanceRepository(db)
        self.activity = ActivityService(db)

    def list(self, *, status: str | None, page: int, page_size: int):
        rows, total = self.repo.search_bills(status=status, page=page, page_size=page_size)
        items = []
        for bill in rows:
            paid = self.repo.bill_allocated_minor(bill.id)
            items.append(
                BillListRow(
                    id=bill.id,
                    bill_no=bill.bill_no,
                    supplier_name=self.repo.supplier_name(bill.supplier_id),
                    total_minor=bill.total_minor,
                    paid_minor=paid,
                    balance_minor=bill.total_minor - paid,
                    status=bill.status,
                    bill_date=bill.bill_date,
                    due_date=bill.due_date,
                )
            )
        return items, total

    def _to_detail(self, bill: Bill) -> BillDetail:
        paid = self.repo.bill_allocated_minor(bill.id)
        lines = []
        for ln in bill.lines:
            product = self.db.get(Product, ln.product_id)
            lines.append(
                BillLineRead(
                    id=ln.id,
                    product_id=ln.product_id,
                    product_name=product.name if product else None,
                    qty=ln.qty,
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                )
            )
        return BillDetail(
            id=bill.id,
            bill_no=bill.bill_no,
            supplier_id=bill.supplier_id,
            supplier_name=self.repo.supplier_name(bill.supplier_id),
            purchase_order_id=bill.purchase_order_id,
            status=bill.status,
            bill_date=bill.bill_date,
            due_date=bill.due_date,
            subtotal_minor=bill.subtotal_minor,
            tax_minor=bill.tax_minor,
            total_minor=bill.total_minor,
            paid_minor=paid,
            balance_minor=bill.total_minor - paid,
            lines=lines,
        )

    def get(self, bill_id: uuid.UUID) -> BillDetail:
        bill = self.repo.get_bill(bill_id)
        if bill is None:
            raise NotFoundError(f"Bill {bill_id} not found")
        return self._to_detail(bill)

    def add_payment(
        self, bill_id: uuid.UUID, payload: BillPaymentCreate, *, actor_id: uuid.UUID | None
    ) -> BillPaymentResult:
        bill = self.repo.get_bill(bill_id)
        if bill is None:
            raise NotFoundError(f"Bill {bill_id} not found")
        if bill.status == "paid":
            raise ConflictError(f"Bill {bill.bill_no} is already fully paid")

        already = self.repo.bill_allocated_minor(bill.id)
        balance = bill.total_minor - already
        if payload.amount_minor > balance:
            raise ValidationError(
                f"Payment {payload.amount_minor} exceeds outstanding balance {balance}"
            )

        payment = Payment(
            direction="out",
            supplier_id=bill.supplier_id,
            payment_no=self.repo.next_payment_no(),
            amount_minor=payload.amount_minor,
            method=payload.method,
            created_by=actor_id,
        )
        payment.allocations.append(
            PaymentAllocation(
                bill_id=bill.id, amount_minor=payload.amount_minor, created_by=actor_id
            )
        )
        self.repo.add_payment(payment)

        new_paid = already + payload.amount_minor
        bill.status = "paid" if new_paid >= bill.total_minor else "part_paid"
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="payment_made",
            entity_type="bill",
            entity_id=bill.id,
            summary=f"Payment {payment.payment_no} of {payload.amount_minor} minor on {bill.bill_no}",
            data={"amount_minor": payload.amount_minor, "bill_status": bill.status},
        )
        return BillPaymentResult(
            payment_id=payment.id,
            payment_no=payment.payment_no,
            bill_id=bill.id,
            amount_minor=payload.amount_minor,
            bill_status=bill.status,
            balance_minor=bill.total_minor - new_paid,
        )
