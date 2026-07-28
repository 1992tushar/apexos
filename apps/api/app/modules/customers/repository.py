"""Customer repository — persistence + read projections."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.config.models import CustomerType
from app.modules.customers.models import (
    Customer,
    CustomerAddress,
    CustomerContact,
    CustomerCreditPolicy,
    CustomerNote,
)


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

    # No `search()` here: paginated/filtered/sorted reads go through the one query
    # helper in `app.db.listing`, driven by `customers/listing.py`'s spec (R2.4).

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

    def count_ever(self) -> int:
        """Rows ever created, soft-deleted ones included.

        The basis for a generated code. `count_all()` would be wrong here: it
        excludes deleted rows, so after one deletion the next generated code is one
        a deleted customer still holds — `code` is UNIQUE across every row in the
        table, deleted or not.
        """
        return self.db.scalar(select(func.count()).select_from(Customer)) or 0

    def next_code(self) -> str:
        n = self.count_ever() + 1
        return f"CUST-{n:04d}"

    # --- Part 6: profile depth (R8.1, R8.2, R8.5) ------------------------

    def contacts(self, customer_id: uuid.UUID) -> list[CustomerContact]:
        """Primary first, then by name — the order the screen wants."""
        return list(
            self.db.scalars(
                select(CustomerContact)
                .where(
                    CustomerContact.customer_id == customer_id,
                    CustomerContact.deleted_at.is_(None),
                )
                .order_by(CustomerContact.is_primary.desc(), CustomerContact.name)
            )
        )

    def branches(self, customer_id: uuid.UUID) -> list[CustomerAddress]:
        """Default first, then by city."""
        return list(
            self.db.scalars(
                select(CustomerAddress)
                .where(
                    CustomerAddress.customer_id == customer_id,
                    CustomerAddress.deleted_at.is_(None),
                )
                .order_by(CustomerAddress.is_default.desc(), CustomerAddress.city)
            )
        )

    def notes(self, customer_id: uuid.UUID) -> list[CustomerNote]:
        """Newest first, with `id` as the tiebreaker — `created_at` defaults to
        `func.now()` and ties for rows written in one transaction."""
        return list(
            self.db.scalars(
                select(CustomerNote)
                .where(
                    CustomerNote.customer_id == customer_id,
                    CustomerNote.deleted_at.is_(None),
                )
                .order_by(CustomerNote.created_at.desc(), CustomerNote.id.desc())
            )
        )

    def documents(self, customer_id: uuid.UUID):
        """Documents already attach to any entity by (entity_type, entity_id), so R8.4
        needs no second upload path — this is a read against the existing table."""
        from app.modules.documents.models import Document

        return list(
            self.db.scalars(
                select(Document)
                .where(
                    Document.entity_type == "customer",
                    Document.entity_id == customer_id,
                    Document.deleted_at.is_(None),
                )
                .order_by(Document.created_at.desc(), Document.id.desc())
            )
        )
