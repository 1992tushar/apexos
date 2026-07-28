"""Pre-order services: requisition → RFQ → quotation → purchase order.

Split from `service.py` deliberately. `service.py` owns the PO/GRN state machine
(create → confirm → receive → bill) and is the file Part 3's second checkpoint
edits; this file owns everything *in front* of the PO. Neither half needs to be
read to work on the other, which is the whole reason for the seam.

Nothing here re-implements the purchase order (G16). Both conversion paths —
requisition → PO, and quotation → PO after an award — build a
`PurchaseOrderCreate` and hand it to `PurchaseOrderService.create`, so PO
numbering, price snapshotting, tax and totals have exactly one implementation.

Each state change writes exactly one `activity_log` row (G5), and approval
records its actor and reason on the row as well as in the log (R4.2) so the
screen can show who signed off without replaying the log.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.activity.service import ActivityService
from app.modules.config.service import allocate_document_number
from app.modules.identity.models import User
from app.modules.procurement.models import (
    PurchaseOrder,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    Rfq,
    RfqLine,
    RfqSupplier,
    SupplierQuotation,
    SupplierQuotationLine,
)
from app.modules.procurement.repository import PreorderRepository
from app.modules.procurement.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderLineCreate,
    QuotationCreate,
    QuotationHistoryRow,
    QuotationLineRead,
    QuotationRead,
    QuoteComparison,
    QuoteComparisonColumn,
    QuoteComparisonLine,
    RequisitionCreate,
    RequisitionDetail,
    RequisitionLineRead,
    RequisitionListRow,
    RfqCreate,
    RfqDetail,
    RfqListRow,
    RfqSupplierRead,
)
from app.modules.procurement.service import (
    PurchaseOrderService,
    _round_minor,
    default_business_unit,
    tax_bps_for,
)
from app.modules.suppliers.service import ProductSupplierService
from app.modules.suppliers.vendor import VendorIntelService

# The requisition lifecycle. One definition — the filter dropdown on /requisitions
# and the transitions below read the same tuple, so a new state cannot be
# selectable without being reachable.
REQUISITION_STATUSES: tuple[tuple[str, str], ...] = (
    ("requested", "Awaiting approval"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("converted", "Converted"),
)
RFQ_STATUSES: tuple[tuple[str, str], ...] = (
    ("issued", "Issued"),
    ("awarded", "Awarded"),
    ("closed", "Closed"),
)


class RequisitionService:
    """"We need this" → approved → a PO or an RFQ (R4.1)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PreorderRepository(db)
        self.activity = ActivityService(db)

    # -- reads -----------------------------------------------------------
    def to_read_many(self, rows) -> list[RequisitionListRow]:
        """Project a page of `PurchaseRequisition` rows for the list (R2.2).

        The whole page at once: one query for the line aggregates and one for the
        outcome numbers, rather than two per row.
        """
        ids = [r.id for r in rows]
        aggregates = self.repo.requisition_line_aggregates(ids)
        outcomes = self.repo.requisition_outcomes(ids)
        out: list[RequisitionListRow] = []
        for r in rows:
            count, qty = aggregates.get(r.id, (0, Decimal("0")))
            out.append(
                RequisitionListRow(
                    id=r.id,
                    requisition_no=r.requisition_no,
                    status=r.status,
                    needed_by=r.needed_by,
                    created_at=r.created_at,
                    line_count=count,
                    qty_total=qty,
                    outcome=outcomes.get(r.id),
                )
            )
        return out

    def _require(self, requisition_id: uuid.UUID) -> PurchaseRequisition:
        req = self.repo.get_requisition(requisition_id)
        if req is None:
            raise NotFoundError(f"Requisition {requisition_id} not found")
        return req

    def _line_reads(self, lines) -> list[RequisitionLineRead]:
        products = self.repo.products_by_id([ln.product_id for ln in lines])
        return [
            RequisitionLineRead(
                id=ln.id,
                product_id=ln.product_id,
                product_name=getattr(products.get(ln.product_id), "name", None),
                sku_code=getattr(products.get(ln.product_id), "sku_code", None),
                qty=ln.qty,
                line_no=ln.line_no,
            )
            for ln in lines
        ]

    def _to_detail(self, req: PurchaseRequisition) -> RequisitionDetail:
        approver = (
            self.db.scalar(select(User.full_name).where(User.id == req.approved_by))
            if req.approved_by
            else None
        )
        po_no = (
            self.db.scalar(
                select(PurchaseOrder.po_no).where(PurchaseOrder.id == req.purchase_order_id)
            )
            if req.purchase_order_id
            else None
        )
        rfq_no = (
            self.db.scalar(select(Rfq.rfq_no).where(Rfq.id == req.rfq_id))
            if req.rfq_id
            else None
        )
        return RequisitionDetail(
            id=req.id,
            requisition_no=req.requisition_no,
            status=req.status,
            needed_by=req.needed_by,
            note=req.note,
            business_unit_id=req.business_unit_id,
            approved_by_name=approver,
            approved_at=req.approved_at,
            approval_reason=req.approval_reason,
            purchase_order_id=req.purchase_order_id,
            po_no=po_no,
            rfq_id=req.rfq_id,
            rfq_no=rfq_no,
            lines=self._line_reads(req.lines),
        )

    def get(self, requisition_id: uuid.UUID) -> RequisitionDetail:
        return self._to_detail(self._require(requisition_id))

    # -- request ---------------------------------------------------------
    def create(
        self, payload: RequisitionCreate, *, actor_id: uuid.UUID | None
    ) -> RequisitionDetail:
        bu = payload.business_unit_id or default_business_unit(self.db)
        req = PurchaseRequisition(
            requisition_no=allocate_document_number(
                self.db, doc_type="REQ", business_unit_id=bu,
                on_date=datetime.now(UTC).date(),
            ),
            status="requested",
            needed_by=payload.needed_by,
            note=payload.note,
            business_unit_id=bu,
            created_by=actor_id,
        )
        for i, line in enumerate(payload.lines, start=1):
            product = self.repo.require_product(line.product_id)
            req.lines.append(
                PurchaseRequisitionLine(
                    product_id=product.id, qty=line.qty, line_no=i, created_by=actor_id
                )
            )
        self.db.add(req)
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="requested",
            entity_type="purchase_requisition",
            entity_id=req.id,
            summary=f"Requisition {req.requisition_no} raised ({len(req.lines)} lines)",
            data={"lines": len(req.lines)},
        )
        return self._to_detail(req)

    # -- approve / reject -------------------------------------------------
    def _decide(
        self,
        requisition_id: uuid.UUID,
        *,
        status: str,
        verb: str,
        reason: str,
        actor_id: uuid.UUID | None,
    ) -> RequisitionDetail:
        req = self._require(requisition_id)
        if req.status != "requested":
            raise ConflictError(
                f"Requisition {req.requisition_no} is already {req.status} — "
                "only a requisition awaiting approval can be decided"
            )
        if not reason.strip():
            raise ValidationError("A reason is required — approvals are on the record (R4.2)")
        req.status = status
        req.approved_by = actor_id
        req.approved_at = datetime.now(UTC)
        req.approval_reason = reason.strip()
        req.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb=verb,
            entity_type="purchase_requisition",
            entity_id=req.id,
            summary=f"Requisition {req.requisition_no} {verb}: {req.approval_reason}",
            data={"reason": req.approval_reason},
        )
        return self._to_detail(req)

    def approve(
        self, requisition_id: uuid.UUID, *, reason: str, actor_id: uuid.UUID | None
    ) -> RequisitionDetail:
        return self._decide(
            requisition_id, status="approved", verb="approved", reason=reason, actor_id=actor_id
        )

    def reject(
        self, requisition_id: uuid.UUID, *, reason: str, actor_id: uuid.UUID | None
    ) -> RequisitionDetail:
        return self._decide(
            requisition_id, status="rejected", verb="rejected", reason=reason, actor_id=actor_id
        )

    # -- convert ----------------------------------------------------------
    def _require_approved(self, requisition_id: uuid.UUID) -> PurchaseRequisition:
        req = self._require(requisition_id)
        if req.status == "converted":
            raise ConflictError(
                f"Requisition {req.requisition_no} has already been converted"
            )
        if req.status != "approved":
            raise ConflictError(
                f"Cannot convert requisition {req.requisition_no} in status "
                f"'{req.status}' — approve it first"
            )
        return req

    def convert_to_po(
        self, requisition_id: uuid.UUID, *, supplier_id: uuid.UUID, actor_id: uuid.UUID | None
    ) -> PurchaseOrderDetail:
        """Straight to a PO, for when the price is already known (R4.1).

        Line prices are left to `PurchaseOrderService.create`, which resolves the
        supplier-specific purchase price — the requisition never carried a price.
        """
        req = self._require_approved(requisition_id)
        po = PurchaseOrderService(self.db).create(
            PurchaseOrderCreate(
                supplier_id=supplier_id,
                business_unit_id=req.business_unit_id,
                lines=[
                    PurchaseOrderLineCreate(product_id=ln.product_id, qty=ln.qty)
                    for ln in req.lines
                ],
            ),
            actor_id=actor_id,
        )
        req.status = "converted"
        req.purchase_order_id = po.id
        req.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="converted",
            entity_type="purchase_requisition",
            entity_id=req.id,
            summary=f"Requisition {req.requisition_no} converted to purchase order {po.po_no}",
            data={"purchase_order": po.po_no, "supplier": po.supplier_name},
        )
        return po

    def convert_to_rfq(
        self,
        requisition_id: uuid.UUID,
        *,
        supplier_ids: list[uuid.UUID],
        due_date=None,
        actor_id: uuid.UUID | None,
    ) -> RfqDetail:
        """Ask the market instead — the same lines, issued to several suppliers."""
        req = self._require_approved(requisition_id)
        rfq = RfqService(self.db).issue(
            RfqCreate(
                supplier_ids=supplier_ids,
                business_unit_id=req.business_unit_id,
                due_date=due_date,
                note=f"From requisition {req.requisition_no}",
                lines=[{"product_id": ln.product_id, "qty": ln.qty} for ln in req.lines],
            ),
            requisition_id=req.id,
            actor_id=actor_id,
        )
        req.status = "converted"
        req.rfq_id = rfq.id
        req.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="converted",
            entity_type="purchase_requisition",
            entity_id=req.id,
            summary=f"Requisition {req.requisition_no} converted to RFQ {rfq.rfq_no}",
            data={"rfq": rfq.rfq_no, "suppliers": len(rfq.suppliers)},
        )
        return rfq


