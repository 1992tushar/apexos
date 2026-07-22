"""Dashboard repository — cross-module aggregate queries."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.customers.models import Customer
from app.modules.finance.models import Invoice
from app.modules.sales.models import SalesOrder


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def today_sales_minor(self, today: date) -> int:
        return int(
            self.db.scalar(
                select(func.coalesce(func.sum(SalesOrder.total_minor), 0)).where(
                    SalesOrder.order_date == today,
                    SalesOrder.status != "cancelled",
                    SalesOrder.deleted_at.is_(None),
                )
            )
            or 0
        )

    def top_customers(self, limit: int = 5) -> list[tuple]:
        stmt = (
            select(
                Customer.id,
                Customer.name,
                func.coalesce(func.sum(Invoice.total_minor), 0).label("rev"),
            )
            .join(Invoice, Invoice.customer_id == Customer.id)
            .where(Invoice.status != "cancelled", Invoice.deleted_at.is_(None))
            .group_by(Customer.id, Customer.name)
            .order_by(func.coalesce(func.sum(Invoice.total_minor), 0).desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).all())

    def revenue_by_date(self, since: date) -> dict[date, int]:
        stmt = (
            select(
                Invoice.invoice_date,
                func.coalesce(func.sum(Invoice.total_minor), 0),
            )
            .where(
                Invoice.invoice_date >= since,
                Invoice.status != "cancelled",
                Invoice.deleted_at.is_(None),
            )
            .group_by(Invoice.invoice_date)
        )
        return {d: int(v or 0) for d, v in self.db.execute(stmt).all()}
