"""Supplier schemas (Create / Update / Read + evaluations + paginated envelope)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    code: str | None = None
    name: str
    supplier_type_id: uuid.UUID
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    business_unit_id: uuid.UUID | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    supplier_type_id: uuid.UUID | None = None
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    status: str | None = None


class SupplierEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_id: uuid.UUID
    quality_score: int
    price_score: int
    reliability_score: int
    overall_score: int
    notes: str | None = None
    evaluated_on: date


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    supplier_type_id: uuid.UUID
    supplier_type_name: str | None = None
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    outstanding_minor: int = 0
    latest_score: int | None = None
    evaluation_count: int = 0
    status: str
    created_at: datetime


class SupplierPage(BaseModel):
    items: list[SupplierRead]
    total: int
    page: int
    page_size: int


class SupplierEvaluationCreate(BaseModel):
    supplier_id: uuid.UUID
    quality_score: int = Field(ge=0, le=5)
    price_score: int = Field(ge=0, le=5)
    reliability_score: int = Field(ge=0, le=5)
    notes: str | None = None


# --- Part 4: product↔supplier mapping (R5.1) + MOQ (R5.5) -------------------


class ProductSupplierUpsert(BaseModel):
    """Link a product to a supplier, or amend the link.

    Deliberately no lead-time field — R5.3 forbids one, lead time is measured.
    """

    product_id: uuid.UUID
    supplier_id: uuid.UUID
    is_preferred: bool = False
    moq: Decimal | None = Field(default=None, gt=0)
    note: str | None = None


class ProductSupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_code: str | None = None
    supplier_name: str | None = None
    is_preferred: bool = False
    moq: Decimal | None = None
    note: str | None = None
    #: Rendered vendor score for this supplier, or "unknown" (G11). A string on
    #: purpose: there is no number to show when the history is not there.
    score: str | None = None
    lead_time: str | None = None
    on_time_rate: str | None = None
