"""Pre-order pages: requisitions and RFQs (R4.1–R4.6, R4.13).

Both lists are the shared machinery — one `ListSpec` each in
`app.modules.procurement.listing` drives the query, the table, the filters and
the CSV export, so this module holds no query and no table markup. The forms are
bulk-entry grids with a `<datalist>` product picker (R4.12): type part of a SKU
or name and pick, no dropdown scrolling.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ValidationError
from app.core.security import Actor
from app.modules.activity.service import ActivityService
from app.modules.procurement.listing import REQUISITION_LIST, RFQ_LIST
from app.modules.procurement.preorder import RequisitionService, RfqService
from app.modules.procurement.schemas import (
    QuotationCreate,
    QuotationLineInput,
    RequisitionCreate,
    RequisitionLineCreate,
    RfqCreate,
    RfqLineCreate,
)
from app.modules.products.models import Product
from app.modules.products.service import ProductService
from app.modules.suppliers.service import SupplierService
from app.web.core import form_action, render
from app.web.listing import csv_response_from_request, view_from_request, wants_csv
from app.web.security import require_web_permission

router = APIRouter()

# How many blank line rows a bulk-entry form offers.
_BULK_ROWS = 6


def _pickers(db: Session) -> dict:
    """The product and supplier options every pre-order form needs."""
    products, _ = ProductService(db).list(search=None, category_id=None, page=1, page_size=300)
    suppliers, _ = SupplierService(db).list(search=None, page=1, page_size=200)
    return {"products": products, "suppliers": suppliers, "rows": range(_BULK_ROWS)}


def _lines(
    db: Session, product_code: list[str], qty: list[str]
) -> list[tuple[uuid.UUID, Decimal]]:
    """Read a bulk-entry grid, skipping the blank rows the founder left alone.

    The picker is a `<datalist>`, so what arrives is the SKU the founder typed —
    resolved here in one query. An unknown SKU is named back to them rather than
    silently dropped, which is the failure mode a free-text picker must not have.
    """
    wanted = [
        (code.strip(), q.strip())
        for code, q in zip(product_code, qty, strict=False)
        if code.strip() and q.strip()
    ]
    if not wanted:
        return []
    found = {
        p.sku_code: p.id
        for p in db.scalars(
            select(Product).where(
                Product.sku_code.in_({c for c, _ in wanted}), Product.deleted_at.is_(None)
            )
        )
    }
    unknown = sorted({c for c, _ in wanted if c not in found})
    if unknown:
        raise ValidationError(f"No product with SKU {', '.join(unknown)}")
    return [(found[code], Decimal(q)) for code, q in wanted]


# --- requisitions ------------------------------------------------------------


@router.get("/requisitions")
def list_requisitions(request: Request, db: Session = Depends(get_db)):
    project = RequisitionService(db).to_read_many
    if wants_csv(request):
        return csv_response_from_request(request, db, REQUISITION_LIST, project=project)
    return render(
        request,
        "requisitions/list.html",
        view=view_from_request(request, db, REQUISITION_LIST, project=project),
        **_pickers(db),
    )


@router.post("/requisitions")
def create_requisition(
    request: Request,
    needed_by: str = Form(""),
    note: str = Form(""),
    product_code: list[str] = Form([]),
    qty: list[str] = Form([]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_requisition.create")),
):
    def work():
        payload = RequisitionCreate(
            needed_by=date.fromisoformat(needed_by) if needed_by else None,
            note=note or None,
            lines=[
                RequisitionLineCreate(product_id=pid, qty=q)
                for pid, q in _lines(db, product_code, qty)
            ],
        )
        return RequisitionService(db).create(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/requisitions",
        success=lambda req: (f"/requisitions/{req.id}", f"Requisition {req.requisition_no} raised"),
        err="Could not raise the requisition",
    )


@router.get("/requisitions/{requisition_id}")
def requisition_detail(
    request: Request, requisition_id: uuid.UUID, db: Session = Depends(get_db)
):
    # A missing requisition raises NotFoundError → the web handler renders error.html.
    req = RequisitionService(db).get(requisition_id)
    return render(
        request,
        "requisitions/detail.html",
        req=req,
        suppliers=SupplierService(db).list(search=None, page=1, page_size=200)[0],
        history=ActivityService(db).history("purchase_requisition", requisition_id),
    )


@router.post("/requisitions/{requisition_id}/approve")
def approve_requisition(
    request: Request,
    requisition_id: uuid.UUID,
    reason: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_requisition.approve")),
):
    return form_action(
        db,
        lambda: RequisitionService(db).approve(
            requisition_id, reason=reason, actor_id=actor.id
        ),
        back=f"/requisitions/{requisition_id}",
        success=(f"/requisitions/{requisition_id}", "Requisition approved"),
        err="Could not approve the requisition",
    )


@router.post("/requisitions/{requisition_id}/reject")
def reject_requisition(
    request: Request,
    requisition_id: uuid.UUID,
    reason: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_requisition.approve")),
):
    return form_action(
        db,
        lambda: RequisitionService(db).reject(
            requisition_id, reason=reason, actor_id=actor.id
        ),
        back=f"/requisitions/{requisition_id}",
        success=(f"/requisitions/{requisition_id}", "Requisition rejected"),
        err="Could not reject the requisition",
    )


@router.post("/requisitions/{requisition_id}/convert-to-po")
def convert_requisition_to_po(
    request: Request,
    requisition_id: uuid.UUID,
    supplier_id: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_order.create")),
):
    return form_action(
        db,
        lambda: RequisitionService(db).convert_to_po(
            requisition_id, supplier_id=uuid.UUID(supplier_id), actor_id=actor.id
        ),
        back=f"/requisitions/{requisition_id}",
        success=lambda po: (f"/purchase-orders/{po.id}", f"Purchase order {po.po_no} created"),
        err="Could not convert the requisition to a purchase order",
    )


@router.post("/requisitions/{requisition_id}/convert-to-rfq")
def convert_requisition_to_rfq(
    request: Request,
    requisition_id: uuid.UUID,
    supplier_ids: list[str] = Form([]),
    due_date: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("rfq.issue")),
):
    return form_action(
        db,
        lambda: RequisitionService(db).convert_to_rfq(
            requisition_id,
            supplier_ids=[uuid.UUID(s) for s in supplier_ids if s.strip()],
            due_date=date.fromisoformat(due_date) if due_date else None,
            actor_id=actor.id,
        ),
        back=f"/requisitions/{requisition_id}",
        success=lambda rfq: (f"/rfqs/{rfq.id}", f"RFQ {rfq.rfq_no} issued"),
        err="Could not raise an RFQ from the requisition",
    )


# --- RFQs --------------------------------------------------------------------


@router.get("/rfqs")
def list_rfqs(request: Request, db: Session = Depends(get_db)):
    project = RfqService(db).to_read_many
    if wants_csv(request):
        return csv_response_from_request(request, db, RFQ_LIST, project=project)
    return render(
        request,
        "rfqs/list.html",
        view=view_from_request(request, db, RFQ_LIST, project=project),
        **_pickers(db),
    )


@router.post("/rfqs")
def create_rfq(
    request: Request,
    supplier_ids: list[str] = Form([]),
    due_date: str = Form(""),
    note: str = Form(""),
    product_code: list[str] = Form([]),
    qty: list[str] = Form([]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("rfq.issue")),
):
    def work():
        payload = RfqCreate(
            supplier_ids=[uuid.UUID(s) for s in supplier_ids if s.strip()],
            due_date=date.fromisoformat(due_date) if due_date else None,
            note=note or None,
            lines=[
                RfqLineCreate(product_id=pid, qty=q)
                for pid, q in _lines(db, product_code, qty)
            ],
        )
        return RfqService(db).issue(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/rfqs",
        success=lambda rfq: (f"/rfqs/{rfq.id}", f"RFQ {rfq.rfq_no} issued"),
        err="Could not issue the RFQ",
    )


@router.get("/rfqs/{rfq_id}")
def rfq_detail(request: Request, rfq_id: uuid.UUID, db: Session = Depends(get_db)):
    rfq = RfqService(db).get(rfq_id)
    quoted = {q.supplier_id for q in rfq.quotations}
    return render(
        request,
        "rfqs/detail.html",
        rfq=rfq,
        # Only suppliers who have not answered yet can be quoted for.
        pending=[s for s in rfq.suppliers if s.supplier_id not in quoted],
        history=ActivityService(db).history("rfq", rfq_id),
    )


@router.post("/rfqs/{rfq_id}/quotes")
def capture_quote(
    request: Request,
    rfq_id: uuid.UUID,
    supplier_id: str = Form(...),
    lead_time_days: str = Form(""),
    valid_until: str = Form(""),
    note: str = Form(""),
    product_id: list[str] = Form([]),
    unit_price_rupees: list[str] = Form([]),
    moq: list[str] = Form([]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("quotation.capture")),
):
    def work():
        lines: list[QuotationLineInput] = []
        for pid, price, m in zip(product_id, unit_price_rupees, moq, strict=False):
            if not pid.strip() or not price.strip():
                continue
            lines.append(
                QuotationLineInput(
                    product_id=uuid.UUID(pid),
                    unit_price_minor=int(round(float(price) * 100)),
                    moq=Decimal(str(m)) if m.strip() else None,
                )
            )
        payload = QuotationCreate(
            supplier_id=uuid.UUID(supplier_id),
            valid_until=date.fromisoformat(valid_until) if valid_until else None,
            lead_time_days=int(lead_time_days) if lead_time_days.strip() else None,
            note=note or None,
            lines=lines,
        )
        return RfqService(db).capture_quote(rfq_id, payload, actor_id=actor.id)

    return form_action(
        db, work, back=f"/rfqs/{rfq_id}",
        success=lambda q: (f"/rfqs/{rfq_id}", f"Quotation {q.quotation_no} captured"),
        err="Could not capture the quotation",
    )


@router.post("/rfqs/{rfq_id}/award")
def award_rfq(
    request: Request,
    rfq_id: uuid.UUID,
    quotation_id: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_order.create")),
):
    return form_action(
        db,
        lambda: RfqService(db).award(
            rfq_id, uuid.UUID(quotation_id), actor_id=actor.id
        ),
        back=f"/rfqs/{rfq_id}",
        success=lambda po: (f"/purchase-orders/{po.id}", f"Awarded — {po.po_no} created"),
        err="Could not award the RFQ",
    )
