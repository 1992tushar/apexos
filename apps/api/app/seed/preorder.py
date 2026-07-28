"""Part 3's seed section: the pre-order flow (R4.15) and its C2 revision story.

This is the worked example of the section-per-module shape. A new part writes its
own `app/seed/<domain>.py` with the same signature and adds one call to `run()`,
rather than appending another hundred lines to `run()` itself.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.modules.pricing.models import PurchasePrice
from app.modules.procurement.models import PurchaseRequisition
from app.modules.procurement.preorder import RequisitionService, RfqService
from app.modules.procurement.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptLineInput,
    PurchaseOrderRevise,
    PurchaseOrderReviseLine,
    QuotationCreate,
    QuotationLineInput,
    RequisitionCreate,
    RequisitionLineCreate,
)
from app.modules.procurement.service import GoodsReceiptService, PurchaseOrderService
from app.modules.products.models import Product
from app.seed.helpers import SeedContext


def seed_preorder(ctx: SeedContext) -> dict | None:
    """Three requisitions, an RFQ with two quotes, a partial receipt and a revision.

    Returns the summary dict `run()` puts under `"preorder"`, or None when the
    section is skipped because requisitions already exist (idempotence).
    """
    db = ctx.db
    actor_id = ctx.actor_id
    suppliers = ctx.suppliers
    paperwings = suppliers["SUPP-0001"]

    preorder_result = None
    if (db.scalar(select(func.count()).select_from(PurchaseRequisition)) or 0) == 0:
        requisitions = RequisitionService(db)
        rfqs = RfqService(db)
        gb1 = db.scalar(select(Product).where(Product.sku_code == "APX-GB-001"))
        tis3 = db.scalar(select(Product).where(Product.sku_code == "AUR-TIS-003"))
        today = datetime.now(UTC).date()

        # 1. Awaiting approval — the one the founder lands on with a decision to make.
        pending_req = requisitions.create(
            RequisitionCreate(
                needed_by=today + timedelta(days=21),
                note="Warehouse running low ahead of the festive season",
                lines=[
                    RequisitionLineCreate(product_id=gb1.id, qty=Decimal("400")),
                    RequisitionLineCreate(product_id=tis3.id, qty=Decimal("120")),
                ],
            ),
            actor_id=actor_id,
        )

        # 2. Approved and converted straight to a PO — price already settled.
        direct_req = requisitions.create(
            RequisitionCreate(
                needed_by=today + timedelta(days=10),
                note="Repeat buy, price already agreed with PaperWings",
                lines=[RequisitionLineCreate(product_id=tis3.id, qty=Decimal("60"))],
            ),
            actor_id=actor_id,
        )
        requisitions.approve(
            direct_req.id,
            reason="Within the monthly consumables budget",
            actor_id=actor_id,
        )
        req_po = requisitions.convert_to_po(
            direct_req.id, supplier_id=paperwings.id, actor_id=actor_id
        )

        # 3. Approved, out as an RFQ, two quotes in — the comparison screen's data.
        #    Deliberately not symmetric: the cheaper unit price comes with the
        #    slower lead time and a higher MOQ, so the screen has a real trade-off
        #    to show rather than one obviously-best column.
        quote_req = requisitions.create(
            RequisitionCreate(
                needed_by=today + timedelta(days=45),
                note="New line — no agreed price yet, ask the market",
                lines=[RequisitionLineCreate(product_id=gb1.id, qty=Decimal("1000"))],
            ),
            actor_id=actor_id,
        )
        requisitions.approve(
            quote_req.id, reason="Volume justifies going out to quote", actor_id=actor_id
        )
        second_supplier = suppliers["SUPP-0002"]
        rfq = requisitions.convert_to_rfq(
            quote_req.id,
            supplier_ids=[paperwings.id, second_supplier.id],
            due_date=today + timedelta(days=14),
            actor_id=actor_id,
        )
        gb_buy = db.scalar(
            select(PurchasePrice.price_minor).where(
                PurchasePrice.product_id == gb1.id, PurchasePrice.supplier_id.is_(None)
            )
        ) or 10000
        rfqs.capture_quote(
            rfq.id,
            QuotationCreate(
                supplier_id=paperwings.id,
                lead_time_days=7,
                valid_until=today + timedelta(days=30),
                note="Ex-works Pune, pallet quantities",
                lines=[
                    QuotationLineInput(
                        product_id=gb1.id,
                        unit_price_minor=int(gb_buy * 1.02) or gb_buy,
                        moq=Decimal("500"),
                    )
                ],
            ),
            actor_id=actor_id,
        )
        rfqs.capture_quote(
            rfq.id,
            QuotationCreate(
                supplier_id=second_supplier.id,
                lead_time_days=18,
                valid_until=today + timedelta(days=45),
                note="Cheaper per unit but a longer lead time and a bigger minimum",
                lines=[
                    QuotationLineInput(
                        product_id=gb1.id,
                        unit_price_minor=int(gb_buy * 0.94) or gb_buy,
                        moq=Decimal("1000"),
                    )
                ],
            ),
            actor_id=actor_id,
        )
        preorder_result = {
            "awaiting_approval": pending_req.requisition_no,
            "converted_to_po": f"{direct_req.requisition_no} → {req_po.po_no}",
            "rfq": rfq.rfq_no,
            "quotes": len(rfqs.get(rfq.id).quotations),
        }

        # --- Part 3 C2: a partial receipt with a live back order, then a
        #     revision (R4.15). The requisition's PO is the subject, so the
        #     screen tells one story end to end: requested → approved → ordered
        #     → part-delivered → renegotiated.
        #
        #     60 ordered, 40 arrived (back order 20), then the supplier admits
        #     they can only ship 50 in total, so version 2 cuts the order to 50
        #     and the back order becomes 10. Version 1 stays readable at 60, and
        #     the receipt stays stamped against version 1 — which is the whole
        #     point of R4.10.
        po_service = PurchaseOrderService(db)
        grn_service = GoodsReceiptService(db)
        po_service.confirm(req_po.id, actor_id=actor_id)
        grn_service.receive(
            req_po.id,
            GoodsReceiptCreate(
                lines=[GoodsReceiptLineInput(product_id=tis3.id, qty=Decimal("40"))],
                against_revision_no=1,
            ),
            actor_id=actor_id,
        )
        revised_po = po_service.revise(
            req_po.id,
            PurchaseOrderRevise(
                reason="PaperWings can only supply 50 of the 60 ordered this month",
                lines=[PurchaseOrderReviseLine(product_id=tis3.id, qty=Decimal("50"))],
            ),
            actor_id=actor_id,
        )
        preorder_result["revised_po"] = (
            f"{revised_po.po_no} v{revised_po.revision_no}, "
            f"back order {revised_po.open_qty_total}"
        )

    return preorder_result
