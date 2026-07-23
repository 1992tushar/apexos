"""Sales order pages: list + filter, new-order form, detail + state-machine actions."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import Actor, get_current_actor
from app.modules.customers.service import CustomerService
from app.modules.products.service import ProductService
from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.sales.service import SalesOrderService
from app.web.core import redirect, render

router = APIRouter()

STATUSES = ["draft", "confirmed", "fulfilled", "invoiced"]


@router.get("/sales")
def list_sales(request: Request, status: str | None = None, db: Session = Depends(get_db)):
    rows, total = SalesOrderService(db).list(status=status or None, page=1, page_size=200)
    return render(
        request,
        "sales/list.html",
        rows=rows,
        total=total,
        statuses=STATUSES,
        current_status=status or "",
    )


@router.get("/sales/new")
def new_sale(request: Request, db: Session = Depends(get_db)):
    customers, _ = CustomerService(db).list(search=None, page=1, page_size=200)
    products, _ = ProductService(db).list(
        search=None, category_id=None, page=1, page_size=300
    )
    return render(
        request,
        "sales/new.html",
        customers=customers,
        products=products,
        line_rows=range(6),
    )


@router.post("/sales")
def create_sale(
    request: Request,
    customer_id: str = Form(...),
    order_date: str = Form(""),
    product_id: list[str] = Form([]),
    qty: list[str] = Form([]),
    unit_price_rupees: list[str] = Form([]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        lines: list[SalesOrderLineCreate] = []
        for pid, q, up in zip(product_id, qty, unit_price_rupees):
            if not pid or not q:
                continue
            unit_price_minor = int(round(float(up) * 100)) if up else None
            lines.append(
                SalesOrderLineCreate(
                    product_id=uuid.UUID(pid),
                    qty=Decimal(str(q)),
                    unit_price_minor=unit_price_minor,
                )
            )
        payload = SalesOrderCreate(
            customer_id=uuid.UUID(customer_id),
            order_date=date.fromisoformat(order_date) if order_date else None,
            lines=lines,
        )
        order = SalesOrderService(db).create(payload, actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/sales/new", err=getattr(exc, "message", "Could not create order"))
    return redirect(f"/sales/{order.id}", ok="Order created")


@router.get("/sales/{order_id}")
def sale_detail(request: Request, order_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        so = SalesOrderService(db).get(order_id)
    except AppError as exc:
        return render(
            request, "error.html", status_code=exc.status_code, code="Not found", message=exc.message
        )
    return render(request, "sales/detail.html", so=so)


@router.post("/sales/{order_id}/confirm")
def confirm_sale(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        SalesOrderService(db).confirm(order_id, actor_id=actor.id)
    except AppError as exc:
        db.rollback()
        return redirect(f"/sales/{order_id}", err=exc.message)
    return redirect(f"/sales/{order_id}", ok="Order confirmed")


@router.post("/sales/{order_id}/fulfill")
def fulfill_sale(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        SalesOrderService(db).fulfill(order_id, actor_id=actor.id)
    except AppError as exc:
        db.rollback()
        return redirect(f"/sales/{order_id}", err=exc.message)
    return redirect(f"/sales/{order_id}", ok="Order fulfilled")


@router.post("/sales/{order_id}/invoice")
def invoice_sale(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        SalesOrderService(db).invoice(order_id, actor_id=actor.id)
    except AppError as exc:
        db.rollback()
        return redirect(f"/sales/{order_id}", err=exc.message)
    return redirect(f"/sales/{order_id}", ok="Invoice created")
