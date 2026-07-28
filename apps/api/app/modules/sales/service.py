"""Sales order service — the spine state machine.

create → confirm → fulfill → invoice. Each transition emits an activity_log row.
Money is integer minor units; tax is basis points off each line subtotal.
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
from app.modules.customers.models import Customer, CustomerCreditPolicy
from app.modules.finance.models import Invoice, InvoiceLine
from app.modules.fulfillment.models import Fulfillment, FulfillmentLine
from app.modules.inventory.schemas import ReservationCreate
from app.modules.inventory.service import InventoryService, ReservationService
from app.modules.pricing.service import PricingService
from app.modules.products.models import Product
from app.modules.sales.models import SalesOrder, SalesOrderLine
from app.modules.sales.repository import SalesRepository
from app.modules.sales.schemas import (
    FulfillmentRef,
    InvoiceRef,
    SalesOrderCreate,
    SalesOrderDetail,
    SalesOrderLineRead,
    SalesOrderListRow,
)


def _round_minor(value: Decimal) -> int:
    return int(value.quantize(Decimal("1")))


class SalesOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SalesRepository(db)
        self.pricing = PricingService(db)
        self.inventory = InventoryService(db)
        self.activity = ActivityService(db)

    # -- helpers ---------------------------------------------------------
    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    def _default_warehouse(self) -> uuid.UUID:
        wh = self.db.scalar(
            select(Warehouse.id).where(Warehouse.deleted_at.is_(None)).limit(1)
        )
        if wh is None:
            raise NotFoundError("No warehouse configured; run the seed first.")
        return wh

    def _product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def _tax_bps(self, product: Product, customer_type_id: uuid.UUID | None) -> int:
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
            SalesOrderListRow(
                id=r[0],
                order_no=r[1],
                customer_name=r[2],
                status=r[3],
                total_minor=r[4],
                order_date=r[5],
                line_count=r[6],
            )
            for r in rows
        ]
        return items, total

    def _to_detail(self, order: SalesOrder) -> SalesOrderDetail:
        line_reads: list[SalesOrderLineRead] = []
        for ln in order.lines:
            product = self.db.get(Product, ln.product_id)
            line_reads.append(
                SalesOrderLineRead(
                    id=ln.id,
                    product_id=ln.product_id,
                    product_name=product.name if product else None,
                    sku_code=product.sku_code if product else None,
                    qty=ln.qty,
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                )
            )
        fulfillments = [
            FulfillmentRef(
                id=f.id,
                fulfillment_no=f.fulfillment_no,
                warehouse_id=f.warehouse_id,
                status=f.status,
                shipped_at=f.shipped_at,
            )
            for f in self.db.scalars(
                select(Fulfillment).where(Fulfillment.sales_order_id == order.id)
            )
        ]
        invoices = [
            InvoiceRef(
                id=inv.id,
                invoice_no=inv.invoice_no,
                status=inv.status,
                total_minor=inv.total_minor,
            )
            for inv in self.db.scalars(
                select(Invoice).where(Invoice.sales_order_id == order.id)
            )
        ]
        return SalesOrderDetail(
            id=order.id,
            order_no=order.order_no,
            customer_id=order.customer_id,
            customer_name=self.repo.customer_name(order.customer_id),
            business_unit_id=order.business_unit_id,
            status=order.status,
            order_date=order.order_date,
            subtotal_minor=order.subtotal_minor,
            tax_minor=order.tax_minor,
            total_minor=order.total_minor,
            lines=line_reads,
            fulfillments=fulfillments,
            invoices=invoices,
        )

    def get(self, order_id: uuid.UUID) -> SalesOrderDetail:
        order = self.repo.get(order_id)
        if order is None:
            raise NotFoundError(f"Sales order {order_id} not found")
        return self._to_detail(order)

    def _require(self, order_id: uuid.UUID) -> SalesOrder:
        order = self.repo.get(order_id)
        if order is None:
            raise NotFoundError(f"Sales order {order_id} not found")
        return order

    # -- create ----------------------------------------------------------
    def create(self, payload: SalesOrderCreate, *, actor_id: uuid.UUID | None) -> SalesOrderDetail:
        customer = self.db.scalar(
            select(Customer).where(
                Customer.id == payload.customer_id, Customer.deleted_at.is_(None)
            )
        )
        if customer is None:
            raise NotFoundError(f"Customer {payload.customer_id} not found")

        bu = payload.business_unit_id or customer.business_unit_id or self._default_bu()
        order_date = payload.order_date or datetime.now(UTC).date()
        order_no = allocate_document_number(
            self.db, doc_type="SO", business_unit_id=bu, on_date=order_date
        )
        order = SalesOrder(
            customer_id=customer.id,
            order_no=order_no,
            order_date=order_date,
            status="draft",
            business_unit_id=bu,
            created_by=actor_id,
        )

        subtotal = tax_total = grand = 0
        for i, line in enumerate(payload.lines, start=1):
            product = self._product(line.product_id)
            unit = line.unit_price_minor
            if unit is None:
                unit = self.pricing.resolve_selling_minor(
                    product.id,
                    customer_id=customer.id,
                    customer_type_id=customer.customer_type_id,
                )
            if unit is None:
                raise ValidationError(
                    f"No selling price for product {product.sku_code}; pass unit_price_minor"
                )
            rate_bps = self._tax_bps(product, customer.customer_type_id)
            line_subtotal = _round_minor(line.qty * Decimal(unit))
            line_tax = _round_minor(Decimal(line_subtotal) * Decimal(rate_bps) / Decimal(10000))
            line_total = line_subtotal + line_tax
            order.lines.append(
                SalesOrderLine(
                    product_id=product.id,
                    qty=line.qty,
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
            entity_type="sales_order",
            entity_id=order.id,
            summary=f"Sales order {order.order_no} created ({grand} minor)",
            data={"total_minor": grand, "lines": len(order.lines)},
        )
        return self._to_detail(order)

    # -- confirm ---------------------------------------------------------
    def confirm(
        self,
        order_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None,
        credit_override_reason: str | None = None,
    ) -> SalesOrderDetail:
        """Draft -> confirmed, subject to the customer's credit limit (R8.6).

        `CreditPolicyService.enforce` either passes, refuses with the numbers (R8.7), or
        records an override against the customer (R8.8). It raises `ConflictError` on a
        breach with no reason given, so the order stays in draft and nothing is logged —
        a refused confirm must not leave a half-changed order behind.

        **Part 7 (R9.8) reserves stock here.** Do that AFTER this check passes: reserving
        against an order the credit check is about to refuse would leave a reservation
        holding stock for an order that never confirmed.
        """
        order = self._require(order_id)
        if order.status != "draft":
            raise ConflictError(f"Cannot confirm order in status '{order.status}'")

        from app.modules.customers.credit import CreditPolicyService

        CreditPolicyService(self.db).enforce(
            order.customer_id,
            order.total_minor,
            override_reason=credit_override_reason,
            actor_id=actor_id,
            ref_label=order.order_no,
        )

        # R9.8 — reserve stock, AFTER the credit gate. Calls Part 5's verb; there is no
        # flag and no second mechanism (R6.5). A reservation reduces AVAILABLE without
        # touching on-hand, so the stock is committed but has not moved.
        warehouse_id = self._default_warehouse()
        reservations = ReservationService(self.db)
        for ln in order.lines:
            reservations.reserve(
                ReservationCreate(
                    product_id=ln.product_id,
                    warehouse_id=warehouse_id,
                    qty=Decimal(ln.qty),
                    ref_type="sales_order",
                    ref_id=order.id,
                    note=f"Confirmed on {order.order_no}",
                ),
                actor_id=actor_id,
            )

        order.status = "confirmed"
        order.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="confirmed",
            entity_type="sales_order",
            entity_id=order.id,
            summary=f"Sales order {order.order_no} confirmed",
        )
        return self._to_detail(order)

    # -- cancel ----------------------------------------------------------
    def cancel(
        self, order_id: uuid.UUID, *, reason: str, actor_id: uuid.UUID | None
    ) -> SalesOrderDetail:
        """R9.9 — cancelling a confirmed order RELEASES its reservation.

        Only draft or confirmed: once fulfilled the stock has physically left, and undoing
        that is a return (R9.4), not a cancellation. A reason is required for the same
        reason R7.4 and R8.8 require one — a state change nobody can explain later is not
        an audit trail.
        """
        order = self._require(order_id)
        if order.status not in ("draft", "confirmed"):
            raise ConflictError(
                f"Cannot cancel order in status '{order.status}' — stock has already "
                f"shipped; record a return instead"
            )
        if not (reason or "").strip():
            raise ValidationError("Cancelling an order needs a reason")

        if order.status == "confirmed":
            # Release exactly what confirm reserved. A draft never reserved anything.
            warehouse_id = self._default_warehouse()
            reservations = ReservationService(self.db)
            for ln in order.lines:
                reservations.release(
                    ReservationCreate(
                        product_id=ln.product_id,
                        warehouse_id=warehouse_id,
                        qty=Decimal(ln.qty),
                        ref_type="sales_order",
                        ref_id=order.id,
                        note=f"Cancelled {order.order_no}: {reason.strip()}",
                    ),
                    actor_id=actor_id,
                )

        order.status = "cancelled"
        order.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="cancelled",
            entity_type="sales_order",
            entity_id=order.id,
            summary=f"Sales order {order.order_no} cancelled — {reason.strip()}",
            data={"reason": reason.strip()},
        )
        return self._to_detail(order)

    # -- fulfill ---------------------------------------------------------
    def fulfill(self, order_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> SalesOrderDetail:
        order = self._require(order_id)
        if order.status != "confirmed":
            raise ConflictError(f"Cannot fulfill order in status '{order.status}'")
        warehouse_id = self._default_warehouse()
        fulfillment = Fulfillment(
            sales_order_id=order.id,
            warehouse_id=warehouse_id,
            fulfillment_no=allocate_document_number(
                self.db, doc_type="FUL", business_unit_id=order.business_unit_id,
                on_date=order.order_date,
            ),
            status="shipped",
            shipped_at=datetime.now(UTC),
            created_by=actor_id,
        )
        for ln in order.lines:
            fulfillment.lines.append(
                FulfillmentLine(product_id=ln.product_id, qty=ln.qty, created_by=actor_id)
            )
        self.db.add(fulfillment)
        self.db.flush()

        reservations = ReservationService(self.db)
        for ln in order.lines:
            # R9.9 — CONSUME the reservation as the stock actually leaves. Consuming before
            # the movement would briefly show the stock as neither reserved nor gone; after
            # it, both would be true at once. They belong in one pass, reservation first,
            # because `available` is derived from on-hand minus reserved and must never
            # double-count the same units.
            reservations.consume(
                ReservationCreate(
                    product_id=ln.product_id,
                    warehouse_id=warehouse_id,
                    qty=Decimal(ln.qty),
                    ref_type="fulfillment",
                    ref_id=fulfillment.id,
                    note=f"Shipped on {fulfillment.fulfillment_no}",
                ),
                actor_id=actor_id,
            )
            self.inventory.record_movement(
                product_id=ln.product_id,
                warehouse_id=warehouse_id,
                qty_delta=-Decimal(ln.qty),
                reason="SALE",
                ref_type="fulfillment",
                ref_id=fulfillment.id,
                unit_cost_minor=self.pricing.latest_purchase_minor(ln.product_id),
                actor_id=actor_id,
            )

        order.status = "fulfilled"
        order.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="fulfilled",
            entity_type="sales_order",
            entity_id=order.id,
            summary=f"Sales order {order.order_no} fulfilled ({fulfillment.fulfillment_no})",
        )
        return self._to_detail(order)

    # -- invoice ---------------------------------------------------------
    def invoice(self, order_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> SalesOrderDetail:
        order = self._require(order_id)
        if order.status != "fulfilled":
            raise ConflictError(f"Cannot invoice order in status '{order.status}'")

        policy = self.db.scalar(
            select(CustomerCreditPolicy)
            .where(
                CustomerCreditPolicy.customer_id == order.customer_id,
                CustomerCreditPolicy.valid_to.is_(None),
                CustomerCreditPolicy.deleted_at.is_(None),
            )
            .order_by(CustomerCreditPolicy.valid_from.desc())
        )
        terms = policy.payment_terms_days if policy else 0
        due = order.order_date + timedelta(days=terms)

        invoice = Invoice(
            customer_id=order.customer_id,
            sales_order_id=order.id,
            invoice_no=allocate_document_number(
                self.db, doc_type="INV", business_unit_id=order.business_unit_id,
                on_date=order.order_date,
            ),
            invoice_date=order.order_date,
            due_date=due,
            status="issued",
            subtotal_minor=order.subtotal_minor,
            tax_minor=order.tax_minor,
            total_minor=order.total_minor,
            business_unit_id=order.business_unit_id,
            created_by=actor_id,
        )
        for i, ln in enumerate(order.lines, start=1):
            invoice.lines.append(
                InvoiceLine(
                    product_id=ln.product_id,
                    qty=ln.qty,
                    unit_price_minor=ln.unit_price_minor,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                    line_no=i,
                    created_by=actor_id,
                )
            )
        self.db.add(invoice)

        order.status = "invoiced"
        order.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="invoiced",
            entity_type="sales_order",
            entity_id=order.id,
            summary=f"Sales order {order.order_no} invoiced ({invoice.invoice_no})",
            data={"invoice_no": invoice.invoice_no, "total_minor": invoice.total_minor},
        )
        return self._to_detail(order)
