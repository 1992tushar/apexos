"""Customer service — CRUD + read projection assembly, emits activity."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.db.duplicates import ensure_unique
from app.db.listing import ListParams, query_page
from app.db.references import ensure_unreferenced
from app.db.soft_delete import soft_delete
from app.modules.activity.history import CHANGES_KEY, field_changes
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit
from app.modules.customers.listing import CUSTOMER_LIST
from app.modules.customers.models import (
    Customer,
    CustomerAddress,
    CustomerContact,
    CustomerCreditPolicy,
    CustomerNote,
)
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

    def to_read_many(self, rows: Sequence[Customer]) -> list[CustomerRead]:
        """The projector the list page passes to `view_from_request(project=...)`."""
        return [self._to_read(c) for c in rows]

    def list(self, *, search: str | None, page: int, page_size: int):
        """One page of customers, through the one query helper (R2.4)."""
        params = ListParams(q=search or "", page=page)
        result = query_page(self.db, replace(CUSTOMER_LIST, page_size=page_size), params)
        return self.to_read_many(result.rows), result.total

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
        # An open sales order still reads the customer; an invoice snapshotted what it
        # needed, which is why R1.7's "delete a customer with an invoice" still works.
        ensure_unreferenced(self.db, customer, action="delete", label="Customer")
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

    # --- Part 6: profile depth (R8.1, R8.2, R8.5, R8.13) -----------------
    # Contacts, branches and notes are ordinary child records: created here, listed by the
    # repository, and retired with the ONE soft-delete helper (R8.13) rather than a second
    # delete path. Each verb writes one activity row against the CUSTOMER, because that is
    # the entity whose history a founder reads.

    def contacts(self, customer_id: uuid.UUID):
        return self.repo.contacts(customer_id)

    def branches(self, customer_id: uuid.UUID):
        return self.repo.branches(customer_id)

    def notes(self, customer_id: uuid.UUID):
        return self.repo.notes(customer_id)

    def documents(self, customer_id: uuid.UUID):
        return self.repo.documents(customer_id)

    def _require(self, customer_id: uuid.UUID) -> Customer:
        customer = self.repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        return customer

    def add_contact(self, customer_id: uuid.UUID, payload, *, actor_id) -> CustomerContact:
        customer = self._require(customer_id)
        if payload.is_primary:
            # Exactly one primary contact, the same exclusivity R5.1 gave the preferred
            # supplier: two "primary" contacts is not a state anyone can act on.
            for existing in self.repo.contacts(customer.id):
                existing.is_primary = False
        contact = CustomerContact(
            customer_id=customer.id,
            name=payload.name.strip(),
            email=payload.email or None,
            phone=payload.phone or None,
            designation=payload.designation or None,
            is_primary=payload.is_primary,
            created_by=actor_id,
        )
        self.db.add(contact)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id, verb="updated", entity_type="customer",
            entity_id=customer.id,
            summary=f"Contact {contact.name} added to {customer.name}",
        )
        return contact

    def delete_contact(self, contact_id: uuid.UUID, *, actor_id) -> CustomerContact:
        contact = self.db.scalar(
            select(CustomerContact).where(
                CustomerContact.id == contact_id, CustomerContact.deleted_at.is_(None)
            )
        )
        if contact is None:
            raise NotFoundError(f"Contact {contact_id} not found")
        soft_delete(self.db, contact, actor_id=actor_id, label="Contact")
        return contact

    def add_branch(self, customer_id: uuid.UUID, payload, *, actor_id) -> CustomerAddress:
        customer = self._require(customer_id)
        if payload.is_default:
            for existing in self.repo.branches(customer.id):
                existing.is_default = False
        branch = CustomerAddress(
            customer_id=customer.id,
            address_type=payload.address_type or "shipping",
            line1=payload.line1.strip(),
            line2=payload.line2 or None,
            city=payload.city.strip(),
            state_code=payload.state_code or None,
            pincode=payload.pincode or None,
            is_default=payload.is_default,
            created_by=actor_id,
        )
        self.db.add(branch)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id, verb="updated", entity_type="customer",
            entity_id=customer.id,
            summary=f"Ship-to branch in {branch.city} added to {customer.name}",
        )
        return branch

    def delete_branch(self, branch_id: uuid.UUID, *, actor_id) -> CustomerAddress:
        branch = self.db.scalar(
            select(CustomerAddress).where(
                CustomerAddress.id == branch_id, CustomerAddress.deleted_at.is_(None)
            )
        )
        if branch is None:
            raise NotFoundError(f"Branch {branch_id} not found")
        soft_delete(self.db, branch, actor_id=actor_id, label="Branch")
        return branch

    def add_note(self, customer_id: uuid.UUID, payload, *, actor_id) -> CustomerNote:
        customer = self._require(customer_id)
        body = payload.body.strip()
        if not body:
            raise ValidationError("A note needs something in it")
        # `created_at` is stamped EXPLICITLY rather than left to `func.now()`. The server
        # default has whole-second resolution here, so two notes added in one request tie,
        # and `uuid7()` cannot break the tie either (its low bits are random). The notes
        # list would then flip order between page loads. `datetime.now(UTC)` has microsecond
        # resolution, which is the same reason `CreditPolicyService` stamps `valid_from`.
        note = CustomerNote(
            customer_id=customer.id,
            body=body,
            created_at=datetime.now(UTC),
            created_by=actor_id,
        )
        self.db.add(note)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id, verb="updated", entity_type="customer",
            entity_id=customer.id,
            summary=f"Note added to {customer.name}",
        )
        return note

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

        # R8.3: credit terms are VERSIONED, so a change here APPENDS a version through
        # CreditPolicyService rather than editing the current row. This used to mutate the
        # policy in place, which quietly destroyed the answer to "what limit were they on
        # when we approved that order?" — the only reason to keep history at all.
        if data.get("credit_limit_minor") is not None or data.get("payment_terms_days") is not None:
            from app.modules.customers.credit import CreditPolicyService
            from app.modules.customers.schemas import CreditPolicySet

            CreditPolicyService(self.db).set_policy(
                customer.id,
                CreditPolicySet(
                    credit_limit_minor=data.get("credit_limit_minor"),
                    payment_terms_days=data.get("payment_terms_days"),
                    reason=(data.get("credit_reason") or "Updated with the customer record"),
                ),
                actor_id=actor_id,
            )

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
