"""Fulfillment service — reads only; fulfillment is created by SalesOrderService
during the confirmed→fulfilled transition."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.fulfillment.repository import FulfillmentRepository


class FulfillmentService:
    def __init__(self, db: Session) -> None:
        self.repo = FulfillmentRepository(db)

    def for_order(self, sales_order_id: uuid.UUID):
        return self.repo.for_order(sales_order_id)
