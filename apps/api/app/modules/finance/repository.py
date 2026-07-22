"""Finance repository."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.customers.models import Customer
from app.modules.finance.models import Bill, Invoice, Payment, PaymentAllocation
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
