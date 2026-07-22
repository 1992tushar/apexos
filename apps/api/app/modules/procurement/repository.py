"""Procurement repository (mirror of SalesRepository + goods receipts)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.config.models import Warehouse
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.modules.suppliers.models import Supplier


class ProcurementRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- purchase orders ------------------------------------------------
    def add(self, order: PurchaseOrder) -> PurchaseOrder:
        self.db.add(order)
        self.db.flush()
        return order

    def get(self, order_id: uuid.UUID) -> PurchaseOrder | None:
        return self.db.scalar(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(PurchaseOrder.id == order_id, PurchaseOrder.deleted_at.is_(None))
        )

    def supplier_name(self, supplier_id: uuid.UUID) -> str | None:
        return self.db.scalar(select(Supplier.name).where(Supplier.id == supplier_id))

    def search(
        self, *, status: str | None, page: int, page_size: int
    ) -> tuple[list[tuple], int]:
        line_count = (
            select(
                PurchaseOrderLine.purchase_order_id.label("po_id"),
                func.count().label("cnt"),
            )
            .group_by(PurchaseOrderLine.purchase_order_id)
            .subquery()
        )
        base = (
            select(
                PurchaseOrder.id,
                PurchaseOrder.po_no,
                Supplier.name,
                PurchaseOrder.status,
                PurchaseOrder.total_minor,
                PurchaseOrder.order_date,
                func.coalesce(line_count.c.cnt, 0),
            )
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .outerjoin(line_count, line_count.c.po_id == PurchaseOrder.id)
            .where(PurchaseOrder.deleted_at.is_(None))
        )
        if status:
            base = base.where(PurchaseOrder.status == status)

        count_base = select(func.count()).select_from(PurchaseOrder).where(
            PurchaseOrder.deleted_at.is_(None)
        )
        if status:
            count_base = count_base.where(PurchaseOrder.status == status)
        total = self.db.scalar(count_base) or 0
        rows = list(
            self.db.execute(
                base.order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.po_no.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return rows, total

    def pending_count(self) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(
                PurchaseOrder.status.in_(["draft", "confirmed", "partially_received"]),
                PurchaseOrder.deleted_at.is_(None),
            )
        ) or 0

    # --- goods receipts -------------------------------------------------
    def add_receipt(self, receipt: GoodsReceipt) -> GoodsReceipt:
        self.db.add(receipt)
        self.db.flush()
        return receipt

    def receipts_for(self, purchase_order_id: uuid.UUID) -> list[GoodsReceipt]:
        return list(
            self.db.scalars(
                select(GoodsReceipt)
                .where(
                    GoodsReceipt.purchase_order_id == purchase_order_id,
                    GoodsReceipt.deleted_at.is_(None),
                )
                .order_by(GoodsReceipt.created_at.asc())
            )
        )

    def receipt_rows(self) -> list[tuple]:
        """All goods receipts enriched with PO + supplier + warehouse display fields."""
        line_count = (
            select(
                GoodsReceiptLine.goods_receipt_id.label("gr_id"),
                func.count().label("cnt"),
            )
            .group_by(GoodsReceiptLine.goods_receipt_id)
            .subquery()
        )
        stmt = (
            select(
                GoodsReceipt.id,
                GoodsReceipt.receipt_no,
                GoodsReceipt.purchase_order_id,
                PurchaseOrder.po_no,
                Supplier.name,
                Warehouse.name,
                GoodsReceipt.status,
                GoodsReceipt.received_at,
                func.coalesce(line_count.c.cnt, 0),
            )
            .join(PurchaseOrder, PurchaseOrder.id == GoodsReceipt.purchase_order_id)
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .join(Warehouse, Warehouse.id == GoodsReceipt.warehouse_id)
            .outerjoin(line_count, line_count.c.gr_id == GoodsReceipt.id)
            .where(GoodsReceipt.deleted_at.is_(None))
            .order_by(GoodsReceipt.received_at.desc().nullslast(), GoodsReceipt.created_at.desc())
        )
        return list(self.db.execute(stmt).all())
