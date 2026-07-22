"""Inventory repository — movement writes + derived-balance reads."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.config.models import Warehouse
from app.modules.inventory.models import StockMovement
from app.modules.products.models import Product


class InventoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, movement: StockMovement) -> StockMovement:
        self.db.add(movement)
        self.db.flush()
        return movement

    def on_hand(self, product_id: uuid.UUID, warehouse_id: uuid.UUID | None = None) -> Decimal:
        stmt = select(func.coalesce(func.sum(StockMovement.qty_delta), 0)).where(
            StockMovement.product_id == product_id,
            StockMovement.deleted_at.is_(None),
        )
        if warehouse_id is not None:
            stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
        return Decimal(self.db.scalar(stmt) or 0)

    def balances(self) -> list[tuple]:
        """(product_id, warehouse_id, qty_on_hand) grouped."""
        stmt = (
            select(
                StockMovement.product_id,
                StockMovement.warehouse_id,
                func.coalesce(func.sum(StockMovement.qty_delta), 0).label("qty"),
            )
            .where(StockMovement.deleted_at.is_(None))
            .group_by(StockMovement.product_id, StockMovement.warehouse_id)
        )
        return list(self.db.execute(stmt).all())

    def stock_rows(self) -> list[tuple]:
        """Balance rows enriched with product + warehouse display fields."""
        stmt = (
            select(
                Product.id,
                Product.sku_code,
                Product.name,
                Warehouse.id,
                Warehouse.name,
                func.coalesce(func.sum(StockMovement.qty_delta), 0).label("qty"),
                Product.reorder_level,
            )
            .join(Product, Product.id == StockMovement.product_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .where(StockMovement.deleted_at.is_(None))
            .group_by(
                Product.id,
                Product.sku_code,
                Product.name,
                Warehouse.id,
                Warehouse.name,
                Product.reorder_level,
            )
            .order_by(Product.sku_code)
        )
        return list(self.db.execute(stmt).all())

    def movements(self, product_id: uuid.UUID | None = None) -> list[StockMovement]:
        stmt = select(StockMovement).where(StockMovement.deleted_at.is_(None))
        if product_id is not None:
            stmt = stmt.where(StockMovement.product_id == product_id)
        stmt = stmt.order_by(StockMovement.occurred_at.desc()).limit(500)
        return list(self.db.scalars(stmt))

    def low_stock_products(self) -> list[tuple]:
        """(product_id, qty_on_hand, reorder_level) where on_hand < reorder_level."""
        rows = []
        prod_stmt = select(Product.id, Product.reorder_level).where(Product.deleted_at.is_(None))
        for pid, reorder in self.db.execute(prod_stmt).all():
            qty = self.on_hand(pid)
            if qty < Decimal(reorder or 0):
                rows.append((pid, qty, Decimal(reorder or 0)))
        return rows