class RfqService:
    """Issue an RFQ, capture what came back, compare it, award one (R4.3–R4.6)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PreorderRepository(db)
        self.activity = ActivityService(db)

    # -- reads -----------------------------------------------------------
    def to_read_many(self, rows) -> list[RfqListRow]:
        ids = [r.id for r in rows]
        lines = self.repo.rfq_line_counts(ids)
        suppliers = self.repo.rfq_supplier_counts(ids)
        quotes = self.repo.rfq_quote_counts(ids)
        return [
            RfqListRow(
                id=r.id,
                rfq_no=r.rfq_no,
                status=r.status,
                due_date=r.due_date,
                created_at=r.created_at,
                supplier_count=suppliers.get(r.id, 0),
                quote_count=quotes.get(r.id, 0),
                line_count=lines.get(r.id, 0),
            )
            for r in rows
        ]

    def _require(self, rfq_id: uuid.UUID) -> Rfq:
        rfq = self.repo.get_rfq(rfq_id)
        if rfq is None:
            raise NotFoundError(f"RFQ {rfq_id} not found")
        return rfq

    def _quotation_read(
        self, quote: SupplierQuotation, *, supplier_names: dict[uuid.UUID, str], products
    ) -> QuotationRead:
        po_no = (
            self.db.scalar(
                select(PurchaseOrder.po_no).where(PurchaseOrder.id == quote.purchase_order_id)
            )
            if quote.purchase_order_id
            else None
        )
        return QuotationRead(
            id=quote.id,
            quotation_no=quote.quotation_no,
            rfq_id=quote.rfq_id,
            supplier_id=quote.supplier_id,
            supplier_name=supplier_names.get(quote.supplier_id),
            status=quote.status,
            quoted_on=quote.quoted_on,
            valid_until=quote.valid_until,
            lead_time_days=quote.lead_time_days,
            note=quote.note,
            subtotal_minor=quote.subtotal_minor,
            tax_minor=quote.tax_minor,
            total_minor=quote.total_minor,
            purchase_order_id=quote.purchase_order_id,
            po_no=po_no,
            lines=[
                QuotationLineRead(
                    id=ln.id,
                    product_id=ln.product_id,
                    product_name=getattr(products.get(ln.product_id), "name", None),
                    sku_code=getattr(products.get(ln.product_id), "sku_code", None),
                    qty=ln.qty,
                    unit_price_minor=ln.unit_price_minor,
                    moq=ln.moq,
                    tax_rate_bps=ln.tax_rate_bps,
                    line_subtotal_minor=ln.line_subtotal_minor,
                    line_tax_minor=ln.line_tax_minor,
                    line_total_minor=ln.line_total_minor,
                )
                for ln in ln_sorted(quote.lines)
            ],
        )

    def comparison(self, rfq_id: uuid.UUID) -> QuoteComparison:
        """The side-by-side (R4.5). A pure read — writes nothing (G15).

        `is_cheapest` per cell and `is_cheapest_total` / `is_fastest` per column are
        computed here rather than in the template, so the screen and any test agree
        on what "best" means. Ties mark every tied column, because silently picking
        one would be a recommendation the data does not support.
        """
        rfq = self._require(rfq_id)
        return self._comparison(rfq)

    def _comparison(self, rfq: Rfq) -> QuoteComparison:
        quotes = self.repo.quotations_for(rfq.id)
        supplier_names = self.repo.supplier_names(
            [q.supplier_id for q in quotes] + [s.supplier_id for s in rfq.suppliers]
        )
        products = self.repo.products_by_id([ln.product_id for ln in rfq.lines])

        # R5.2/R5.5: the measured vendor score and the standing MOQ join the grid.
        # Both are read from the services that own them (G16) — this method computes
        # neither. `score` is already rendered and may read "unknown" (R5.11);
        # `score_explained` carries the arithmetic the screen has to show (G11).
        intel = VendorIntelService(self.db)
        mapping = ProductSupplierService(self.db)

        columns: list[QuoteComparisonColumn] = []
        for quote in quotes:
            cells = {
                ln.product_id: QuoteComparisonLine(
                    product_id=ln.product_id,
                    unit_price_minor=ln.unit_price_minor,
                    moq=ln.moq,
                    agreed_moq=mapping.moq(ln.product_id, quote.supplier_id),
                )
                for ln in quote.lines
            }
            score = intel.score(quote.supplier_id)
            columns.append(
                QuoteComparisonColumn(
                    quotation_id=quote.id,
                    quotation_no=quote.quotation_no,
                    supplier_id=quote.supplier_id,
                    supplier_name=supplier_names.get(quote.supplier_id),
                    status=quote.status,
                    lead_time_days=quote.lead_time_days,
                    total_minor=quote.total_minor,
                    score=score.display,
                    score_explained=score,
                    cells=cells,
                )
            )

        # Mark the best cell per product, and the best column overall.
        for line in rfq.lines:
            prices = [
                col.cells[line.product_id].unit_price_minor
                for col in columns
                if line.product_id in col.cells
                and col.cells[line.product_id].unit_price_minor is not None
            ]
            if not prices:
                continue
            best = min(prices)
            for col in columns:
                cell = col.cells.get(line.product_id)
                if cell is not None and cell.unit_price_minor == best:
                    cell.is_cheapest = True
        if columns:
            cheapest_total = min(c.total_minor for c in columns)
            for col in columns:
                col.is_cheapest_total = col.total_minor == cheapest_total
            leads = [c.lead_time_days for c in columns if c.lead_time_days is not None]
            if leads:
                fastest = min(leads)
                for col in columns:
                    col.is_fastest = col.lead_time_days == fastest

        quoted = {q.supplier_id for q in quotes}
        silent = [
            supplier_names.get(s.supplier_id) or str(s.supplier_id)
            for s in rfq.suppliers
            if s.supplier_id not in quoted
        ]
        return QuoteComparison(
            rfq_id=rfq.id,
            rfq_no=rfq.rfq_no,
            lines=self._rfq_line_reads(rfq.lines, products),
            columns=columns,
            invited_not_quoted=sorted(silent),
        )

    @staticmethod
    def _rfq_line_reads(lines, products) -> list[RequisitionLineRead]:
        return [
            RequisitionLineRead(
                id=ln.id,
                product_id=ln.product_id,
                product_name=getattr(products.get(ln.product_id), "name", None),
                sku_code=getattr(products.get(ln.product_id), "sku_code", None),
                qty=ln.qty,
                line_no=ln.line_no,
            )
            for ln in lines
        ]

    def _to_detail(self, rfq: Rfq) -> RfqDetail:
        quotes = self.repo.quotations_for(rfq.id)
        supplier_names = self.repo.supplier_names(
            [q.supplier_id for q in quotes] + [s.supplier_id for s in rfq.suppliers]
        )
        products = self.repo.products_by_id(
            [ln.product_id for ln in rfq.lines]
            + [ln.product_id for q in quotes for ln in q.lines]
        )
        requisition_no = self.db.scalar(
            select(PurchaseRequisition.requisition_no).where(
                PurchaseRequisition.id == rfq.purchase_requisition_id
            )
        ) if rfq.purchase_requisition_id else None
        return RfqDetail(
            id=rfq.id,
            rfq_no=rfq.rfq_no,
            status=rfq.status,
            issued_at=rfq.issued_at,
            due_date=rfq.due_date,
            note=rfq.note,
            business_unit_id=rfq.business_unit_id,
            purchase_requisition_id=rfq.purchase_requisition_id,
            requisition_no=requisition_no,
            awarded_quotation_id=rfq.awarded_quotation_id,
            lines=self._rfq_line_reads(rfq.lines, products),
            suppliers=[
                RfqSupplierRead(
                    supplier_id=s.supplier_id,
                    supplier_name=supplier_names.get(s.supplier_id),
                    status=s.status,
                )
                for s in rfq.suppliers
            ],
            quotations=[
                self._quotation_read(q, supplier_names=supplier_names, products=products)
                for q in quotes
            ],
            comparison=self._comparison(rfq),
        )

    def get(self, rfq_id: uuid.UUID) -> RfqDetail:
        return self._to_detail(self._require(rfq_id))

    # -- issue ------------------------------------------------------------
    def issue(
        self,
        payload: RfqCreate,
        *,
        requisition_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None,
    ) -> RfqDetail:
        bu = payload.business_unit_id or default_business_unit(self.db)
        rfq = Rfq(
            rfq_no=allocate_document_number(
                self.db, doc_type="RFQ", business_unit_id=bu, on_date=datetime.now(UTC).date()
            ),
            status="issued",
            issued_at=datetime.now(UTC),
            due_date=payload.due_date,
            note=payload.note,
            purchase_requisition_id=requisition_id,
            business_unit_id=bu,
            created_by=actor_id,
        )
        for i, line in enumerate(payload.lines, start=1):
            product = self.repo.require_product(line.product_id)
            rfq.lines.append(
                RfqLine(product_id=product.id, qty=line.qty, line_no=i, created_by=actor_id)
            )
        seen: set[uuid.UUID] = set()
        for supplier_id in payload.supplier_ids:
            if supplier_id in seen:
                continue  # the same supplier asked twice is one invitation
            seen.add(supplier_id)
            supplier = self.repo.require_supplier(supplier_id)
            rfq.suppliers.append(
                RfqSupplier(supplier_id=supplier.id, status="invited", created_by=actor_id)
            )
        self.db.add(rfq)
        self.db.flush()

        self.activity.log(
            actor_id=actor_id,
            verb="issued",
            entity_type="rfq",
            entity_id=rfq.id,
            summary=(
                f"RFQ {rfq.rfq_no} issued to {len(rfq.suppliers)} suppliers "
                f"({len(rfq.lines)} lines)"
            ),
            data={"suppliers": len(rfq.suppliers), "lines": len(rfq.lines)},
        )
        return self._to_detail(rfq)

    # -- capture a quotation ---------------------------------------------
    def capture_quote(
        self, rfq_id: uuid.UUID, payload: QuotationCreate, *, actor_id: uuid.UUID | None
    ) -> QuotationRead:
        """Record what one supplier came back with (R4.4).

        A supplier who was not invited but answered anyway is accepted and added to
        the invitation list — refusing the data would lose a real quote. Quantities
        default to the RFQ line's, so the comparison is like-for-like.
        """
        rfq = self._require(rfq_id)
        if rfq.status != "issued":
            raise ConflictError(
                f"RFQ {rfq.rfq_no} is {rfq.status} — quotes can only be captured while it is issued"
            )
        supplier = self.repo.require_supplier(payload.supplier_id)
        if self.repo.quotation_for_supplier(rfq.id, supplier.id) is not None:
            raise ConflictError(
                f"{supplier.name} has already quoted on {rfq.rfq_no}. "
                "A revised price is a new RFQ, not an edit (D3)."
            )

        rfq_qty = {ln.product_id: ln.qty for ln in rfq.lines}
        quote = SupplierQuotation(
            quotation_no=allocate_document_number(
                self.db, doc_type="SQ", business_unit_id=rfq.business_unit_id,
                on_date=datetime.now(UTC).date(),
            ),
            rfq_id=rfq.id,
            supplier_id=supplier.id,
            status="received",
            quoted_on=payload.quoted_on or datetime.now(UTC).date(),
            valid_until=payload.valid_until,
            lead_time_days=payload.lead_time_days,
            note=payload.note,
            business_unit_id=rfq.business_unit_id,
            created_by=actor_id,
        )
        subtotal = tax_total = grand = 0
        for i, line in enumerate(payload.lines, start=1):
            product = self.repo.require_product(line.product_id)
            if line.product_id not in rfq_qty:
                raise ValidationError(f"{product.sku_code} is not on RFQ {rfq.rfq_no}")
            qty = line.qty if line.qty is not None else rfq_qty[line.product_id]
            if qty <= 0:
                raise ValidationError(f"Quoted quantity for {product.sku_code} must be positive")
            rate_bps = tax_bps_for(self.db, product)
            line_subtotal = _round_minor(qty * Decimal(line.unit_price_minor))
            line_tax = _round_minor(Decimal(line_subtotal) * Decimal(rate_bps) / Decimal(10000))
            quote.lines.append(
                SupplierQuotationLine(
                    product_id=product.id,
                    qty=qty,
                    unit_price_minor=line.unit_price_minor,
                    moq=line.moq,
                    tax_rate_bps=rate_bps,
                    line_subtotal_minor=line_subtotal,
                    line_tax_minor=line_tax,
                    line_total_minor=line_subtotal + line_tax,
                    line_no=i,
                    created_by=actor_id,
                )
            )
            subtotal += line_subtotal
            tax_total += line_tax
            grand += line_subtotal + line_tax
        quote.subtotal_minor = subtotal
        quote.tax_minor = tax_total
        quote.total_minor = grand
        self.db.add(quote)

        invitation = self.repo.invitation(rfq.id, supplier.id)
        if invitation is None:
            self.db.add(
                RfqSupplier(
                    rfq_id=rfq.id, supplier_id=supplier.id, status="quoted", created_by=actor_id
                )
            )
        else:
            invitation.status = "quoted"
            invitation.updated_by = actor_id
        self.db.flush()

        lead = "unknown" if payload.lead_time_days is None else str(payload.lead_time_days)
        self.activity.log(
            actor_id=actor_id,
            verb="quoted",
            entity_type="rfq",
            entity_id=rfq.id,
            summary=(
                f"{supplier.name} quoted {quote.quotation_no} on {rfq.rfq_no} "
                f"({grand} minor, {lead} day lead time)"
            ),
            data={
                "quotation_no": quote.quotation_no,
                "supplier": supplier.name,
                "total_minor": grand,
                "lead_time_days": payload.lead_time_days,
            },
        )
        products = self.repo.products_by_id([ln.product_id for ln in quote.lines])
        return self._quotation_read(
            quote, supplier_names={supplier.id: supplier.name}, products=products
        )

    # -- award ------------------------------------------------------------
    def award(
        self, rfq_id: uuid.UUID, quotation_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> PurchaseOrderDetail:
        """Pick a quotation and turn it into a PO at the quoted prices (R4.16).

        The losing quotations are left exactly as received. Marking them "rejected"
        would be a state change per supplier with no decision behind it, and the
        award is already recorded on the RFQ — `awarded_quotation_id` says which one
        won without rewriting the others.
        """
        rfq = self._require(rfq_id)
        if rfq.status != "issued":
            raise ConflictError(f"RFQ {rfq.rfq_no} is already {rfq.status}")
        quote = self.repo.get_quotation(quotation_id)
        if quote is None or quote.rfq_id != rfq.id:
            raise NotFoundError(f"Quotation {quotation_id} is not on RFQ {rfq.rfq_no}")
        if not quote.lines:
            raise ValidationError(f"Quotation {quote.quotation_no} has no priced lines")

        po = PurchaseOrderService(self.db).create(
            PurchaseOrderCreate(
                supplier_id=quote.supplier_id,
                business_unit_id=rfq.business_unit_id,
                lines=[
                    PurchaseOrderLineCreate(
                        product_id=ln.product_id,
                        qty=ln.qty,
                        unit_price_minor=ln.unit_price_minor,
                    )
                    for ln in quote.lines
                ],
            ),
            actor_id=actor_id,
        )
        quote.status = "awarded"
        quote.purchase_order_id = po.id
        quote.updated_by = actor_id
        rfq.status = "awarded"
        rfq.awarded_quotation_id = quote.id
        rfq.updated_by = actor_id
        self.db.flush()

        supplier_name = self.repo.supplier_names([quote.supplier_id]).get(quote.supplier_id)
        self.activity.log(
            actor_id=actor_id,
            verb="awarded",
            entity_type="rfq",
            entity_id=rfq.id,
            summary=(
                f"RFQ {rfq.rfq_no} awarded to {supplier_name} "
                f"({quote.quotation_no}) → purchase order {po.po_no}"
            ),
            data={
                "quotation_no": quote.quotation_no,
                "supplier": supplier_name,
                "purchase_order": po.po_no,
                "total_minor": quote.total_minor,
            },
        )
        return po

    # -- quotation history (R4.6) -----------------------------------------
    def quotation_history(
        self, product_id: uuid.UUID, *, supplier_id: uuid.UUID | None = None, limit: int = 50
    ) -> list[QuotationHistoryRow]:
        """Every price this product has been quoted, newest first. A pure read."""
        rows = self.repo.quotation_history_rows(
            product_id, supplier_id=supplier_id, limit=limit
        )
        return [
            QuotationHistoryRow(
                quotation_id=r[0],
                quotation_no=r[1],
                rfq_no=r[2],
                supplier_id=r[3],
                supplier_name=r[4],
                quoted_on=r[5],
                unit_price_minor=r[6],
                moq=r[7],
                lead_time_days=r[8],
                status=r[9],
            )
            for r in rows
        ]


def ln_sorted(lines):
    """Lines in `line_no` order — a freshly built quote has not been reloaded."""
    return sorted(lines, key=lambda ln: ln.line_no)
