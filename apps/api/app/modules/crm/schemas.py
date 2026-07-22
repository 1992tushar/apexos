"""CRM schemas — pipeline stages, leads, opportunities, competitors."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineStageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    sort_order: int
    is_won: bool
    is_lost: bool
    is_active: bool


class LeadCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    source: str | None = None
    customer_type_id: uuid.UUID | None = None
    notes: str | None = None
    business_unit_id: uuid.UUID | None = None


class LeadConvert(BaseModel):
    """Optional overrides when converting a lead to a customer."""

    customer_type_id: uuid.UUID | None = None
    credit_limit_minor: int = 0
    payment_terms_days: int = 30


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    source: str | None = None
    customer_type_id: uuid.UUID | None = None
    status: str
    converted_customer_id: uuid.UUID | None = None
    notes: str | None = None
    created_at: datetime


class LeadPage(BaseModel):
    items: list[LeadRead]
    total: int
    page: int
    page_size: int


class OpportunityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    lead_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    pipeline_stage_id: uuid.UUID | None = None
    estimated_value_minor: int = Field(default=0, ge=0)
    expected_close_date: date | None = None
    business_unit_id: uuid.UUID | None = None


class OpportunityAdvance(BaseModel):
    pipeline_stage_id: uuid.UUID


class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    lead_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    pipeline_stage_id: uuid.UUID
    estimated_value_minor: int
    status: str
    expected_close_date: date | None = None
    created_at: datetime


class OpportunityListRow(BaseModel):
    id: uuid.UUID
    name: str
    pipeline_stage_id: uuid.UUID
    stage_name: str | None = None
    estimated_value_minor: int
    status: str
    expected_close_date: date | None = None
    customer_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None


class CompetitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    strength: str | None = None
    notes: str | None = None
    business_unit_id: uuid.UUID | None = None


class CompetitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    strength: str | None = None
    notes: str | None = None
    created_at: datetime
