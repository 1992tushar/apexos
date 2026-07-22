"""Analytics schemas — the KPI board payload (read-only)."""
from __future__ import annotations

import uuid

from pydantic import BaseModel


class TrendPoint(BaseModel):
    period: str  # YYYY-MM
    amount_minor: int


class RankRow(BaseModel):
    id: uuid.UUID | None = None
    name: str
    value_minor: int


class KpiBoard(BaseModel):
    revenue_minor: int
    purchases_minor: int
    gross_profit_minor: int
    margin_bps: int
    receivables_minor: int
    payables_minor: int
    dso_days: int
    fill_rate_bps: int
    revenue_trend: list[TrendPoint]
    purchase_trend: list[TrendPoint]
    top_customers: list[RankRow]
    top_suppliers: list[RankRow]
    top_products: list[RankRow]
