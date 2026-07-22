"""Inventory service — record movements, derive on-hand, list low stock.

`InventoryService.record_movement` is the ONLY writer of `stock_movement` (D3);
Sales/Procurement and the Phase-B warehouse operations all go through it.
`StockTransferService` and `StockAdjustmentService` are the state-changing verbs
that each emit one `activity_log` row (D10); balances stay derived from the ledger.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.activity.service import ActivityService
from app.modules.config.models import Warehouse
from app.modules.inventory.models import StockMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    StockAdjustmentResult,
    StockRow,
    StockTransferResult,
    WarehouseStockRow,
)
from app.modules.products.models import Product


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

    def warehouse_stock(self, warehouse_id: uuid.UUID | None = None) -> list[WarehouseStockRow]:
        """Per-warehouse on-hand rows (optionally filtered to one warehouse)."""
        rows: list[WarehouseStockRow] = []
        for pid, sku, pname, wid, wname, qty, reorder in self.repo.stock_rows():
            if warehouse_id is not None and wid != warehouse_id:
                continue
            qty = Decimal(qty or 0)
            reorder = Decimal(reorder or 0)
            rows.append(
                WarehouseStockRow(
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


class StockTransferService:
    """Moves stock between two warehouses as two ledger movements (OUT then IN).
    Balances remain derived; nothing is stored mutably (D3)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryService(db)
        self.activity = ActivityService(db)

    def _require_warehouse(self, warehouse_id: uuid.UUID) -> Warehouse:
        wh = self.db.scalar(
            select(Warehouse).where(
                Warehouse.id == warehouse_id, Warehouse.deleted_at.is_(None)
            )
        )
        if wh is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        return wh

    def _require_product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def transfer(self, payload, *, actor_id: uuid.UUID | None) -> StockTransferResult:
        """Post a TRANSFER OUT at the source and TRANSFER IN at the destination.

        Raises:
            ValidationError: same source/destination, or insufficient on-hand.
            NotFoundError: unknown product or warehouse.
        """
        if payload.from_warehouse_id == payload.to_warehouse_id:
            raise ValidationError("Source and destination warehouses must differ")
        product = self._require_product(payload.product_id)
        src = self._require_warehouse(payload.from_warehouse_id)
        dst = self._require_warehouse(payload.to_warehouse_id)

        available = self.inventory.on_hand(product.id, src.id)
        if payload.qty > available:
            raise ValidationError(
                f"Transfer {payload.qty} exceeds on-hand {available} at {src.name}"
            )

        from app.modules.pricing.service import PricingService

        unit_cost = PricingService(self.db).latest_purchase_minor(product.id)
        self.inventory.record_movement(
            product_id=product.id,
            warehouse_id=src.id,
            qty_delta=-Decimal(payload.qty),
            reason="TRANSFER",
            ref_type="stock_transfer",
            ref_id=product.id,
            unit_cost_minor=unit_cost,
            actor_id=actor_id,
        )
        self.inventory.record_movement(
            product_id=product.id,
            warehouse_id=dst.id,
            qty_delta=Decimal(payload.qty),
            reason="TRANSFER",
            ref_type="stock_transfer",
            ref_id=product.id,
            unit_cost_minor=unit_cost,
            actor_id=actor_id,
        )
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="transferred",
            entity_type="stock",
            entity_id=product.id,
            summary=f"Transferred {payload.qty} × {product.sku_code} from {src.name} to {dst.name}",
            data={"qty": str(payload.qty), "from": src.code, "to": dst.code},
        )
        return StockTransferResult(
            product_id=product.id,
            from_warehouse_id=src.id,
            to_warehouse_id=dst.id,
            qty=Decimal(payload.qty),
            from_on_hand=self.inventory.on_hand(product.id, src.id),
            to_on_hand=self.inventory.on_hand(product.id, dst.id),
        )


class StockAdjustmentService:
    """Manual corrections and cycle counts — a single signed ledger movement
    (reason `ADJUSTMENT` or `COUNT`) plus one `activity_log` row (D10)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryService(db)
        self.activity = ActivityService(db)

    def _require_warehouse(self, warehouse_id: uuid.UUID) -> Warehouse:
        wh = self.db.scalar(
            select(Warehouse).where(
                Warehouse.id == warehouse_id, Warehouse.deleted_at.is_(None)
            )
        )
        if wh is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        return wh

    def _require_product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def _post(
        self,
        *,
        product: Product,
        warehouse: Warehouse,
        qty_delta: Decimal,
        reason: str,
        actor_id: uuid.UUID | None,
        summary: str,
    ) -> StockAdjustmentResult:
        from app.modules.pricing.service import PricingService

        self.inventory.record_movement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            qty_delta=qty_delta,
            reason=reason,
            ref_type="stock_adjustment",
            ref_id=product.id,
            unit_cost_minor=PricingService(self.db).latest_purchase_minor(product.id),
            actor_id=actor_id,
        )
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="adjusted",
            entity_type="stock",
            entity_id=product.id,
            summary=summary,
            data={"qty_delta": str(qty_delta), "reason": reason, "warehouse": warehouse.code},
        )
        return StockAdjustmentResult(
            product_id=product.id,
            warehouse_id=warehouse.id,
            qty_delta=qty_delta,
            reason=reason,
            on_hand=self.inventory.on_hand(product.id, warehouse.id),
        )

    def adjust(self, payload, *, actor_id: uuid.UUID | None) -> StockAdjustmentResult:
        """Apply a signed correction to on-hand at a warehouse."""
        if payload.qty_delta == 0:
            raise ValidationError("Adjustment quantity must be non-zero")
        reason = (payload.reason or "ADJUSTMENT").upper()
        if reason not in ("ADJUSTMENT", "COUNT"):
            raise ConflictError(f"Unsupported adjustment reason '{reason}'")
        product = self._require_product(payload.product_id)
        warehouse = self._require_warehouse(payload.warehouse_id)
        sign = "+" if payload.qty_delta > 0 else ""
        return self._post(
            product=product,
            warehouse=warehouse,
            qty_delta=Decimal(payload.qty_delta),
            reason=reason,
            actor_id=actor_id,
            summary=(
                f"Adjusted {product.sku_code} at {warehouse.name} "
                f"by {sign}{payload.qty_delta}"
            ),
        )

    def count(self, payload, *, actor_id: uuid.UUID | None) -> StockAdjustmentResult:
        """Reconcile on-hand to a physically counted quantity (posts the delta)."""
        product = self._require_product(payload.product_id)
        warehouse = self._require_warehouse(payload.warehouse_id)
        current = self.inventory.on_hand(product.id, warehouse.id)
        delta = Decimal(payload.counted_qty) - current
        if delta == 0:
            raise ConflictError(
                f"Counted quantity matches on-hand ({current}); nothing to reconcile"
            )
        return self._post(
            product=product,
            warehouse=warehouse,
            qty_delta=delta,
            reason="COUNT",
            actor_id=actor_id,
            summary=(
                f"Cycle count {product.sku_code} at {warehouse.name}: "
                f"{current} → {payload.counted_qty}"
            ),
        )
