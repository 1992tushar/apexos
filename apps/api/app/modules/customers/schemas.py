"""Customer schemas (Create / Update / Read + paginated envelope)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    code: str | None = None
    name: str
    customer_type_id: uuid.UUID
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    billing_address: str | None = None
    city: str | None = None
    state: str | None = None
    credit_limit_minor: int = 0
    payment_terms_days: int = 30
    business_unit_id: uuid.UUID | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    customer_type_id: uuid.UUID | None = None
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    billing_address: str | None = None
    city: str | None = None
    state: str | None = None
    status: str | None = None
    credit_limit_minor: int | None = None
    payment_terms_days: int | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    customer_type_id: uuid.UUID
    customer_type_name: str | None = None
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    billing_address: str | None = None
    city: str | None = None
    state: str | None = None
    credit_limit_minor: int = 0
    payment_terms_days: int = 0
    outstanding_minor: int = 0
    status: str
    created_at: datetime


class CustomerPage(BaseModel):
    items: list[CustomerRead]
    total: int
    page: int
    page_size: int
