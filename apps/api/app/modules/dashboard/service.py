"""Dashboard service — assembles the command-center summary tile."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.activity.service import ActivityService
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    DashboardSummary,
    RecentActivity,
    RevenuePoint,
    TopCustomer,
)
from app.modules.finance.repository import FinanceRepository
from app.modules.inventory.service import InventoryService
from app.modules.pricing.service import PricingService
from app.modules.procurement.repository import ProcurementRepository
from app.modules.products.models import Product
from app.modules.sales.repository import SalesRepository


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DashboardRepository(db)
        self.finance = FinanceRepository(db)
        self.inventory = InventoryService(db)
        self.pricing = PricingService(db)
        self.sales = SalesRepository(db)
        self.procurement = ProcurementRepository(db)
        self.activity = ActivityService(db)

    def _inventory_value_minor(self) -> int:
        total = 0
        for pid in self.db.scalars(
            select(Product.id).where(Product.deleted_at.is_(None))
        ):
            on_hand = self.inventory.on_hand(pid)
            if on_hand <= 0:
                continue
            unit_cost = self.pricing.latest_purchase_minor(pid) or 0
            total += int((on_hand * Decimal(unit_cost)).quantize(Decimal("1")))
        return total

    def summary(self) -> DashboardSummary:
        today = datetime.now(UTC).date()

        # 14-day revenue trend (inclusive of today), zero-filled.
        since = today - timedelta(days=13)
        rev_map = self.repo.revenue_by_date(since)
        trend = [
            RevenuePoint(
                date=since + timedelta(days=i),
                amount_minor=rev_map.get(since + timedelta(days=i), 0),
            )
            for i in range(14)
        ]

        top = [
            TopCustomer(id=cid, name=name, revenue_minor=int(rev or 0))
            for cid, name, rev in self.repo.top_customers(5)
        ]

        recent = [
            RecentActivity(
                id=a.id,
                verb=a.verb,
                entity_type=a.entity_type,
                summary=a.summary,
                occurred_at=a.occurred_at,
            )
            for a in self.activity.recent(10)
        ]

        return DashboardSummary(
            today_sales_minor=self.repo.today_sales_minor(today),
            outstanding_receivables_minor=self.finance.outstanding_total(),
            inventory_value_minor=self._inventory_value_minor(),
            low_stock_count=self.inventory.low_stock_count(),
            pending_sales_orders=self.sales.pending_count(),
            pending_purchase_orders=self.procurement.pending_count(),
            top_customers=top,
            revenue_trend=trend,
            recent_activities=recent,
        )
