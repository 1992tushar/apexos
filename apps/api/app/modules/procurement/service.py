"""Procurement services — the buy-side state machine (mirror of Sales).

create → confirm → receive (stock IN) → bill. Each transition emits one
activity_log row (D10). Money is integer minor units; tax is basis points off
each line subtotal. `PurchaseOrderService` owns create/confirm/bill;
`GoodsReceiptService.receive` posts the IN movement (partial receipts allowed).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit, TaxRate, Warehouse
from app.modules.config.service import allocate_document_number
from app.modules.finance.models import Bill, BillLine
from app.modules.inventory.service import InventoryService
from app.modules.pricing.service import PricingService
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.modules.procurement.repository import ProcurementRepository
from app.modules.procurement.schemas import (
    BillRef,
    GoodsReceiptCreate,
    GoodsReceiptListRow,
    GoodsReceiptRef,
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderLineRead,
    PurchaseOrderListRow,
)
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier


def _round_minor(value: Decimal) -> int:
    return int(value.quantize(Decimal("1")))


class PurchaseOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProcurementRepository(db)
        self.pricing = PricingService(db)
        self.activity = ActivityService(db)

    # -- helpers ---------------------------------------------------------
    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    def _product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def _tax_bps(self, product: Product) -> int:
        if product.default_tax_rate_id is None:
            return 0
        return (
            self.db.scalar(
                select(TaxRate.rate_bps).where(TaxRate.id == product.default_tax_rate_id)
            )
            or 0
        )

    # -- reads -----------------------------------------------------------
    def list(self, *, status: str | None, page: int, page_size: int):
        rows, total = self.repo.search(status=status, page=page, page_size=page_size)
        items = [
            PurchaseOrderListRow(
                id=r[0],
                po_no=r[1],
                supplier_name=r[2],
                status=r[3],
                total_minor=r[4],
                order_date=r[5],
                line_count=r[6],
            )
            for r in rows
        ]
        return items, total

    def _to_detail(self, order: PurchaseOrder) -> PurchaseOrderDetail:
        line_reads: list[PurchaseOrderLineRead] = []
        for ln in order.lines:
            product = self.db.get(Product, ln.product_id)
            line_reads.append(
                PurchaseOrderLineRead(
                    id=ln.id,
                    product_id=ln.product_id,
                    product_name=product.name if product else None,
                    sku_code=product.sku_code if product else None,
                    qty=ln.qty,
                    qty_received=ln.qty_received,
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                )
            )
        goods_receipts = [
            GoodsReceiptRef(
                id=gr.id,
                receipt_no=gr.receipt_no,
                warehouse_id=gr.warehouse_id,
                status=gr.status,
                received_at=gr.received_at,
            )
            for gr in self.repo.receipts_for(order.id)
        ]
        bills = [
            BillRef(
                id=b.id,
                bill_no=b.bill_no,
                status=b.status,
                total_minor=b.total_minor,
            )
            for b in self.db.scalars(
                select(Bill).where(
                    Bill.purchase_order_id == order.id, Bill.deleted_at.is_(None)
                )
            )
        ]
        return PurchaseOrderDetail(
            id=order.id,
            po_no=order.po_no,
            supplier_id=order.supplier_id,
            supplier_name=self.repo.supplier_name(order.supplier_id),
            business_unit_id=order.business_unit_id,
            status=order.status,
            order_date=order.order_date,
            subtotal_minor=order.subtotal_minor,
            tax_minor=order.tax_minor,
            total_minor=order.total_minor,
            lines=line_reads,
            goods_receipts=goods_receipts,
            bills=bills,
        )

    def get(self, order_id: uuid.UUID) -> PurchaseOrderDetail:
        order = self._require(order_id)
        return self._to_detail(order)

    def _require(self, order_id: uuid.UUID) -> PurchaseOrder:
        order = self.repo.get(order_id)
        if order is None:
            raise NotFoundError(f"Purchase order {order_id} not found")
        return order

    # -- create ----------------------------------------------------------
    def create(
        self, payload: PurchaseOrderCreate, *, actor_id: uuid.UUID | None
    ) -> PurchaseOrderDetail:
        supplier = self.db.scalar(
            select(Supplier).where(
                Supplier.id == payload.supplier_id, Supplier.deleted_at.is_(None)
            )
        )
        if supplier is None:
            raise NotFoundError(f"Supplier {payload.supplier_id} not found")

        bu = payload.business_unit_id or supplier.business_unit_id or self._default_bu()
        order_date = payload.order_date or datetime.now(UTC).date()
        po_no = allocate_document_number(
            self.db, doc_type="PO", business_unit_id=bu, on_date=order_date
        )
        order = PurchaseOrder(
            supplier_id=supplier.id,
            po_no=po_no,
            order_date=order_date,
            status="draft",
            business_unit_id=bu,
            created_by=actor_id,
        )

        subtotal = tax_total = grand = 0
        for i, line in enumerate(payload.lines, start=1):
            product = self._product(line.product_id)
            # Snapshot the effective purchase price onto the line (supplier-specific
            # first, else the product's current buy price).
            unit = line.unit_price_minor
            if unit is None:
                unit = self.pricing.resolve_purchase_minor(product.id, supplier_id=supplier.id)
            if unit is None:
                raise ValidationError(
                    f"No purchase price for product {product.sku_code}; pass unit_price_minor"
                )
            rate_bps = self._tax_bps(product)
            line_subtotal = _round_minor(line.qty * Decimal(unit))
            line_tax = _round_minor(Decimal(line_subtotal) * Decimal(rate_bps) / Decimal(10000))
            line_total = line_subtotal + line_tax
            order.lines.append(
                PurchaseOrderLine(
                    product_id=product.id,
                    qty=line.qty,
                    qty_received=Decimal("0"),
                    unit_price_minor=unit,
                    tax_rate_bps=rate_bps,
                    line_subtotal_minor=line_subtotal,
                    line_tax_minor=line_tax,
                    line_total_minor=line_total,
                    line_no=i,
                    created_by=actor_id,
                )
            )
            subtotal += line_subtotal
            tax_total += line_tax
            grand += line_total

        order.subtotal_minor = subtotal
        order.tax_minor = tax_total
        order.total_minor = grand
        self.repo.add(order)

        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="purchase_order",
            entity_id=order.id,
            summary=f"Purchase order {order.po_no} created ({grand} minor)",
            data={"total_minor": grand, "lines": len(order.lines)},
        )
        return self._to_detail(order)

    # -- confirm ---------------------------------------------------------
    def confirm(self, order_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> PurchaseOrderDetail:
        order = self._require(order_id)
        if order.status != "draft":
            raise ConflictError(f"Cannot confirm purchase order in status '{order.status}'")
        order.status = "confirmed"
        order.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="confirmed",
            entity_type="purchase_order",
            entity_id=order.id,
            summary=f"Purchase order {order.po_no} confirmed",
        )
        return self._to_detail(order)

    # -- bill ------------------------------------------------------------
    def bill(self, order_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> PurchaseOrderDetail:
        """Issue a supplier bill from the received quantities (mirror of
        SalesOrderService.invoice). Bills what has actually been received."""
        order = self._require(order_id)
        if order.status not in ("received", "partially_received"):
            raise ConflictError(f"Cannot bill purchase order in status '{order.status}'")

        billable = [ln for ln in order.lines if ln.qty_received and ln.qty_received > 0]
        if not billable:
            raise ValidationError("Nothing received yet; receive goods before billing")

        due = order.order_date + timedelta(days=30)
        bill = Bill(
            supplier_id=order.supplier_id,
            purchase_order_id=order.id,
            bill_no=allocate_document_number(
                self.db, doc_type="BILL", business_unit_id=order.business_unit_id,
                on_date=order.order_date,
            ),
            bill_date=order.order_date,
            due_date=due,
            status="issued",
            business_unit_id=order.business_unit_id,
            created_by=actor_id,
        )
        subtotal = tax_total = grand = 0
        for i, ln in enumerate(billable, start=1):
            line_subtotal = _round_minor(ln.qty_received * Decimal(ln.unit_price_minor))
            line_tax = _round_minor(
                Decimal(line_subtotal) * Decimal(ln.tax_rate_bps) / Decimal(10000)
            )
            line_total = line_subtotal + line_tax
            bill.lines.append(
                BillLine(
                    product_id=ln.product_id,
                    qty=ln.qty_received,
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=line_subtotal,
                    line_tax_minor=line_tax,
                    line_total_minor=line_total,
                    line_no=i,
                    created_by=actor_id,
                )
            )
            subtotal += line_subtotal
            tax_total += line_tax
            grand += line_total
        bill.subtotal_minor = subtotal
        bill.tax_minor = tax_total
        bill.total_minor = grand
        self.db.add(bill)

        order.status = "billed"
        order.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="billed",
            entity_type="purchase_order",
            entity_id=order.id,
            summary=f"Purchase order {order.po_no} billed ({bill.bill_no})",
            data={"bill_no": bill.bill_no, "total_minor": bill.total_minor},
        )
        return self._to_detail(order)


class GoodsReceiptService:
    """Receives goods against a purchase order, posting the IN stock movement
    through InventoryService. Partial receipts are allowed — each line accrues
    `qty_received` until the ordered quantity is met."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProcurementRepository(db)
        self.inventory = InventoryService(db)
        self.activity = ActivityService(db)

    def _default_warehouse(self) -> uuid.UUID:
        wh = self.db.scalar(
            select(Warehouse.id).where(Warehouse.deleted_at.is_(None)).limit(1)
        )
        if wh is None:
            raise NotFoundError("No warehouse configured; run the seed first.")
        return wh

    def receive(
        self,
        order_id: uuid.UUID,
        payload: GoodsReceiptCreate | None = None,
        *,
        actor_id: uuid.UUID | None,
    ) -> PurchaseOrderDetail:
        order = self.repo.get(order_id)
        if order is None:
            raise NotFoundError(f"Purchase order {order_id} not found")
        if order.status not in ("confirmed", "partially_received"):
            raise ConflictError(f"Cannot receive purchase order in status '{order.status}'")

        lines_by_product = {ln.product_id: ln for ln in order.lines}

        # Determine the quantity to receive per line.
        requested: dict[uuid.UUID, Decimal] = {}
        if payload is not None and payload.lines:
            for item in payload.lines:
                line = lines_by_product.get(item.product_id)
                if line is None:
                    raise ValidationError(
                        f"Product {item.product_id} is not on purchase order {order.po_no}"
                    )
                outstanding = Decimal(line.qty) - Decimal(line.qty_received or 0)
                if item.qty > outstanding:
                    raise ValidationError(
                        f"Receiving {item.qty} exceeds outstanding {outstanding} for a line"
                    )
                requested[item.product_id] = Decimal(item.qty)
        else:
            for line in order.lines:
                outstanding = Decimal(line.qty) - Decimal(line.qty_received or 0)
                if outstanding > 0:
                    requested[line.product_id] = outstanding

        if not requested:
            raise ValidationError("Nothing outstanding to receive on this purchase order")

        warehouse_id = self._default_warehouse()
        receipt = GoodsReceipt(
            purchase_order_id=order.id,
            warehouse_id=warehouse_id,
            receipt_no=allocate_document_number(
                self.db, doc_type="GRN", business_unit_id=order.business_unit_id,
                on_date=order.order_date,
            ),
            status="received",
            received_at=datetime.now(UTC),
            created_by=actor_id,
        )
        for product_id, qty in requested.items():
            receipt.lines.append(
                GoodsReceiptLine(product_id=product_id, qty=qty, created_by=actor_id)
            )
        self.repo.add_receipt(receipt)

        # Post one IN movement per received line and accrue qty_received.
        for product_id, qty in requested.items():
            line = lines_by_product[product_id]
            self.inventory.record_movement(
                product_id=product_id,
                warehouse_id=warehouse_id,
                qty_delta=Decimal(qty),
                reason="PURCHASE",
                ref_type="goods_receipt",
                ref_id=receipt.id,
                unit_cost_minor=line.unit_price_minor,
                actor_id=actor_id,
            )
            line.qty_received = Decimal(line.qty_received or 0) + Decimal(qty)

        fully = all(
            Decimal(ln.qty_received or 0) >= Decimal(ln.qty) for ln in order.lines
        )
        order.status = "received" if fully else "partially_received"
        order.updated_by = actor_id
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="received",
            entity_type="goods_receipt",
            entity_id=receipt.id,
            summary=f"Goods receipt {receipt.receipt_no} against {order.po_no}",
            data={"purchase_order": order.po_no, "lines": len(receipt.lines)},
        )
        return PurchaseOrderService(self.db)._to_detail(order)

    def list_all(self) -> list[GoodsReceiptListRow]:
        rows = []
        for r in self.repo.receipt_rows():
            rows.append(
                GoodsReceiptListRow(
                    id=r[0],
                    receipt_no=r[1],
                    purchase_order_id=r[2],
                    po_no=r[3],
                    supplier_name=r[4],
                    warehouse_name=r[5],
                    status=r[6],
                    received_at=r[7],
                    line_count=r[8],
                )
            )
        return rows
