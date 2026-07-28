"""Customers pages: list + inline create + detail.

Reference implementation for the web layer's conventions:
- GET handlers call a domain service and render a template.
- POST handlers build the service's Pydantic payload from form fields, call the
  service with `actor_id`, and 303-redirect (Post/Redirect/Get). On a domain
  `AppError` we `db.rollback()` (the create may have partially flushed) and
  redirect back with an `err` flash. Unexpected errors propagate so `get_db`
  rolls back and surfaces them.
- Money inputs are collected in rupees and converted to integer minor units.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.activity.service import ActivityService
from app.modules.config.service import ConfigService
from app.modules.customers.credit import CreditPolicyService
from app.modules.customers.listing import CUSTOMER_LIST
from app.modules.customers.schemas import (
    BranchUpsert,
    ContactUpsert,
    CreditPolicySet,
    CustomerCreate,
    NoteCreate,
)
from app.modules.customers.service import CustomerService
from app.modules.customers.timeline import CustomerTimelineService
from app.web.core import form_action, render
from app.web.listing import csv_response_from_request, view_from_request, wants_csv
from app.web.security import require_web_permission

router = APIRouter()


@router.get("/customers")
def list_customers(request: Request, db: Session = Depends(get_db)):
    # List state is entirely in the query string (R2.3) — nothing to declare here.
    project = CustomerService(db).to_read_many
    if wants_csv(request):
        return csv_response_from_request(request, db, CUSTOMER_LIST, project=project)
    return render(
        request,
        "customers/list.html",
        view=view_from_request(request, db, CUSTOMER_LIST, project=project),
        customer_types=ConfigService(db).customer_types(),
    )


@router.post("/customers")
def create_customer(
    request: Request,
    name: str = Form(...),
    customer_type_id: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    gstin: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    billing_address: str = Form(""),
    credit_limit_rupees: str = Form("0"),
    payment_terms_days: int = Form(30),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("customer.create")),
):
    def work():
        payload = CustomerCreate(
            name=name,
            customer_type_id=uuid.UUID(customer_type_id),
            phone=phone or None,
            email=email or None,
            gstin=gstin or None,
            city=city or None,
            state=state or None,
            billing_address=billing_address or None,
            credit_limit_minor=int(round(float(credit_limit_rupees or 0) * 100)),
            payment_terms_days=payment_terms_days,
        )
        return CustomerService(db).create(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/customers",
        success=lambda c: (f"/customers/{c.id}", "Customer created"),
        err="Could not create customer",
    )


@router.get("/customers/{customer_id}")
def customer_detail(request: Request, customer_id: uuid.UUID, db: Session = Depends(get_db)):
    # A missing customer raises NotFoundError → the web error handler renders error.html.
    svc = CustomerService(db)
    customer = svc.get(customer_id)
    credit = CreditPolicyService(db)
    return render(
        request,
        "customers/detail.html",
        c=customer,
        history=ActivityService(db).history("customer", customer_id),
        # R8.1–R8.5 — everything about this customer, on one page.
        contacts=svc.contacts(customer_id),
        branches=svc.branches(customer_id),
        notes=svc.notes(customer_id),
        documents=svc.documents(customer_id),
        # R8.3 — the versioned terms, so a prior limit is readable.
        credit_history=credit.history(customer_id),
        # R8.7 — the current credit position, explained. Order value zero: this is the
        # standing position, not a decision about a particular order.
        credit_explained=credit.explain(credit.check(customer_id, 0)),
        # R8.10 — the one chronological view.
        timeline=CustomerTimelineService(db).events(customer_id, limit=60),
    )


@router.post("/customers/{customer_id}/contacts")
def add_contact(
    request: Request,
    customer_id: uuid.UUID,
    name: str = Form(...),
    designation: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    is_primary: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("customer.update")),
):
    """R8.1 — a customer has as many contacts as it has people."""

    def work():
        return CustomerService(db).add_contact(
            customer_id,
            ContactUpsert(
                name=name,
                designation=designation or None,
                email=email or None,
                phone=phone or None,
                is_primary=bool(is_primary),
            ),
            actor_id=actor.id,
        )

    return form_action(
        db, work, back=f"/customers/{customer_id}",
        success=lambda c: (f"/customers/{customer_id}", f"{c.name} added"),
        err="Could not add the contact",
    )


@router.post("/customer-contacts/{contact_id}/delete")
def delete_contact(
    request: Request,
    contact_id: uuid.UUID,
    customer_id: uuid.UUID = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("customer.update")),
):
    return form_action(
        db, lambda: CustomerService(db).delete_contact(contact_id, actor_id=actor.id),
        back=f"/customers/{customer_id}",
        success=(f"/customers/{customer_id}", "Contact removed"),
        err="Could not remove the contact",
    )


@router.post("/customers/{customer_id}/branches")
def add_branch(
    request: Request,
    customer_id: uuid.UUID,
    line1: str = Form(...),
    line2: str = Form(""),
    city: str = Form(...),
    state_code: str = Form(""),
    pincode: str = Form(""),
    is_default: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("customer.update")),
):
    """R8.2 — a ship-to branch. The billing address stays on the customer."""

    def work():
        return CustomerService(db).add_branch(
            customer_id,
            BranchUpsert(
                line1=line1,
                line2=line2 or None,
                city=city,
                state_code=state_code or None,
                pincode=pincode or None,
                is_default=bool(is_default),
            ),
            actor_id=actor.id,
        )

    return form_action(
        db, work, back=f"/customers/{customer_id}",
        success=lambda b: (f"/customers/{customer_id}", f"Branch in {b.city} added"),
        err="Could not add the branch",
    )


@router.post("/customer-branches/{branch_id}/delete")
def delete_branch(
    request: Request,
    branch_id: uuid.UUID,
    customer_id: uuid.UUID = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("customer.update")),
):
    return form_action(
        db, lambda: CustomerService(db).delete_branch(branch_id, actor_id=actor.id),
        back=f"/customers/{customer_id}",
        success=(f"/customers/{customer_id}", "Branch removed"),
        err="Could not remove the branch",
    )


@router.post("/customers/{customer_id}/notes")
def add_note(
    request: Request,
    customer_id: uuid.UUID,
    body: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("customer.update")),
):
    """R8.5 — a dated note, which then appears on the timeline."""
    return form_action(
        db,
        lambda: CustomerService(db).add_note(
            customer_id, NoteCreate(body=body), actor_id=actor.id
        ),
        back=f"/customers/{customer_id}",
        success=(f"/customers/{customer_id}", "Note added"),
        err="Could not add the note",
    )


@router.post("/customers/{customer_id}/credit")
def set_credit_policy(
    request: Request,
    customer_id: uuid.UUID,
    credit_limit_rupees: str = Form(""),
    payment_terms_days: str = Form(""),
    delivery_preference: str = Form(""),
    reason: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("customer.update")),
):
    """R8.3 — appends a VERSION of the terms. The reason is required, because a version
    nobody can explain later is as good as no history."""

    def work():
        return CreditPolicyService(db).set_policy(
            customer_id,
            CreditPolicySet(
                credit_limit_minor=(
                    int(round(float(credit_limit_rupees) * 100))
                    if credit_limit_rupees.strip()
                    else None
                ),
                payment_terms_days=(
                    int(payment_terms_days) if payment_terms_days.strip() else None
                ),
                delivery_preference=delivery_preference or None,
                reason=reason,
            ),
            actor_id=actor.id,
        )

    return form_action(
        db, work, back=f"/customers/{customer_id}",
        success=(f"/customers/{customer_id}", "Credit terms updated — a new version was recorded"),
        err="Could not update the credit terms",
    )


@router.post("/customers/{customer_id}/delete")
def delete_customer(
    request: Request,
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("customer.delete")),
):
    # On success the detail page is gone, so land on the list; on failure stay put.
    return form_action(
        db, lambda: CustomerService(db).delete(customer_id, actor_id=actor.id),
        back=f"/customers/{customer_id}",
        success=("/customers", "Customer deleted"),
        err="Could not delete customer",
    )
