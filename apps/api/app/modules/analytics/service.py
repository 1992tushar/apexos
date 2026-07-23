"""Analytics service — read-only KPI projections over the ledgers (docs §2.10).

Owns no entities, writes no activity_log. Money is integer minor units; margins
are basis points to round-trip cleanly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.customers.models import Customer
from app.modules.finance.models import Bill, Invoice, InvoiceLine
from app.modules.finance.repository import FinanceRepository
from app.modules.analytics.schemas import KpiBoard, RankRow, TrendPoint
from app.modules.pricing.service import PricingService
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.finance = FinanceRepository(db)
        self.pricing = PricingService(db)

    def _month_keys(self, n: int) -> list[str]:
        today = datetime.now(timezone.utc).date()
        keys: list[str] = []
        y, m = today.year, today.month
        for _ in range(n):
            keys.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        return list(reversed(keys))

    def _revenue_trend(self, months: int) -> list[TrendPoint]:
        keys = self._month_keys(months)
        rows = self.db.execute(
            select(
                func.strftime("%Y-%m", Invoice.invoice_date),
                func.coalesce(func.sum(Invoice.total_minor), 0),
            )
            .where(Invoice.status != "cancelled", Invoice.deleted_at.is_(None))
            .group_by(func.strftime("%Y-%m", Invoice.invoice_date))
        ).all()
        by_key = {r[0]: int(r[1]) for r in rows}
        return [TrendPoint(period=k, amount_minor=by_key.get(k, 0)) for k in keys]

    def _purchase_trend(self, months: int) -> list[TrendPoint]:
        keys = self._month_keys(months)
        rows = self.db.execute(
            select(
                func.strftime("%Y-%m", Bill.bill_date),
                func.coalesce(func.sum(Bill.total_minor), 0),
            )
            .where(Bill.status != "cancelled", Bill.deleted_at.is_(None))
            .group_by(func.strftime("%Y-%m", Bill.bill_date))
        ).all()
        by_key = {r[0]: int(r[1]) for r in rows}
        return [TrendPoint(period=k, amount_minor=by_key.get(k, 0)) for k in keys]

    def _top_customers(self, limit: int) -> list[RankRow]:
        rows = self.db.execute(
            select(Customer.id, Customer.name, func.coalesce(func.sum(Invoice.total_minor), 0))
            .join(Invoice, Invoice.customer_id == Customer.id)
            .where(Invoice.status != "cancelled", Invoice.deleted_at.is_(None))
            .group_by(Customer.id, Customer.name)
            .order_by(func.coalesce(func.sum(Invoice.total_minor), 0).desc())
            .limit(limit)
        ).all()
        return [RankRow(id=r[0], name=r[1], value_minor=int(r[2])) for r in rows]

    def _top_suppliers(self, limit: int) -> list[RankRow]:
        rows = self.db.execute(
            select(Supplier.id, Supplier.name, func.coalesce(func.sum(Bill.total_minor), 0))
            .join(Bill, Bill.supplier_id == Supplier.id)
            .where(Bill.status != "cancelled", Bill.deleted_at.is_(None))
            .group_by(Supplier.id, Supplier.name)
            .order_by(func.coalesce(func.sum(Bill.total_minor), 0).desc())
            .limit(limit)
        ).all()
        return [RankRow(id=r[0], name=r[1], value_minor=int(r[2])) for r in rows]

    def _top_products(self, limit: int) -> list[RankRow]:
        rows = self.db.execute(
            select(Product.id, Product.name, func.coalesce(func.sum(InvoiceLine.line_total_minor), 0))
            .join(InvoiceLine, InvoiceLine.product_id == Product.id)
            .group_by(Product.id, Product.name)
            .order_by(func.coalesce(func.sum(InvoiceLine.line_total_minor), 0).desc())
            .limit(limit)
        ).all()
        return [RankRow(id=r[0], name=r[1], value_minor=int(r[2])) for r in rows]

    def _gross_profit_minor(self) -> tuple[int, int]:
        """Returns (gross_profit_minor, revenue_subtotal_minor). GP approximated per
        invoice line as (unit_price − latest buy price) × qty."""
        gp = 0
        revenue_subtotal = 0
        cost_cache: dict = {}
        rows = self.db.execute(
            select(
                InvoiceLine.product_id,
                InvoiceLine.qty,
                InvoiceLine.unit_price_minor,
                InvoiceLine.line_subtotal_minor,
            )
        ).all()
        for product_id, qty, unit_price, line_subtotal in rows:
            revenue_subtotal += int(line_subtotal or 0)
            if product_id not in cost_cache:
                cost_cache[product_id] = self.pricing.latest_purchase_minor(product_id) or 0
            buy = cost_cache[product_id]
            gp += int((Decimal(int(unit_price) - int(buy)) * Decimal(qty)).quantize(Decimal("1")))
        return gp, revenue_subtotal

    def _fill_rate_bps(self) -> int:
        """Orders fulfilled-or-beyond ÷ orders confirmed-or-beyond, in basis points."""
        from app.modules.sales.models import SalesOrder

        denom = self.db.scalar(
            select(func.count())
            .select_from(SalesOrder)
            .where(
                SalesOrder.status.in_(["confirmed", "fulfilled", "invoiced"]),
                SalesOrder.deleted_at.is_(None),
            )
        ) or 0
        if denom == 0:
            return 0
        numer = self.db.scalar(
            select(func.count())
            .select_from(SalesOrder)
            .where(
                SalesOrder.status.in_(["fulfilled", "invoiced"]),
                SalesOrder.deleted_at.is_(None),
            )
        ) or 0
        return int(round((numer / denom) * 10000))

    def board(self) -> KpiBoard:
        revenue = self.db.scalar(
            select(func.coalesce(func.sum(Invoice.total_minor), 0)).where(
                Invoice.status != "cancelled", Invoice.deleted_at.is_(None)
            )
        ) or 0
        purchases = self.db.scalar(
            select(func.coalesce(func.sum(Bill.total_minor), 0)).where(
                Bill.status != "cancelled", Bill.deleted_at.is_(None)
            )
        ) or 0
        gp, revenue_subtotal = self._gross_profit_minor()
        margin_bps = int(round((gp / revenue_subtotal) * 10000)) if revenue_subtotal else 0
        receivables = self.finance.outstanding_total()

        # DSO ≈ receivables ÷ (revenue over trailing window) × window days. Use 90d.
        dso = 0
        if revenue:
            dso = int(round((receivables / int(revenue)) * 90))

        return KpiBoard(
            revenue_minor=int(revenue),
            purchases_minor=int(purchases),
            gross_profit_minor=gp,
            margin_bps=margin_bps,
            receivables_minor=receivables,
            payables_minor=self.finance.payable_total(),
            dso_days=dso,
            fill_rate_bps=self._fill_rate_bps(),
            revenue_trend=self._revenue_trend(6),
            purchase_trend=self._purchase_trend(6),
            top_customers=self._top_customers(5),
            top_suppliers=self._top_suppliers(5),
            top_products=self._top_products(5),
        )
