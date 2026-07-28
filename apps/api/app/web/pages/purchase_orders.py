"""Purchase order pages: list + new (multi-line) + detail with workflow actions."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.procurement.schemas import PurchaseOrderCreate, PurchaseOrderLineCreate
from app.modules.procurement.service import GoodsReceiptService, PurchaseOrderService
from app.modules.products.service import ProductService
from app.modules.suppliers.service import SupplierService
from app.web.core import form_action, render
from app.web.security import require_web_permission

router = APIRouter()


@router.get("/purchase-orders")
def list_purchase_orders(
    request: Request, status: str | None = None, db: Session = Depends(get_db)
):
    rows, total = PurchaseOrderService(db).list(status=status or None, page=1, page_size=200)
    return render(
        request,
        "purchase_orders/list.html",
        orders=rows,
        total=total,
        status=status or "",
    )


@router.get("/purchase-orders/new")
def new_purchase_order(request: Request, db: Session = Depends(get_db)):
    suppliers, _ = SupplierService(db).list(search=None, page=1, page_size=200)
    products, _ = ProductService(db).list(search=None, category_id=None, page=1, page_size=300)
    return render(
        request,
        "purchase_orders/new.html",
        suppliers=suppliers,
        products=products,
        rows=range(6),
    )


@router.post("/purchase-orders")
def create_purchase_order(
    request: Request,
    supplier_id: str = Form(...),
    order_date: str = Form(""),
    product_id: list[str] = Form([]),
    qty: list[str] = Form([]),
    unit_price_rupees: list[str] = Form([]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_order.create")),
):
    def work():
        lines: list[PurchaseOrderLineCreate] = []
        for pid, q, up in zip(product_id, qty, unit_price_rupees, strict=False):
            if not pid or not q:
                continue
            unit_price_minor = int(round(float(up) * 100)) if up else None
            lines.append(
                PurchaseOrderLineCreate(
                    product_id=uuid.UUID(pid),
                    qty=Decimal(str(q)),
                    unit_price_minor=unit_price_minor,
                )
            )
        payload = PurchaseOrderCreate(
            supplier_id=uuid.UUID(supplier_id),
            order_date=date.fromisoformat(order_date) if order_date else None,
            lines=lines,
        )
        return PurchaseOrderService(db).create(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/purchase-orders/new",
        success=lambda po: (f"/purchase-orders/{po.id}", "PO created"),
        err="Could not create PO",
    )


@router.get("/purchase-orders/{order_id}")
def purchase_order_detail(request: Request, order_id: uuid.UUID, db: Session = Depends(get_db)):
    # A missing PO raises NotFoundError → the web error handler renders error.html.
    po = PurchaseOrderService(db).get(order_id)
    return render(request, "purchase_orders/detail.html", po=po)


@router.post("/purchase-orders/{order_id}/confirm")
def confirm_purchase_order(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_order.confirm")),
):
    return form_action(
        db, lambda: PurchaseOrderService(db).confirm(order_id, actor_id=actor.id),
        back=f"/purchase-orders/{order_id}",
        success=(f"/purchase-orders/{order_id}", "PO confirmed"),
    )


@router.post("/purchase-orders/{order_id}/receive")
def receive_purchase_order(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("goods_receipt.receive")),
):
    return form_action(
        db, lambda: GoodsReceiptService(db).receive(order_id, None, actor_id=actor.id),
        back=f"/purchase-orders/{order_id}",
        success=(f"/purchase-orders/{order_id}", "Goods received"),
    )


@router.post("/purchase-orders/{order_id}/bill")
def bill_purchase_order(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("bill.issue")),
):
    return form_action(
        db, lambda: PurchaseOrderService(db).bill(order_id, actor_id=actor.id),
        back=f"/purchase-orders/{order_id}",
        success=(f"/purchase-orders/{order_id}", "Bill created"),
    )
