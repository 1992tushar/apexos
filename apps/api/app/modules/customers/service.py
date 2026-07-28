"""Customer service — CRUD + read projection assembly, emits activity."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.duplicates import ensure_unique
from app.db.soft_delete import soft_delete
from app.modules.activity.history import CHANGES_KEY, field_changes
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit
from app.modules.customers.models import Customer, CustomerCreditPolicy
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.schemas import CustomerCreate, CustomerRead, CustomerUpdate


class CustomerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CustomerRepository(db)
        self.activity = ActivityService(db)

    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    def _to_read(self, customer: Customer) -> CustomerRead:
        policy = self.repo.current_credit_policy(customer.id)
        return CustomerRead(
            id=customer.id,
            code=customer.code,
            name=customer.name,
            customer_type_id=customer.customer_type_id,
            customer_type_name=self.repo.customer_type_name(customer.customer_type_id),
            phone=customer.phone,
            email=customer.email,
            gstin=customer.gstin,
            billing_address=customer.billing_address,
            city=customer.city,
            state=customer.state,
            credit_limit_minor=policy.credit_limit_minor if policy else 0,
            payment_terms_days=policy.payment_terms_days if policy else 0,
            outstanding_minor=self.repo.outstanding_minor(customer.id),
            status=customer.status,
            created_at=customer.created_at,
        )

    def list(self, *, search: str | None, page: int, page_size: int):
        rows, total = self.repo.search(search=search, page=page, page_size=page_size)
        return [self._to_read(c) for c in rows], total

    def get(self, customer_id: uuid.UUID) -> CustomerRead:
        customer = self.repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        return self._to_read(customer)

    def delete(self, customer_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        """Soft-delete a customer (R1.2).

        Invoices and orders that reference the customer keep rendering — the row
        stays addressable, it just leaves the lists and lookups (R1.7).
        """
        customer = self.repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        soft_delete(self.db, customer, actor_id=actor_id, label="Customer")

    def create(self, payload: CustomerCreate, *, actor_id: uuid.UUID | None) -> CustomerRead:
        code = payload.code or self.repo.next_code()
        # The one duplicate check (R2.9) — natural keys are configured in
        # app.db.duplicates, not spelled out here.
        ensure_unique(
            self.db,
            Customer,
            {"code": code, "name": payload.name, "city": payload.city},
        )
        customer = Customer(
            code=code,
            name=payload.name,
            customer_type_id=payload.customer_type_id,
            phone=payload.phone,
            email=payload.email,
            gstin=payload.gstin,
            billing_address=payload.billing_address,
            city=payload.city,
            state=payload.state,
            status="active",
            business_unit_id=payload.business_unit_id or self._default_bu(),
            created_by=actor_id,
        )
        self.repo.add(customer)
        self.repo.add_credit_policy(
            CustomerCreditPolicy(
                customer_id=customer.id,
                credit_limit_minor=payload.credit_limit_minor,
                payment_terms_days=payload.payment_terms_days,
                status="active",
                created_by=actor_id,
            )
        )
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="customer",
            entity_id=customer.id,
            summary=f"Customer {customer.name} ({customer.code}) created",
        )
        return self._to_read(customer)

    def update(
        self, customer_id: uuid.UUID, payload: CustomerUpdate, *, actor_id: uuid.UUID | None
    ) -> CustomerRead:
        customer = self.repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        data = payload.model_dump(exclude_unset=True)
        own_fields = ("name", "customer_type_id", "phone", "email", "gstin",
                      "billing_address", "city", "state", "status")

        # An edit that moves the record onto another one's natural key is a
        # duplicate too; `exclude_id` keeps it from colliding with itself (R2.9).
        ensure_unique(
            self.db,
            Customer,
            {
                "code": customer.code,
                "name": data.get("name", customer.name),
                "city": data.get("city", customer.city),
            },
            exclude_id=customer.id,
        )

        # Captured before the assignment loop: `field_changes` reads the current
        # values off the row, so after the loop every diff would be empty (R2.10).
        changes = field_changes(customer, {f: data[f] for f in own_fields if f in data})

        for field in own_fields:
            if field in data:
                setattr(customer, field, data[field])
        customer.updated_by = actor_id

        if "credit_limit_minor" in data or "payment_terms_days" in data:
            policy = self.repo.current_credit_policy(customer.id)
            if policy is None:
                policy = CustomerCreditPolicy(customer_id=customer.id, created_by=actor_id)
                self.repo.add_credit_policy(policy)
            for field in ("credit_limit_minor", "payment_terms_days"):
                if data.get(field) is not None:
                    changes.update(field_changes(policy, {field: data[field]}))
                    setattr(policy, field, data[field])

        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="updated",
            entity_type="customer",
            entity_id=customer.id,
            summary=f"Customer {customer.name} updated",
            data={CHANGES_KEY: changes} if changes else None,
        )
        return self._to_read(customer)
