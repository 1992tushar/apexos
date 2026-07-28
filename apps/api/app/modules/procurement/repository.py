"""Procurement repository (mirror of SalesRepository + goods receipts).

Two classes, matching the service split: `ProcurementRepository` for the PO/GRN
chain, `PreorderRepository` for requisitions, RFQs and quotations. Neither holds
a `search()` — list screens go through `app.db.listing.query_page` (R2.4); what
lives here is detail loading and the *page-at-a-time* aggregates a projection
needs, so a 25-row list costs two queries rather than fifty.
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.modules.config.models import Warehouse
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    Rfq,
    RfqLine,
    RfqSupplier,
    SupplierQuotation,
    SupplierQuotationLine,
)
from app.modules.products.models import Product
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


class PreorderRepository:
    """Reads for the pre-order half: requisitions, RFQs, quotations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- shared lookups -------------------------------------------------
    def require_product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def require_supplier(self, supplier_id: uuid.UUID) -> Supplier:
        supplier = self.db.scalar(
            select(Supplier).where(Supplier.id == supplier_id, Supplier.deleted_at.is_(None))
        )
        if supplier is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        return supplier

    def products_by_id(self, product_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Product]:
        """One query for every product a detail page or projection will name."""
        ids = {pid for pid in product_ids if pid is not None}
        if not ids:
            return {}
        return {
            p.id: p for p in self.db.scalars(select(Product).where(Product.id.in_(ids)))
        }

    def supplier_names(self, supplier_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        ids = {sid for sid in supplier_ids if sid is not None}
        if not ids:
            return {}
        return dict(
            self.db.execute(
                select(Supplier.id, Supplier.name).where(Supplier.id.in_(ids))
            ).all()
        )

    # --- requisitions ---------------------------------------------------
    def get_requisition(self, requisition_id: uuid.UUID) -> PurchaseRequisition | None:
        return self.db.scalar(
            select(PurchaseRequisition)
            .options(selectinload(PurchaseRequisition.lines))
            .where(
                PurchaseRequisition.id == requisition_id,
                PurchaseRequisition.deleted_at.is_(None),
            )
        )

    def requisition_line_aggregates(
        self, requisition_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[int, Decimal]]:
        """(line count, total quantity) per requisition, for a whole page at once."""
        if not requisition_ids:
            return {}
        rows = self.db.execute(
            select(
                PurchaseRequisitionLine.purchase_requisition_id,
                func.count(),
                func.coalesce(func.sum(PurchaseRequisitionLine.qty), 0),
            )
            .where(
                PurchaseRequisitionLine.purchase_requisition_id.in_(requisition_ids),
                PurchaseRequisitionLine.deleted_at.is_(None),
            )
            .group_by(PurchaseRequisitionLine.purchase_requisition_id)
        ).all()
        return {r[0]: (r[1], Decimal(str(r[2]))) for r in rows}

    def requisition_outcomes(
        self, requisition_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """The PO or RFQ number a converted requisition became."""
        if not requisition_ids:
            return {}
        out: dict[uuid.UUID, str] = {}
        for rid, po_no in self.db.execute(
            select(PurchaseRequisition.id, PurchaseOrder.po_no)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseRequisition.purchase_order_id)
            .where(PurchaseRequisition.id.in_(requisition_ids))
        ).all():
            out[rid] = po_no
        for rid, rfq_no in self.db.execute(
            select(PurchaseRequisition.id, Rfq.rfq_no)
            .join(Rfq, Rfq.id == PurchaseRequisition.rfq_id)
            .where(PurchaseRequisition.id.in_(requisition_ids))
        ).all():
            out.setdefault(rid, rfq_no)
        return out

    # --- RFQs + quotations ----------------------------------------------
    def get_rfq(self, rfq_id: uuid.UUID) -> Rfq | None:
        return self.db.scalar(
            select(Rfq)
            .options(selectinload(Rfq.lines), selectinload(Rfq.suppliers))
            .where(Rfq.id == rfq_id, Rfq.deleted_at.is_(None))
        )

    def _counts(self, model, fk: str, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not ids:
            return {}
        column = getattr(model, fk)
        rows = self.db.execute(
            select(column, func.count())
            .where(column.in_(ids), model.deleted_at.is_(None))
            .group_by(column)
        ).all()
        return {r[0]: r[1] for r in rows}

    def rfq_line_counts(self, rfq_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        return self._counts(RfqLine, "rfq_id", rfq_ids)

    def rfq_supplier_counts(self, rfq_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        return self._counts(RfqSupplier, "rfq_id", rfq_ids)

    def rfq_quote_counts(self, rfq_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        return self._counts(SupplierQuotation, "rfq_id", rfq_ids)

    def quotations_for(self, rfq_id: uuid.UUID) -> list[SupplierQuotation]:
        return list(
            self.db.scalars(
                select(SupplierQuotation)
                .options(selectinload(SupplierQuotation.lines))
                .where(
                    SupplierQuotation.rfq_id == rfq_id,
                    SupplierQuotation.deleted_at.is_(None),
                )
                .order_by(SupplierQuotation.total_minor.asc(), SupplierQuotation.created_at.asc())
            )
        )

    def get_quotation(self, quotation_id: uuid.UUID) -> SupplierQuotation | None:
        return self.db.scalar(
            select(SupplierQuotation)
            .options(selectinload(SupplierQuotation.lines))
            .where(
                SupplierQuotation.id == quotation_id,
                SupplierQuotation.deleted_at.is_(None),
            )
        )

    def quotation_for_supplier(
        self, rfq_id: uuid.UUID, supplier_id: uuid.UUID
    ) -> SupplierQuotation | None:
        return self.db.scalar(
            select(SupplierQuotation).where(
                SupplierQuotation.rfq_id == rfq_id,
                SupplierQuotation.supplier_id == supplier_id,
                SupplierQuotation.deleted_at.is_(None),
            )
        )

    def invitation(self, rfq_id: uuid.UUID, supplier_id: uuid.UUID) -> RfqSupplier | None:
        return self.db.scalar(
            select(RfqSupplier).where(
                RfqSupplier.rfq_id == rfq_id,
                RfqSupplier.supplier_id == supplier_id,
                RfqSupplier.deleted_at.is_(None),
            )
        )

    def quotation_history_rows(
        self,
        product_id: uuid.UUID,
        *,
        supplier_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[tuple]:
        """Every quote for one product (R4.6), newest first, optionally one supplier."""
        stmt = (
            select(
                SupplierQuotation.id,
                SupplierQuotation.quotation_no,
                Rfq.rfq_no,
                SupplierQuotation.supplier_id,
                Supplier.name,
                SupplierQuotation.quoted_on,
                SupplierQuotationLine.unit_price_minor,
                SupplierQuotationLine.moq,
                SupplierQuotation.lead_time_days,
                SupplierQuotation.status,
            )
            .join(
                SupplierQuotation,
                SupplierQuotation.id == SupplierQuotationLine.supplier_quotation_id,
            )
            .join(Supplier, Supplier.id == SupplierQuotation.supplier_id)
            .outerjoin(Rfq, Rfq.id == SupplierQuotation.rfq_id)
            .where(
                SupplierQuotationLine.product_id == product_id,
                SupplierQuotationLine.deleted_at.is_(None),
                SupplierQuotation.deleted_at.is_(None),
            )
            .order_by(SupplierQuotation.quoted_on.desc(), SupplierQuotation.created_at.desc())
            .limit(limit)
        )
        if supplier_id is not None:
            stmt = stmt.where(SupplierQuotation.supplier_id == supplier_id)
        return list(self.db.execute(stmt).all())
