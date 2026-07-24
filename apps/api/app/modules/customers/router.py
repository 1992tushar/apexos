"""Customers router — thin; delegates to CustomerService."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.customers.schemas import (
    CustomerCreate,
    CustomerPage,
    CustomerRead,
    CustomerUpdate,
)
from app.modules.customers.service import CustomerService

router = APIRouter(tags=["customers"])


@router.get("/customers", response_model=CustomerPage)
def list_customers(
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = CustomerService(db).list(search=search, page=page, page_size=page_size)
    return CustomerPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/customers", response_model=CustomerRead, status_code=201)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("customer.create")),
):
    return CustomerService(db).create(payload, actor_id=actor.id)


@router.get("/customers/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    return CustomerService(db).get(customer_id)


@router.patch("/customers/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("customer.update")),
):
    return CustomerService(db).update(customer_id, payload, actor_id=actor.id)
