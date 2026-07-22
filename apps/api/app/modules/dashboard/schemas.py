"""Dashboard summary schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class TopCustomer(BaseModel):
    id: uuid.UUID
    name: str
    revenue_minor: int


class RevenuePoint(BaseModel):
    date: date
    amount_minor: int


class RecentActivity(BaseModel):
    id: uuid.UUID
    verb: str
    entity_type: str
    summary: str
    occurred_at: datetime


class DashboardSummary(BaseModel):
    today_sales_minor: int
    outstanding_receivables_minor: int
    inventory_value_minor: int
    low_stock_count: int
    pending_sales_orders: int
    pending_purchase_orders: int
    top_customers: list[TopCustomer]
    revenue_trend: list[RevenuePoint]
    recent_activities: list[RecentActivity]
