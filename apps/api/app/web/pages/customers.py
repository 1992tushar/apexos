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
from app.core.security import Actor, get_current_actor
from app.modules.config.service import ConfigService
from app.modules.customers.schemas import CustomerCreate
from app.modules.customers.service import CustomerService
from app.web.core import form_action, render

router = APIRouter()


@router.get("/customers")
def list_customers(request: Request, q: str | None = None, db: Session = Depends(get_db)):
    items, total = CustomerService(db).list(search=q, page=1, page_size=200)
    customer_types = ConfigService(db).customer_types()
    return render(
        request,
        "customers/list.html",
        customers=items,
        total=total,
        customer_types=customer_types,
        q=q or "",
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
    actor: Actor = Depends(get_current_actor),
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
    return render(request, "customers/detail.html", c=customer)
