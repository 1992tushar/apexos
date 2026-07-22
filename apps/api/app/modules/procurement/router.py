"""Procurement router — thin; delegates to PurchaseOrderService / GoodsReceiptService."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.procurement.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptListRow,
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderPage,
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
