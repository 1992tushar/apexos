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
from app.modules.customers.listing import CUSTOMER_LIST
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import CustomerService
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
    customer = CustomerService(db).get(customer_id)
    return render(
        request,
        "customers/detail.html",
        c=customer,
        history=ActivityService(db).history("customer", customer_id),
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
