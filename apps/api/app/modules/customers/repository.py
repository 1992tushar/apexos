"""Customer repository — persistence + read projections."""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.config.models import CustomerType
from app.modules.customers.models import Customer, CustomerCreditPolicy


class CustomerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- writes ---------------------------------------------------------
    def add(self, customer: Customer) -> Customer:
        self.db.add(customer)
        self.db.flush()
        return customer

    def add_credit_policy(self, policy: CustomerCreditPolicy) -> CustomerCreditPolicy:
        self.db.add(policy)
        self.db.flush()
        return policy

    # --- reads ----------------------------------------------------------
    def get(self, customer_id: uuid.UUID) -> Customer | None:
        return self.db.scalar(
            select(Customer).where(Customer.id == customer_id, Customer.deleted_at.is_(None))
        )

    def count_all(self) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Customer).where(Customer.deleted_at.is_(None))
        ) or 0

    def search(self, *, search: str | None, page: int, page_size: int) -> tuple[list[Customer], int]:
        base = select(Customer).where(Customer.deleted_at.is_(None))
        if search:
            like = f"%{search.lower()}%"
            base = base.where(
                or_(
                    func.lower(Customer.name).like(like),
                    func.lower(Customer.code).like(like),
                    func.lower(func.coalesce(Customer.city, "")).like(like),
                )
            )
        total = self.db.scalar(
            select(func.count()).select_from(base.subquery())
        ) or 0
        rows = list(
            self.db.scalars(
                base.order_by(Customer.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total

    def customer_type_name(self, customer_type_id: uuid.UUID) -> str | None:
        return self.db.scalar(
            select(CustomerType.name).where(CustomerType.id == customer_type_id)
        )

    def current_credit_policy(self, customer_id: uuid.UUID) -> CustomerCreditPolicy | None:
        return self.db.scalar(
            select(CustomerCreditPolicy)
            .where(
                CustomerCreditPolicy.customer_id == customer_id,
                CustomerCreditPolicy.valid_to.is_(None),
                CustomerCreditPolicy.deleted_at.is_(None),
            )
            .order_by(CustomerCreditPolicy.valid_from.desc())
        )

    def outstanding_minor(self, customer_id: uuid.UUID) -> int:
        """Receivable = Σ invoice.total − Σ allocations against those invoices."""
        from app.modules.finance.models import Invoice, PaymentAllocation

        invoiced = self.db.scalar(
            select(func.coalesce(func.sum(Invoice.total_minor), 0)).where(
                Invoice.customer_id == customer_id,
                Invoice.status != "cancelled",
                Invoice.deleted_at.is_(None),
            )
        ) or 0
        allocated = self.db.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.amount_minor), 0))
            .select_from(PaymentAllocation)
            .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
            .where(Invoice.customer_id == customer_id)
        ) or 0
        return int(invoiced) - int(allocated)

    def next_code(self) -> str:
        n = self.count_all() + 1
        return f"CUST-{n:04d}"
