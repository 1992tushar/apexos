"""Inventory service — record movements, derive on-hand, list low stock."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.inventory.models import StockMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import StockRow


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InventoryRepository(db)

    def record_movement(
        self,
        *,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        qty_delta: Decimal,
        reason: str,
        ref_type: str | None = None,
        ref_id: uuid.UUID | None = None,
        unit_cost_minor: int | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> StockMovement:
        movement = StockMovement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            qty_delta=qty_delta,
            reason=reason,
            ref_type=ref_type,
            ref_id=ref_id,
            unit_cost_minor=unit_cost_minor,
            created_by=actor_id,
        )
        return self.repo.add(movement)

    def on_hand(self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None) -> Decimal:
        return self.repo.on_hand(product_id, warehouse_id)

    def stock(self) -> list[StockRow]:
        rows = []
        for pid, sku, pname, wid, wname, qty, reorder in self.repo.stock_rows():
            qty = Decimal(qty or 0)
            reorder = Decimal(reorder or 0)
            rows.append(
                StockRow(
                    product_id=pid,
                    sku_code=sku,
                    product_name=pname,
                    warehouse_id=wid,
                    warehouse_name=wname,
                    qty_on_hand=qty,
                    reorder_level=reorder,
                    is_low=qty < reorder,
                )
            )
        return rows

    def low_stock(self) -> list[tuple]:
        return self.repo.low_stock_products()

    def low_stock_count(self) -> int:
        return len(self.repo.low_stock_products())

    def movements(self, product_id: uuid.UUID | None = None):
        return self.repo.movements(product_id)
