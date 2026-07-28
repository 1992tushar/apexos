"""Procurement services — the buy-side state machine (mirror of Sales).

create → confirm → receive (stock IN) → bill. Each transition emits one
activity_log row (D10). Money is integer minor units; tax is basis points off
each line subtotal. `PurchaseOrderService` owns create/confirm/bill;
`GoodsReceiptService.receive` posts the IN movement (partial receipts allowed).
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.money import qty_text, round_minor
from app.modules.activity.service import ActivityService
from app.modules.config.models import TaxRate, Warehouse
from app.modules.config.service import allocate_document_number
from app.modules.config.service import default_business_unit as _default_business_unit
from app.modules.finance.models import Bill, BillLine
from app.modules.inventory.service import InventoryService
from app.modules.pricing.service import PricingService
from app.modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderRevision,
    PurchaseOrderRevisionLine,
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
    PurchaseOrderRevise,
    PurchaseOrderRevisionLineRead,
    PurchaseOrderRevisionRead,
)
from app.modules.products.models import Product
from app.modules.suppliers.models import Supplier

# Moved to `app.core.money` in Part 5 C2, same reason as `_qty_text` below: inventory
# valuation needs it and cannot import this module. Re-exported under the original name,
# so this module's call sites are unchanged and there is still ONE rounding step (G1).
_round_minor = round_minor


# Moved to `app.core.money` in Part 5 C1 so the inventory module can use it too —
# inventory cannot import this module (it would be circular). Re-exported under the
# original name: this module's own call sites, and `recommend.py`'s import of it, are
# unchanged, and there is still exactly one implementation.
_qty_text = qty_text


# Moved to `app.modules.config.service` in Part 5 C3 so inventory can number its transfer
# and count documents — inventory cannot import this module (circular). Re-exported under
# the original name, so `preorder.py` and this module's callers are unchanged.
default_business_unit = _default_business_unit


def tax_bps_for(db: Session, product: Product) -> int:
    """The product's default GST rate in basis points, or 0 if it has none.

    Module-level because the pre-order half (`preorder.py`) prices quotation lines
    the same way a PO line is priced; one lookup, so a quote and the PO it becomes
    can never disagree about the tax rate.
    """
    if product.default_tax_rate_id is None:
        return 0
    return (
        db.scalar(select(TaxRate.rate_bps).where(TaxRate.id == product.default_tax_rate_id))
        or 0
    )


class PurchaseOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProcurementRepository(db)
        self.pricing = PricingService(db)
        self.activity = ActivityService(db)

    # -- helpers ---------------------------------------------------------
    def _default_bu(self) -> uuid.UUID:
        return default_business_unit(self.db)

    def _product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def _tax_bps(self, product: Product) -> int:
        return tax_bps_for(self.db, product)

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

    @staticmethod
    def open_qty(line: PurchaseOrderLine) -> Decimal:
        """R4.9 — the back order for one line, derived (G7).

        Clamped at zero: a revision that cuts a line down to what already arrived
        must read as "nothing outstanding", not as a negative back order.
        """
        outstanding = Decimal(line.qty) - Decimal(line.qty_received or 0)
        return outstanding if outstanding > 0 else Decimal("0")

    def _to_revision_read(
        self, revision: PurchaseOrderRevision, *, current_no: int
    ) -> PurchaseOrderRevisionRead:
        lines = []
        for ln in revision.lines:
            product = self.db.get(Product, ln.product_id)
            lines.append(
                PurchaseOrderRevisionLineRead(
                    product_id=ln.product_id,
                    product_name=product.name if product else None,
                    sku_code=product.sku_code if product else None,
                    qty=ln.qty,
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                    line_no=ln.line_no,
                )
            )
        return PurchaseOrderRevisionRead(
            id=revision.id,
            revision_no=revision.revision_no,
            reason=revision.reason,
            subtotal_minor=revision.subtotal_minor,
            tax_minor=revision.tax_minor,
            total_minor=revision.total_minor,
            created_at=revision.created_at,
            is_current=revision.revision_no == current_no,
            lines=lines,
        )

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
                    open_qty=self.open_qty(ln),
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                )
            )
        revisions = list(order.revisions)
        current_no = revisions[-1].revision_no if revisions else 0
        revision_reads = [self._to_revision_read(r, current_no=current_no) for r in revisions]
        revision_no_by_id = {r.id: r.revision_no for r in revisions}
        goods_receipts = [
            GoodsReceiptRef(
                id=gr.id,
                receipt_no=gr.receipt_no,
                warehouse_id=gr.warehouse_id,
                status=gr.status,
                received_at=gr.received_at,
                revision_no=revision_no_by_id.get(gr.purchase_order_revision_id),
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
            confirmed_at=order.confirmed_at,
            subtotal_minor=order.subtotal_minor,
            tax_minor=order.tax_minor,
            total_minor=order.total_minor,
            revision_no=current_no,
            open_qty_total=sum((ln.open_qty for ln in line_reads), Decimal("0")),
            lines=line_reads,
            revisions=revision_reads,
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
    def _snapshot_revision(
        self,
        order: PurchaseOrder,
        *,
        reason: str | None,
        actor_id: uuid.UUID | None,
    ) -> PurchaseOrderRevision:
        """Append a verbatim copy of the order's current lines as the next revision.

        Writes no `activity_log` row of its own — the verb that calls it (confirm or
        revise) owns the single row G5 allows for that state change.
        """
        next_no = (order.revisions[-1].revision_no + 1) if order.revisions else 1
        revision = PurchaseOrderRevision(
            purchase_order_id=order.id,
            revision_no=next_no,
            reason=reason,
            subtotal_minor=order.subtotal_minor,
            tax_minor=order.tax_minor,
            total_minor=order.total_minor,
            created_by=actor_id,
        )
        for ln in order.lines:
            revision.lines.append(
                PurchaseOrderRevisionLine(
                    product_id=ln.product_id,
                    qty=ln.qty,
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                    line_no=ln.line_no,
                    created_by=actor_id,
                )
            )
        order.revisions.append(revision)
        self.db.flush()
        return revision

    def confirm(
        self,
        order_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        confirmed_at: datetime | None = None,
        expected_date: date | None = None,
    ) -> PurchaseOrderDetail:
        """Confirm a draft order.

        `confirmed_at` and `expected_date` are optional INPUTS, not derived values.
        An order confirmed on the phone yesterday and entered this morning really was
        confirmed yesterday, and the supplier really did promise a date — pretending
        otherwise would corrupt the lead time part 4 measures from this instant.
        Both default to "now" / "nothing promised". Passing `confirmed_at` is how the
        seed fabricates history at INSERT time rather than UPDATE-ing a ledger (G4).
        """
        order = self._require(order_id)
        if order.status != "draft":
            raise ConflictError(f"Cannot confirm purchase order in status '{order.status}'")
        order.status = "confirmed"
        # R4.11: the instant part 4 measures lead time from. Deliberately its own
        # column — `updated_at` is overwritten by the first receipt.
        order.confirmed_at = confirmed_at or datetime.now(UTC)
        # R5.4/R5.7: what the supplier committed to for THIS order. Not a lead-time
        # field (R5.3) — lead time stays measured from confirm → receipt.
        if expected_date is not None:
            order.expected_date = expected_date
        order.updated_by = actor_id
        # R4.7: revision 1 is the agreement as confirmed, and the baseline every
        # receipt and later revision is read against.
        self._snapshot_revision(order, reason=None, actor_id=actor_id)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="confirmed",
            entity_type="purchase_order",
            entity_id=order.id,
            summary=f"Purchase order {order.po_no} confirmed",
        )
        return self._to_detail(order)

    # -- revise ----------------------------------------------------------
    def revise(
        self,
        order_id: uuid.UUID,
        payload: PurchaseOrderRevise,
        *,
        actor_id: uuid.UUID | None,
    ) -> PurchaseOrderDetail:
        """R4.7 — change a confirmed PO by appending a revision, never in place.

        Lines are matched by product: a product already on the order has its
        quantity and price updated, one that is not is added. Omitted lines keep
        what they had. There is no line *removal* — cutting a quantity down to what
        has already arrived is the real-world equivalent and is allowed; cutting
        below it is refused, because that would make the back order negative and
        contradict receipts that already posted stock.
        """
        order = self._require(order_id)
        if order.status not in ("confirmed", "partially_received"):
            raise ConflictError(
                f"Cannot revise purchase order in status '{order.status}' — "
                "only a confirmed or partially received order has an agreement to change"
            )
        reason = payload.reason.strip()
        if not reason:
            raise ValidationError("A revision needs a reason")

        lines_by_product = {ln.product_id: ln for ln in order.lines}
        next_line_no = max((ln.line_no for ln in order.lines), default=0) + 1

        for item in payload.lines:
            product = self._product(item.product_id)
            line = lines_by_product.get(item.product_id)
            if line is None:
                unit = item.unit_price_minor
                if unit is None:
                    unit = self.pricing.resolve_purchase_minor(
                        product.id, supplier_id=order.supplier_id
                    )
                if unit is None:
                    raise ValidationError(
                        f"No purchase price for product {product.sku_code}; "
                        "pass unit_price_minor"
                    )
                line = PurchaseOrderLine(
                    product_id=product.id,
                    qty=item.qty,
                    qty_received=Decimal("0"),
                    unit_price_minor=unit,
                    tax_rate_bps=self._tax_bps(product),
                    line_no=next_line_no,
                    created_by=actor_id,
                )
                order.lines.append(line)
                lines_by_product[product.id] = line
                next_line_no += 1
            else:
                already = Decimal(line.qty_received or 0)
                if item.qty < already:
                    raise ValidationError(
                        f"Cannot revise {product.sku_code} down to {_qty_text(item.qty)}: "
                        f"{_qty_text(already)} has already been received"
                    )
                line.qty = item.qty
                if item.unit_price_minor is not None:
                    line.unit_price_minor = item.unit_price_minor
                line.updated_by = actor_id

        # Re-price every line with the same integer arithmetic `create` uses (G1),
        # so a revision cannot drift from the order it revises.
        subtotal = tax_total = grand = 0
        for ln in order.lines:
            ln.line_subtotal_minor = _round_minor(Decimal(ln.qty) * Decimal(ln.unit_price_minor))
            ln.line_tax_minor = _round_minor(
                Decimal(ln.line_subtotal_minor) * Decimal(ln.tax_rate_bps) / Decimal(10000)
            )
            ln.line_total_minor = ln.line_subtotal_minor + ln.line_tax_minor
            subtotal += ln.line_subtotal_minor
            tax_total += ln.line_tax_minor
            grand += ln.line_total_minor
        order.subtotal_minor = subtotal
        order.tax_minor = tax_total
        order.total_minor = grand
        order.updated_by = actor_id

        # Cutting the balance of a part-delivered order down to what actually
        # arrived closes it. (The reverse — reopening a fully received order — is
        # not reachable: the status guard above rejects `received`, because more
        # goods after a complete delivery is a new order, not a revision.)
        if any(Decimal(ln.qty_received or 0) > 0 for ln in order.lines):
            fully = all(self.open_qty(ln) == 0 for ln in order.lines)
            order.status = "received" if fully else "partially_received"

        revision = self._snapshot_revision(order, reason=reason, actor_id=actor_id)
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="revised",
            entity_type="purchase_order",
            entity_id=order.id,
            summary=(
                f"Purchase order {order.po_no} revised to version "
                f"{revision.revision_no} ({reason})"
            ),
            data={
                "revision_no": revision.revision_no,
                "reason": reason,
                "total_minor": grand,
            },
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

        # R4.10 — which version of the order these goods were checked against.
        current = order.revisions[-1] if order.revisions else None
        named = payload.against_revision_no if payload is not None else None
        if named is not None:
            current_no = current.revision_no if current else 0
            if named != current_no:
                raise ConflictError(
                    f"Purchase order {order.po_no} is now at revision {current_no}, but this "
                    f"receipt was checked against revision {named}. Re-check the delivery "
                    f"against the current order before receiving it."
                )

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
                outstanding = PurchaseOrderService.open_qty(line)
                if item.qty > outstanding:
                    product = self.db.get(Product, item.product_id)
                    raise ValidationError(
                        f"Receiving {_qty_text(item.qty)} of "
                        f"{product.sku_code if product else 'a line'} exceeds the "
                        f"{_qty_text(outstanding)} still outstanding"
                    )
                requested[item.product_id] = Decimal(item.qty)
        else:
            for line in order.lines:
                outstanding = PurchaseOrderService.open_qty(line)
                if outstanding > 0:
                    requested[line.product_id] = outstanding

        if not requested:
            raise ValidationError("Nothing outstanding to receive on this purchase order")

        warehouse_id = self._default_warehouse()
        receipt = GoodsReceipt(
            purchase_order_id=order.id,
            purchase_order_revision_id=current.id if current else None,
            warehouse_id=warehouse_id,
            receipt_no=allocate_document_number(
                self.db, doc_type="GRN", business_unit_id=order.business_unit_id,
                on_date=order.order_date,
            ),
            status="received",
            # R4.11: part 4 measures lead time as this minus `PurchaseOrder.confirmed_at`.
            # Taken from the payload when the delivery physically arrived earlier than
            # it was keyed in; set at INSERT, never patched afterwards (G4).
            received_at=(payload.received_at if payload is not None else None)
            or datetime.now(UTC),
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

        fully = all(PurchaseOrderService.open_qty(ln) == 0 for ln in order.lines)
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
