"""Sales router — thin; delegates to SalesOrderService."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.sales.schemas import (
    SalesOrderCreate,
    SalesOrderDetail,
    SalesOrderPage,
)
from app.modules.sales.service import SalesOrderService

router = APIRouter(tags=["sales"])


@router.get("/sales-orders", response_model=SalesOrderPage)
def list_sales_orders(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = SalesOrderService(db).list(status=status, page=page, page_size=page_size)
    return SalesOrderPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/sales-orders", response_model=SalesOrderDetail, status_code=201)
def create_sales_order(
    payload: SalesOrderCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("sales_order.create")),
):
    return SalesOrderService(db).create(payload, actor_id=actor.id)


@router.get("/sales-orders/{order_id}", response_model=SalesOrderDetail)
def get_sales_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    return SalesOrderService(db).get(order_id)


@router.post("/sales-orders/{order_id}/confirm", response_model=SalesOrderDetail)
def confirm_sales_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("sales_order.confirm")),
):
    return SalesOrderService(db).confirm(order_id, actor_id=actor.id)


@router.post("/sales-orders/{order_id}/fulfill", response_model=SalesOrderDetail)
def fulfill_sales_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("sales_order.fulfill")),
):
    return SalesOrderService(db).fulfill(order_id, actor_id=actor.id)


@router.post("/sales-orders/{order_id}/invoice", response_model=SalesOrderDetail)
def invoice_sales_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("sales_order.invoice")),
):
    return SalesOrderService(db).invoice(order_id, actor_id=actor.id)
