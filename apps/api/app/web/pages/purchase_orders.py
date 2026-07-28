"""Purchase order pages: list + new (multi-line) + detail with workflow actions."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.procurement.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptLineInput,
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderRevise,
    PurchaseOrderReviseLine,
)
from app.modules.procurement.service import GoodsReceiptService, PurchaseOrderService
from app.modules.products.service import ProductService
from app.modules.suppliers.service import SupplierService
from app.web.core import form_action, render
from app.web.pages.preorder import _lines
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
    product_code: list[str] = Form([]),
    qty: list[str] = Form([]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_order.create")),
):
    def work():
        # R4.12: SKUs are typed, not picked from a 311-option <select>, and the buy
        # price defaults from history (`PricingService.resolve_purchase_minor`, which
        # `create` already consults when unit_price_minor is None) rather than being
        # retyped. Override it on the revision screen if the supplier quotes another.
        lines = [
            PurchaseOrderLineCreate(product_id=pid, qty=quantity)
            for pid, quantity in _lines(db, product_code, qty)
        ]
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


@router.post("/purchase-orders/{order_id}/revise")
def revise_purchase_order(
    request: Request,
    order_id: uuid.UUID,
    reason: str = Form(...),
    line_product_id: list[str] = Form([]),
    line_qty: list[str] = Form([]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("purchase_order.revise")),
):
    """R4.7 — the founder edits quantities on the detail screen; the service
    appends a revision rather than mutating the confirmed order."""

    def work():
        lines = [
            PurchaseOrderReviseLine(product_id=uuid.UUID(pid), qty=Decimal(str(q)))
            for pid, q in zip(line_product_id, line_qty, strict=False)
            if pid and q
        ]
        payload = PurchaseOrderRevise(reason=reason, lines=lines)
        return PurchaseOrderService(db).revise(order_id, payload, actor_id=actor.id)

    return form_action(
        db, work,
        back=f"/purchase-orders/{order_id}",
        success=lambda po: (
            f"/purchase-orders/{order_id}",
            f"Revised to version {po.revision_no}",
        ),
        err="Could not revise PO",
    )


@router.post("/purchase-orders/{order_id}/receive")
def receive_purchase_order(
    request: Request,
    order_id: uuid.UUID,
    against_revision_no: str = Form(""),
    receive_product_id: list[str] = Form([]),
    receive_qty: list[str] = Form([]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("goods_receipt.receive")),
):
    """R4.8/R4.10 — a partial receipt, checked against a named revision.

    The form carries the revision it was rendered from, so a tab left open across
    a revision cannot silently book goods against a superseded agreement: the
    service refuses and says which version it is now on.
    """

    def work():
        lines = [
            GoodsReceiptLineInput(product_id=uuid.UUID(pid), qty=Decimal(str(q)))
            for pid, q in zip(receive_product_id, receive_qty, strict=False)
            if pid and q and Decimal(str(q)) > 0
        ]
        payload = GoodsReceiptCreate(
            lines=lines or None,  # None = receive everything still outstanding
            against_revision_no=int(against_revision_no) if against_revision_no else None,
        )
        return GoodsReceiptService(db).receive(order_id, payload, actor_id=actor.id)

    return form_action(
        db, work,
        back=f"/purchase-orders/{order_id}",
        success=(f"/purchase-orders/{order_id}", "Goods received"),
        err="Could not receive goods",
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
