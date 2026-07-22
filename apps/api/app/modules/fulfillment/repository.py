"""Fulfillment repository."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.fulfillment.models import Fulfillment


class FulfillmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def for_order(self, sales_order_id: uuid.UUID) -> list[Fulfillment]:
        return list(
            self.db.scalars(
                select(Fulfillment).where(Fulfillment.sales_order_id == sales_order_id)
            )
        )
