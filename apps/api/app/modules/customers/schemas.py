"""Customer schemas (Create / Update / Read + paginated envelope)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


# --- Part 6: profile depth, versioned terms, the credit decision, the timeline ---


class ContactUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str | None = None
    phone: str | None = None
    designation: str | None = None
    is_primary: bool = False


class BranchUpsert(BaseModel):
    """A ship-to branch (R8.2). `address_type` defaults to `shipping` because that is what
    a branch IS — the billing address lives on the customer."""

    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = None
    city: str = Field(min_length=1, max_length=80)
    state_code: str | None = None
    pincode: str | None = None
    address_type: str = "shipping"
    is_default: bool = False


class NoteCreate(BaseModel):
    body: str = Field(min_length=1)


class CreditPolicySet(BaseModel):
    """A new VERSION of the terms (R8.3). Fields left None carry forward from the version
    being replaced, so setting a limit does not silently zero the payment terms."""

    credit_limit_minor: int | None = None
    payment_terms_days: int | None = None
    delivery_preference: str | None = None
    reason: str = Field(min_length=1)


class CreditPolicyRead(BaseModel):
    id: uuid.UUID
    credit_limit_minor: int
    payment_terms_days: int
    delivery_preference: str | None
    reason: str | None
    valid_from: datetime
    valid_to: datetime | None
    is_current: bool


class CreditDecision(BaseModel):
    """The answer to "may this order be confirmed?", carrying the numbers R8.7 requires."""

    customer_id: uuid.UUID
    customer_name: str
    allowed: bool
    limit_minor: int
    outstanding_minor: int
    order_total_minor: int
    # A limit of zero means none is recorded — not "refuse everything".
    unlimited: bool = False
    overridden: bool = False
    override_reason: str | None = None

    @property
    def exposure_minor(self) -> int:
        return self.outstanding_minor + self.order_total_minor

    @property
    def shortfall_minor(self) -> int:
        """How far over the limit this order would put them. Zero when within."""
        if self.unlimited:
            return 0
        return max(self.exposure_minor - self.limit_minor, 0)


class TimelineEvent(BaseModel):
    """One entry in R8.10's unified view — a PROJECTION, never a stored row."""

    at: datetime
    kind: str  # order | invoice | payment | task | note | activity
    summary: str
    href: str | None = None
    amount_minor: int | None = None
