"""Supplier schemas (Create / Update / Read + evaluations + paginated envelope)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

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
