"""Procurement router — thin; delegates to the services in `service.py` (the PO/GRN
chain) and `preorder.py` (requisitions, RFQs, quotations)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.procurement.preorder import RequisitionService, RfqService
from app.modules.procurement.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptListRow,
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderPage,
    QuotationCreate,
    QuotationHistoryRow,
    QuotationRead,
    QuoteComparison,
    RequisitionCreate,
    RequisitionDetail,
    RfqCreate,
    RfqDetail,
)
from app.modules.procurement.service import GoodsReceiptService, PurchaseOrderService

router = APIRouter(tags=["procurement"])


@router.get("/purchase-orders", response_model=PurchaseOrderPage)
def list_purchase_orders(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = PurchaseOrderService(db).list(status=status, page=page, page_size=page_size)
    return PurchaseOrderPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/purchase-orders", response_model=PurchaseOrderDetail, status_code=201)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("purchase_order.create")),
):
    return PurchaseOrderService(db).create(payload, actor_id=actor.id)


@router.get("/purchase-orders/{order_id}", response_model=PurchaseOrderDetail)
def get_purchase_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    return PurchaseOrderService(db).get(order_id)


@router.post("/purchase-orders/{order_id}/confirm", response_model=PurchaseOrderDetail)
def confirm_purchase_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("purchase_order.confirm")),
):
    return PurchaseOrderService(db).confirm(order_id, actor_id=actor.id)


@router.post("/purchase-orders/{order_id}/receive", response_model=PurchaseOrderDetail)
def receive_purchase_order(
    order_id: uuid.UUID,
    payload: GoodsReceiptCreate | None = None,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("goods_receipt.receive")),
):
    return GoodsReceiptService(db).receive(order_id, payload, actor_id=actor.id)


@router.post("/purchase-orders/{order_id}/bill", response_model=PurchaseOrderDetail)
def bill_purchase_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("bill.issue")),
):
    return PurchaseOrderService(db).bill(order_id, actor_id=actor.id)


@router.get("/goods-receipts", response_model=list[GoodsReceiptListRow])
def list_goods_receipts(db: Session = Depends(get_db)):
    return GoodsReceiptService(db).list_all()


# --- pre-order: requisitions -------------------------------------------------


@router.post("/requisitions", response_model=RequisitionDetail, status_code=201)
def create_requisition(
    payload: RequisitionCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("purchase_requisition.create")),
):
    return RequisitionService(db).create(payload, actor_id=actor.id)


@router.get("/requisitions/{requisition_id}", response_model=RequisitionDetail)
def get_requisition(requisition_id: uuid.UUID, db: Session = Depends(get_db)):
    return RequisitionService(db).get(requisition_id)


@router.post("/requisitions/{requisition_id}/approve", response_model=RequisitionDetail)
def approve_requisition(
    requisition_id: uuid.UUID,
    reason: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("purchase_requisition.approve")),
):
    return RequisitionService(db).approve(requisition_id, reason=reason, actor_id=actor.id)


@router.post("/requisitions/{requisition_id}/reject", response_model=RequisitionDetail)
def reject_requisition(
    requisition_id: uuid.UUID,
    reason: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("purchase_requisition.approve")),
):
    return RequisitionService(db).reject(requisition_id, reason=reason, actor_id=actor.id)


@router.post(
    "/requisitions/{requisition_id}/convert-to-po",
    response_model=PurchaseOrderDetail,
    status_code=201,
)
def convert_requisition_to_po(
    requisition_id: uuid.UUID,
    supplier_id: uuid.UUID = Body(..., embed=True),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("purchase_order.create")),
):
    return RequisitionService(db).convert_to_po(
        requisition_id, supplier_id=supplier_id, actor_id=actor.id
    )


@router.post(
    "/requisitions/{requisition_id}/convert-to-rfq", response_model=RfqDetail, status_code=201
)
def convert_requisition_to_rfq(
    requisition_id: uuid.UUID,
    supplier_ids: list[uuid.UUID] = Body(..., embed=True),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("rfq.issue")),
):
    return RequisitionService(db).convert_to_rfq(
        requisition_id, supplier_ids=supplier_ids, actor_id=actor.id
    )


# --- pre-order: RFQs + quotations --------------------------------------------


@router.post("/rfqs", response_model=RfqDetail, status_code=201)
def issue_rfq(
    payload: RfqCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("rfq.issue")),
):
    return RfqService(db).issue(payload, actor_id=actor.id)


@router.get("/rfqs/{rfq_id}", response_model=RfqDetail)
def get_rfq(rfq_id: uuid.UUID, db: Session = Depends(get_db)):
    return RfqService(db).get(rfq_id)


@router.get("/rfqs/{rfq_id}/comparison", response_model=QuoteComparison)
def compare_rfq(rfq_id: uuid.UUID, db: Session = Depends(get_db)):
    """The side-by-side (R4.5). A pure read — it writes nothing (G15)."""
    return RfqService(db).comparison(rfq_id)


@router.post("/rfqs/{rfq_id}/quotations", response_model=QuotationRead, status_code=201)
def capture_quotation(
    rfq_id: uuid.UUID,
    payload: QuotationCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("quotation.capture")),
):
    return RfqService(db).capture_quote(rfq_id, payload, actor_id=actor.id)


@router.post("/rfqs/{rfq_id}/award", response_model=PurchaseOrderDetail, status_code=201)
def award_rfq(
    rfq_id: uuid.UUID,
    quotation_id: uuid.UUID = Body(..., embed=True),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("purchase_order.create")),
):
    return RfqService(db).award(rfq_id, quotation_id, actor_id=actor.id)


@router.get("/products/{product_id}/quotations", response_model=list[QuotationHistoryRow])
def product_quotation_history(
    product_id: uuid.UUID,
    supplier_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Quotation history per product, optionally narrowed to one supplier (R4.6)."""
    return RfqService(db).quotation_history(product_id, supplier_id=supplier_id)
