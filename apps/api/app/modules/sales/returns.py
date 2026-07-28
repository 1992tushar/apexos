"""Sales returns and credit notes: the gap AFTER the invoice (R9.4–R9.7).

The rule that shapes everything here: **the original invoice is never mutated** (G4/R9.5).
A return posts stock IN through `InventoryService.record_movement` — the only writer (G8) —
and raises a `CreditNote`. The receivable falls because the credit note is subtracted from
it, not because the invoice was edited down. An invoice is a document the customer already
holds; editing it destroys the record of what was billed.

`returnable` is derived (G7): invoiced minus already returned, clamped at zero. One
definition, the shape `PurchaseOrderService.open_qty` gave back orders — so a partial return
leaves a correct remainder and a second return cannot exceed it.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.money import qty_text, round_minor
from app.modules.activity.service import ActivityService
from app.modules.config.service import allocate_document_number
from app.modules.finance.models import CreditNote, Invoice, InvoiceLine
from app.modules.inventory.service import InventoryService
from app.modules.products.models import Product
from app.modules.sales.models import SalesReturn, SalesReturnLine
from app.modules.sales.schemas import (
    CreditNoteRead,
    ReturnableLine,
    SalesReturnDetail,
    SalesReturnLineRead,
)

DOC_TYPE_RETURN = "RET"
DOC_TYPE_CREDIT = "CRN"


class SalesReturnService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.inventory = InventoryService(db)
        self.activity = ActivityService(db)

    # --- helpers ---------------------------------------------------------

    def _invoice(self, invoice_id: uuid.UUID) -> Invoice:
        invoice = self.db.scalar(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.deleted_at.is_(None))
        )
        if invoice is None:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        return invoice

    def _returned_so_far(self, invoice_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
        """Quantity already returned per product against this invoice — ONE query."""
        rows = self.db.execute(
            select(
                SalesReturnLine.product_id,
                func.coalesce(func.sum(SalesReturnLine.qty), 0),
            )
            .join(SalesReturn, SalesReturn.id == SalesReturnLine.sales_return_id)
            .where(
                SalesReturn.invoice_id == invoice_id,
                SalesReturn.deleted_at.is_(None),
                SalesReturnLine.deleted_at.is_(None),
            )
            .group_by(SalesReturnLine.product_id)
        ).all()
        return {pid: Decimal(qty or 0) for pid, qty in rows}

    @staticmethod
    def returnable_qty(invoiced: Decimal, already_returned: Decimal) -> Decimal:
        """THE definition of what may still come back (R9.6/G7).

        Clamped at zero, for the reason `open_qty` is clamped: a data oddity that made
        returns exceed the invoice must read as "nothing left", not as a negative allowance.
        """
        remaining = Decimal(invoiced) - Decimal(already_returned)
        return remaining if remaining > 0 else Decimal("0")

    def returnable(self, invoice_id: uuid.UUID) -> list[ReturnableLine]:
        """What is still returnable on an invoice, line by line."""
        invoice = self._invoice(invoice_id)
        returned = self._returned_so_far(invoice.id)
        out: list[ReturnableLine] = []
        for line in invoice.lines:
            product = self.db.get(Product, line.product_id)
            already = returned.get(line.product_id, Decimal(0))
            out.append(
                ReturnableLine(
                    product_id=line.product_id,
                    sku_code=product.sku_code if product else None,
                    product_name=product.name if product else None,
                    invoiced_qty=Decimal(line.qty),
                    returned_qty=already,
                    returnable_qty=self.returnable_qty(line.qty, already),
                    unit_price_minor=line.unit_price_minor,
                    tax_rate_bps=line.tax_rate_bps,
                )
            )
        return out

    # --- reads -----------------------------------------------------------

    def _to_detail(self, ret: SalesReturn) -> SalesReturnDetail:
        credit = self.db.scalar(
            select(CreditNote).where(
                CreditNote.sales_return_id == ret.id, CreditNote.deleted_at.is_(None)
            )
        )
        invoice = self.db.get(Invoice, ret.invoice_id)
        lines: list[SalesReturnLineRead] = []
        for line in ret.lines:
            product = self.db.get(Product, line.product_id)
            lines.append(
                SalesReturnLineRead(
                    product_id=line.product_id,
                    sku_code=product.sku_code if product else None,
                    product_name=product.name if product else None,
                    qty=line.qty,
                    unit_price_minor=line.unit_price_minor,
                    line_total_minor=line.line_total_minor,
                    line_no=line.line_no,
                )
            )
        return SalesReturnDetail(
            id=ret.id,
            return_no=ret.return_no,
            customer_id=ret.customer_id,
            invoice_id=ret.invoice_id,
            invoice_no=invoice.invoice_no if invoice else None,
            return_date=ret.return_date,
            reason=ret.reason,
            subtotal_minor=ret.subtotal_minor,
            tax_minor=ret.tax_minor,
            total_minor=ret.total_minor,
            lines=lines,
            credit_note=(
                CreditNoteRead(
                    id=credit.id,
                    credit_note_no=credit.credit_note_no,
                    invoice_id=credit.invoice_id,
                    note_date=credit.note_date,
                    total_minor=credit.total_minor,
                    reason=credit.reason,
                )
                if credit
                else None
            ),
        )

    def get(self, return_id: uuid.UUID) -> SalesReturnDetail:
        ret = self.db.scalar(
            select(SalesReturn).where(
                SalesReturn.id == return_id, SalesReturn.deleted_at.is_(None)
            )
        )
        if ret is None:
            raise NotFoundError(f"Return {return_id} not found")
        return self._to_detail(ret)

    def for_invoice(self, invoice_id: uuid.UUID) -> list[SalesReturnDetail]:
        rows = self.db.scalars(
            select(SalesReturn)
            .where(SalesReturn.invoice_id == invoice_id, SalesReturn.deleted_at.is_(None))
            .order_by(SalesReturn.return_date.desc())
        )
        return [self._to_detail(r) for r in rows]

    def credit_notes(self, customer_id: uuid.UUID) -> list[CreditNoteRead]:
        rows = self.db.scalars(
            select(CreditNote)
            .where(CreditNote.customer_id == customer_id, CreditNote.deleted_at.is_(None))
            .order_by(CreditNote.note_date.desc())
        )
        return [
            CreditNoteRead(
                id=c.id,
                credit_note_no=c.credit_note_no,
                invoice_id=c.invoice_id,
                note_date=c.note_date,
                total_minor=c.total_minor,
                reason=c.reason,
            )
            for c in rows
        ]

    # --- R9.4–R9.7: the return -------------------------------------------

    def create(self, payload, *, actor_id: uuid.UUID | None) -> SalesReturnDetail:
        """Take goods back, put the stock on the shelf, and credit the customer.

        Order of operations matters: validate the whole payload against what is returnable
        BEFORE writing anything, so a return that is partly invalid does not leave half its
        stock posted. `form_action` would roll back anyway, but a service that half-applies
        is a service whose failure mode depends on its caller.
        """
        invoice = self._invoice(payload.invoice_id)
        reason = (payload.reason or "").strip()
        if not reason:
            raise ValidationError(
                "A return needs a reason — stock does not reappear on the shelf by itself"
            )

        allowed = {ln.product_id: ln for ln in self.returnable(invoice.id)}
        invoice_lines = {ln.product_id: ln for ln in invoice.lines}

        planned: list[tuple[InvoiceLine, Decimal]] = []
        for item in payload.lines:
            allowance = allowed.get(item.product_id)
            if allowance is None:
                raise ValidationError(
                    f"Product {item.product_id} is not on invoice {invoice.invoice_no}"
                )
            if Decimal(item.qty) > allowance.returnable_qty:
                product_label = allowance.sku_code or str(item.product_id)
                raise ConflictError(
                    f"Cannot return {qty_text(item.qty)} of {product_label}: "
                    f"{qty_text(allowance.invoiced_qty)} was invoiced, "
                    f"{qty_text(allowance.returned_qty)} already came back, so "
                    f"{qty_text(allowance.returnable_qty)} is returnable"
                )
            planned.append((invoice_lines[item.product_id], Decimal(item.qty)))

        if not planned:
            raise ValidationError("A return needs at least one line")

        warehouse_id = payload.warehouse_id or self._default_warehouse()
        ret = SalesReturn(
            customer_id=invoice.customer_id,
            invoice_id=invoice.id,
            warehouse_id=warehouse_id,
            return_no=allocate_document_number(
                self.db,
                doc_type=DOC_TYPE_RETURN,
                business_unit_id=invoice.business_unit_id,
                on_date=datetime.now(UTC).date(),
            ),
            reason=reason,
            business_unit_id=invoice.business_unit_id,
            created_by=actor_id,
        )

        subtotal = tax_total = grand = 0
        for i, (invoice_line, qty) in enumerate(planned, start=1):
            # Priced as INVOICED, never re-resolved: a credit is for what the customer
            # actually paid.
            line_subtotal = round_minor(qty * Decimal(invoice_line.unit_price_minor))
            line_tax = round_minor(
                Decimal(line_subtotal) * Decimal(invoice_line.tax_rate_bps) / Decimal(10000)
            )
            line_total = line_subtotal + line_tax
            ret.lines.append(
                SalesReturnLine(
                    product_id=invoice_line.product_id,
                    qty=qty,
                    unit_price_minor=invoice_line.unit_price_minor,
                    tax_rate_bps=invoice_line.tax_rate_bps,
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

        ret.subtotal_minor = subtotal
        ret.tax_minor = tax_total
        ret.total_minor = grand
        self.db.add(ret)
        self.db.flush()

        # R9.4 — stock IN, through the only writer (G8).
        from app.modules.pricing.service import PricingService

        pricing = PricingService(self.db)
        for line in ret.lines:
            self.inventory.record_movement(
                product_id=line.product_id,
                warehouse_id=warehouse_id,
                qty_delta=Decimal(line.qty),
                reason="RETURN",
                ref_type="sales_return",
                ref_id=ret.id,
                unit_cost_minor=pricing.latest_purchase_minor(line.product_id),
                actor_id=actor_id,
            )

        # R9.5 — a credit note against the invoice. The invoice itself is untouched.
        credit = CreditNote(
            customer_id=invoice.customer_id,
            invoice_id=invoice.id,
            sales_return_id=ret.id,
            credit_note_no=allocate_document_number(
                self.db,
                doc_type=DOC_TYPE_CREDIT,
                business_unit_id=invoice.business_unit_id,
                on_date=datetime.now(UTC).date(),
            ),
            reason=reason,
            subtotal_minor=subtotal,
            tax_minor=tax_total,
            total_minor=grand,
            business_unit_id=invoice.business_unit_id,
            created_by=actor_id,
        )
        self.db.add(credit)
        self.db.flush()

        # One row for the return; the credit note is part of the same decision, named in the
        # same summary, so this stays one activity row per state change (G5).
        self.activity.log(
            actor_id=actor_id,
            verb="returned",
            entity_type="sales_return",
            entity_id=ret.id,
            summary=(
                f"Return {ret.return_no} against {invoice.invoice_no} — "
                f"{credit.credit_note_no} raised for {grand} minor. {reason}"
            ),
            data={
                "invoice_no": invoice.invoice_no,
                "credit_note_no": credit.credit_note_no,
                "total_minor": grand,
                "lines": len(ret.lines),
            },
        )
        return self._to_detail(ret)

    def _default_warehouse(self) -> uuid.UUID:
        from app.modules.config.models import Warehouse

        warehouse_id = self.db.scalar(
            select(Warehouse.id).where(Warehouse.deleted_at.is_(None)).limit(1)
        )
        if warehouse_id is None:
            raise NotFoundError("No warehouse configured; run the seed first.")
        return warehouse_id
