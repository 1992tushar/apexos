"""Quotation: the gap BEFORE the order (R9.1–R9.3).

create → send → (revise…) → convert, or → expire.

Three decisions worth reading before changing anything here:

* **Revisions mirror Part 3's purchase-order shape rather than inventing a second idiom.**
  Append-only rows, current = `max(revision_no)`, no `superseded_at`. Part 6 introduced a
  different versioning style for credit terms (`valid_from`/`valid_to`) because a policy is
  a *period* — it applies between two dates. A quotation revision is a *sequence* of offers,
  which is what Part 3 already modelled, so this reuses that. **Two idioms is enough; do not
  add a third.**
* **`revision_no` 1 is written by `send`, not `create`.** A draft nobody has seen has no
  agreement to preserve — the same reasoning R4.7 used for an unconfirmed PO. A draft is
  therefore edited freely, and `revise` requires a *sent* quotation.
* **Conversion CALLS `SalesOrderService.create`** and passes the quoted `unit_price_minor`
  explicitly (R9.3). It does not rebuild the order, and it does not let the price re-resolve
  from the price list — carrying the quoted price forward is the entire point of quoting, and
  a re-resolve would silently honour today's list price instead of what the customer agreed.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.money import round_minor
from app.modules.activity.service import ActivityService
from app.modules.config.service import allocate_document_number, default_business_unit
from app.modules.customers.models import Customer
from app.modules.products.models import Product
from app.modules.sales.models import (
    Quotation,
    QuotationLine,
    QuotationRevision,
    QuotationRevisionLine,
    SalesOrder,
)
from app.modules.sales.schemas import (
    QuotationDetail,
    QuotationLineRead,
    QuotationListRow,
    QuotationRevisionRead,
    SalesOrderCreate,
    SalesOrderLineCreate,
)

# Its own document type. `QUO` already numbers Part 3's SUPPLIER quotations, and sharing it
# would interleave two unrelated sequences in `number_sequence`.
DOC_TYPE = "SQT"

# A quotation can still become an order while it is in one of these.
OPEN_STATUSES: tuple[str, ...] = ("draft", "sent")


class QuotationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.activity = ActivityService(db)

    # --- helpers ---------------------------------------------------------

    def _require(self, quotation_id: uuid.UUID) -> Quotation:
        row = self.db.scalar(
            select(Quotation).where(
                Quotation.id == quotation_id, Quotation.deleted_at.is_(None)
            )
        )
        if row is None:
            raise NotFoundError(f"Quotation {quotation_id} not found")
        return row

    def _customer(self, customer_id: uuid.UUID) -> Customer:
        customer = self.db.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.deleted_at.is_(None)
            )
        )
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        return customer

    def _product(self, product_id: uuid.UUID) -> Product:
        product = self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    def _price_lines(self, quotation: Quotation, payload_lines, customer: Customer, actor_id):
        """Build priced `QuotationLine`s and return them with the three totals.

        Money is integer minor units throughout and rounds through the ONE rounding step
        (G1) — the same arithmetic `SalesOrderService.create` uses, so a quotation and the
        order it becomes cannot disagree about tax on the same lines.
        """
        from app.modules.pricing.service import PricingService
        from app.modules.sales.service import SalesOrderService

        pricing = PricingService(self.db)
        tax_for = SalesOrderService(self.db)._tax_bps

        lines: list[QuotationLine] = []
        subtotal = tax_total = grand = 0
        for i, item in enumerate(payload_lines, start=1):
            product = self._product(item.product_id)
            unit = item.unit_price_minor
            if unit is None:
                unit = pricing.resolve_selling_minor(
                    product.id,
                    customer_id=customer.id,
                    customer_type_id=customer.customer_type_id,
                )
            if unit is None:
                raise ValidationError(
                    f"No selling price for {product.sku_code}; quote a unit price explicitly"
                )
            rate_bps = tax_for(product, customer.customer_type_id)
            line_subtotal = round_minor(Decimal(item.qty) * Decimal(unit))
            line_tax = round_minor(
                Decimal(line_subtotal) * Decimal(rate_bps) / Decimal(10000)
            )
            line_total = line_subtotal + line_tax
            lines.append(
                QuotationLine(
                    product_id=product.id,
                    qty=item.qty,
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
        return lines, subtotal, tax_total, grand

    def _snapshot(self, quotation: Quotation, *, reason: str | None, actor_id) -> QuotationRevision:
        """Append a verbatim copy of the current lines as the next revision (R9.2)."""
        next_no = (
            max((r.revision_no for r in quotation.revisions), default=0) + 1
        )
        revision = QuotationRevision(
            quotation_id=quotation.id,
            revision_no=next_no,
            reason=reason,
            subtotal_minor=quotation.subtotal_minor,
            tax_minor=quotation.tax_minor,
            total_minor=quotation.total_minor,
            created_by=actor_id,
        )
        for line in quotation.lines:
            revision.lines.append(
                QuotationRevisionLine(
                    product_id=line.product_id,
                    qty=line.qty,
                    unit_price_minor=line.unit_price_minor,
                    tax_rate_bps=line.tax_rate_bps,
                    line_subtotal_minor=line.line_subtotal_minor,
                    line_tax_minor=line.line_tax_minor,
                    line_total_minor=line.line_total_minor,
                    line_no=line.line_no,
                    created_by=actor_id,
                )
            )
        quotation.revisions.append(revision)
        self.db.flush()
        return revision

    # --- reads -----------------------------------------------------------

    def _line_reads(self, lines) -> list[QuotationLineRead]:
        out: list[QuotationLineRead] = []
        for line in lines:
            product = self.db.get(Product, line.product_id)
            out.append(
                QuotationLineRead(
                    product_id=line.product_id,
                    product_name=product.name if product else None,
                    sku_code=product.sku_code if product else None,
                    qty=line.qty,
                    unit_price_minor=line.unit_price_minor,
                    tax_rate_bps=line.tax_rate_bps,
                    line_subtotal_minor=line.line_subtotal_minor,
                    line_tax_minor=line.line_tax_minor,
                    line_total_minor=line.line_total_minor,
                    line_no=line.line_no,
                )
            )
        return out

    def _to_detail(self, quotation: Quotation) -> QuotationDetail:
        customer = self.db.get(Customer, quotation.customer_id)
        order = (
            self.db.get(SalesOrder, quotation.sales_order_id)
            if quotation.sales_order_id
            else None
        )
        current_no = max((r.revision_no for r in quotation.revisions), default=0)
        return QuotationDetail(
            id=quotation.id,
            quotation_no=quotation.quotation_no,
            customer_id=quotation.customer_id,
            customer_name=customer.name if customer else None,
            quotation_date=quotation.quotation_date,
            valid_until=quotation.valid_until,
            status=quotation.status,
            subtotal_minor=quotation.subtotal_minor,
            tax_minor=quotation.tax_minor,
            total_minor=quotation.total_minor,
            sales_order_id=quotation.sales_order_id,
            sales_order_no=order.order_no if order else None,
            note=quotation.note,
            lines=self._line_reads(quotation.lines),
            revisions=[
                QuotationRevisionRead(
                    id=r.id,
                    revision_no=r.revision_no,
                    reason=r.reason,
                    subtotal_minor=r.subtotal_minor,
                    tax_minor=r.tax_minor,
                    total_minor=r.total_minor,
                    created_at=r.created_at,
                    is_current=r.revision_no == current_no,
                    lines=self._line_reads(r.lines),
                )
                for r in quotation.revisions
            ],
            past_validity=self._past_validity(quotation),
        )

    @staticmethod
    def _past_validity(quotation: Quotation, *, today: date | None = None) -> bool:
        """Whether the validity date has passed — DERIVED (G7), and deliberately distinct
        from `status == "expired"`, which is somebody having actually retired it."""
        if quotation.valid_until is None:
            return False
        return quotation.valid_until < (today or datetime.now(UTC).date())

    def get(self, quotation_id: uuid.UUID) -> QuotationDetail:
        return self._to_detail(self._require(quotation_id))

    def list(self, *, status: str | None = None, limit: int = 100) -> list[QuotationListRow]:
        stmt = select(Quotation).where(Quotation.deleted_at.is_(None))
        if status is not None:
            stmt = stmt.where(Quotation.status == status)
        rows = self.db.scalars(
            stmt.order_by(Quotation.quotation_date.desc(), Quotation.id.desc()).limit(limit)
        )
        out: list[QuotationListRow] = []
        for q in rows:
            customer = self.db.get(Customer, q.customer_id)
            out.append(
                QuotationListRow(
                    id=q.id,
                    quotation_no=q.quotation_no,
                    customer_name=customer.name if customer else None,
                    status=q.status,
                    quotation_date=q.quotation_date,
                    valid_until=q.valid_until,
                    total_minor=q.total_minor,
                    revision_count=len(q.revisions),
                    past_validity=self._past_validity(q),
                )
            )
        return out

    # --- R9.1: create / send / revise / expire ---------------------------

    def create(self, payload, *, actor_id: uuid.UUID | None) -> QuotationDetail:
        customer = self._customer(payload.customer_id)
        bu = payload.business_unit_id or customer.business_unit_id or default_business_unit(self.db)
        quotation_date = payload.quotation_date or datetime.now(UTC).date()
        if payload.valid_until is not None and payload.valid_until < quotation_date:
            raise ValidationError(
                "A quotation cannot expire before the day it was raised"
            )

        quotation = Quotation(
            customer_id=customer.id,
            quotation_no=allocate_document_number(
                self.db, doc_type=DOC_TYPE, business_unit_id=bu, on_date=quotation_date
            ),
            quotation_date=quotation_date,
            valid_until=payload.valid_until,
            status="draft",
            business_unit_id=bu,
            note=payload.note,
            created_by=actor_id,
        )
        lines, subtotal, tax_total, grand = self._price_lines(
            quotation, payload.lines, customer, actor_id
        )
        quotation.lines.extend(lines)
        quotation.subtotal_minor = subtotal
        quotation.tax_minor = tax_total
        quotation.total_minor = grand
        self.db.add(quotation)
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="quotation",
            entity_id=quotation.id,
            summary=f"Quotation {quotation.quotation_no} raised for {customer.name}",
            data={"total_minor": grand, "lines": len(lines)},
        )
        return self._to_detail(quotation)

    def send(self, quotation_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> QuotationDetail:
        """Mark it sent, and preserve what was sent as revision 1 (R9.2)."""
        quotation = self._require(quotation_id)
        if quotation.status != "draft":
            raise ConflictError(
                f"Quotation {quotation.quotation_no} is already {quotation.status}"
            )
        quotation.status = "sent"
        quotation.updated_by = actor_id
        self._snapshot(quotation, reason=None, actor_id=actor_id)

        self.activity.log(
            actor_id=actor_id,
            verb="sent",
            entity_type="quotation",
            entity_id=quotation.id,
            summary=f"Quotation {quotation.quotation_no} sent to the customer",
        )
        return self._to_detail(quotation)

    def revise(
        self, quotation_id: uuid.UUID, payload, *, actor_id: uuid.UUID | None
    ) -> QuotationDetail:
        """Re-quote a sent quotation. Appends a revision; never edits the previous one.

        Requires `sent`: a draft has no agreed version to preserve, so a draft is simply
        edited. Refusing a converted or expired quotation is the point — the customer has
        either already ordered or been told the offer lapsed.
        """
        quotation = self._require(quotation_id)
        if quotation.status != "sent":
            raise ConflictError(
                f"Only a sent quotation can be revised; {quotation.quotation_no} is "
                f"{quotation.status}"
            )
        reason = (payload.reason or "").strip()
        if not reason:
            raise ValidationError(
                "A revision needs a reason — why the price changed is the whole value of "
                "keeping the history"
            )
        customer = self._customer(quotation.customer_id)

        lines, subtotal, tax_total, grand = self._price_lines(
            quotation, payload.lines, customer, actor_id
        )
        # Replace the live lines; the previous figures are already preserved in the
        # revision written when it was sent (or by the previous revise).
        quotation.lines.clear()
        self.db.flush()
        quotation.lines.extend(lines)
        quotation.subtotal_minor = subtotal
        quotation.tax_minor = tax_total
        quotation.total_minor = grand
        if payload.valid_until is not None:
            quotation.valid_until = payload.valid_until
        quotation.updated_by = actor_id
        self.db.flush()

        revision = self._snapshot(quotation, reason=reason, actor_id=actor_id)
        self.activity.log(
            actor_id=actor_id,
            verb="revised",
            entity_type="quotation",
            entity_id=quotation.id,
            summary=(
                f"Quotation {quotation.quotation_no} revised to v{revision.revision_no} "
                f"— {reason}"
            ),
            data={"revision_no": revision.revision_no, "reason": reason},
        )
        return self._to_detail(quotation)

    def expire(self, quotation_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> QuotationDetail:
        """Retire an offer that will not become an order."""
        quotation = self._require(quotation_id)
        if quotation.status not in OPEN_STATUSES:
            raise ConflictError(
                f"Quotation {quotation.quotation_no} is {quotation.status} and cannot expire"
            )
        quotation.status = "expired"
        quotation.updated_by = actor_id
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="expired",
            entity_type="quotation",
            entity_id=quotation.id,
            summary=f"Quotation {quotation.quotation_no} expired",
        )
        return self._to_detail(quotation)

    # --- R9.3: convert ---------------------------------------------------

    def convert(self, quotation_id: uuid.UUID, *, actor_id: uuid.UUID | None):
        """One action: quotation → sales order, carrying the QUOTED prices (R9.3).

        Calls `SalesOrderService.create` rather than assembling an order itself (Part 3's
        decision 2), and passes each `unit_price_minor` explicitly. Letting the order
        re-resolve the price would honour today's price list instead of what the customer
        agreed, which is the one thing a quotation exists to prevent.

        Returns the created `SalesOrderDetail`. One activity row on the QUOTATION for the
        conversion; `create` writes its own on the order (Part 3's decision 3), so two
        entities get one row each and G5 holds without either service knowing about the
        other's log.
        """
        from app.modules.sales.service import SalesOrderService

        quotation = self._require(quotation_id)
        if quotation.status not in OPEN_STATUSES:
            raise ConflictError(
                f"Quotation {quotation.quotation_no} is {quotation.status} and cannot be "
                f"converted"
            )
        if not quotation.lines:
            raise ValidationError(f"Quotation {quotation.quotation_no} has no lines")

        order = SalesOrderService(self.db).create(
            SalesOrderCreate(
                customer_id=quotation.customer_id,
                business_unit_id=quotation.business_unit_id,
                lines=[
                    SalesOrderLineCreate(
                        product_id=line.product_id,
                        qty=line.qty,
                        # The quoted price, explicitly. Not None.
                        unit_price_minor=line.unit_price_minor,
                    )
                    for line in quotation.lines
                ],
            ),
            actor_id=actor_id,
        )

        quotation.status = "converted"
        quotation.sales_order_id = order.id
        quotation.updated_by = actor_id
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="converted",
            entity_type="quotation",
            entity_id=quotation.id,
            summary=(
                f"Quotation {quotation.quotation_no} converted to sales order "
                f"{order.order_no}"
            ),
            data={"sales_order_id": str(order.id), "total_minor": order.total_minor},
        )
        return order
