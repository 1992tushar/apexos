"""Sales order repository."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.customers.models import Customer
from app.modules.sales.models import SalesOrder, SalesOrderLine


class SalesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, order: SalesOrder) -> SalesOrder:
        self.db.add(order)
        self.db.flush()
        return order

    def get(self, order_id: uuid.UUID) -> SalesOrder | None:
        return self.db.scalar(
            select(SalesOrder)
            .options(selectinload(SalesOrder.lines))
            .where(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None))
        )

    def customer_name(self, customer_id: uuid.UUID) -> str | None:
        return self.db.scalar(select(Customer.name).where(Customer.id == customer_id))

    def search(
        self, *, status: str | None, page: int, page_size: int
    ) -> tuple[list[tuple], int]:
        line_count = (
            select(
                SalesOrderLine.sales_order_id.label("so_id"),
                func.count().label("cnt"),
            )
            .group_by(SalesOrderLine.sales_order_id)
            .subquery()
        )
        base = (
            select(
                SalesOrder.id,
                SalesOrder.order_no,
                Customer.name,
                SalesOrder.status,
                SalesOrder.total_minor,
                SalesOrder.order_date,
                func.coalesce(line_count.c.cnt, 0),
            )
            .join(Customer, Customer.id == SalesOrder.customer_id)
            .outerjoin(line_count, line_count.c.so_id == SalesOrder.id)
            .where(SalesOrder.deleted_at.is_(None))
        )
        if status:
            base = base.where(SalesOrder.status == status)

        count_base = select(func.count()).select_from(SalesOrder).where(
            SalesOrder.deleted_at.is_(None)
        )
        if status:
            count_base = count_base.where(SalesOrder.status == status)
        total = self.db.scalar(count_base) or 0
        rows = list(
            self.db.execute(
                base.order_by(SalesOrder.order_date.desc(), SalesOrder.order_no.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return rows, total

    def pending_count(self) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(SalesOrder)
            .where(
                SalesOrder.status.in_(["draft", "confirmed"]),
                SalesOrder.deleted_at.is_(None),
            )
        ) or 0
