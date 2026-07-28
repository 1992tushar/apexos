"""Sales order pages: list + filter, new-order form, detail + state-machine actions."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.customers.service import CustomerService
from app.modules.products.service import ProductService
from app.modules.sales.fast_entry import FastEntryService
from app.modules.sales.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.sales.service import SalesOrderService
from app.web.core import form_action, render
from app.web.pages.preorder import _lines as resolve_sku_lines
from app.web.security import require_web_permission

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
def new_sale(
    request: Request,
    customer_id: str = "",
    repeat: str = "",
    db: Session = Depends(get_db),
):
    """The fast entry form (R9.12–R9.14).

    `?customer_id=…&repeat=1` prefills the lines from that customer's last order — the
    reorder-from-last-order path. It is a GET so the founder can see and adjust what they are
    about to order rather than having an order created behind their back.
    """
    customers, _ = CustomerService(db).list(search=None, page=1, page_size=200)
    products, _ = ProductService(db).list(
        search=None, category_id=None, page=1, page_size=300
    )
    fast = FastEntryService(db)

    prefill: list[tuple[str, Decimal, int]] = []
    selected: uuid.UUID | None = None
    if customer_id.strip():
        try:
            selected = uuid.UUID(customer_id)
        except ValueError:
            selected = None
    if selected is not None and repeat.strip():
        prefill = fast.last_order_lines(selected)

    return render(
        request,
        "sales/new.html",
        customers=customers,
        products=products,
        # R9.14 — generous row count. A blank row costs nothing: `_lines` skips it.
        line_rows=range(max(len(prefill) + 2, 8)),
        # R9.12 — price and AVAILABLE stock beside every SKU in the picker.
        hints=fast.picker_hints(products),
        prefill=prefill,
        selected_customer_id=str(selected) if selected else "",
        repeatable=fast.customers_with_history(),
    )


@router.post("/sales")
def create_sale(
    request: Request,
    customer_id: str = Form(...),
    order_date: str = Form(""),
    product_code: list[str] = Form(default=[]),
    qty: list[str] = Form(default=[]),
    unit_price_rupees: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("sales_order.create")),
):
    """Create the order from the typed SKU grid (R9.12).

    The form now posts `product_code` (a SKU) rather than `product_id`, because the picker is
    a `<datalist>` and datalists submit display text. `_lines` — Part 3's resolver, reused
    rather than reimplemented (G16) — turns those into ids and **names an unknown SKU back to
    the founder** instead of silently dropping the row.
    """

    def work():
        resolved = resolve_sku_lines(db, product_code, qty)
        # Prices are indexed against the rows the resolver KEPT, not the raw form fields, or
        # a blank row in the middle would shift every price down a line.
        kept = [
            i
            for i, (code, quantity) in enumerate(zip(product_code, qty, strict=False))
            if code.strip() and quantity.strip()
        ]
        raw_prices = [p.strip() for p in unit_price_rupees] if unit_price_rupees else []

        lines: list[SalesOrderLineCreate] = []
        for position, (pid, quantity) in enumerate(resolved):
            source_row = kept[position] if position < len(kept) else None
            raw = (
                raw_prices[source_row]
                if source_row is not None and source_row < len(raw_prices)
                else ""
            )
            lines.append(
                SalesOrderLineCreate(
                    product_id=pid,
                    qty=quantity,
                    unit_price_minor=int(round(float(raw) * 100)) if raw else None,
                )
            )
        payload = SalesOrderCreate(
            customer_id=uuid.UUID(customer_id),
            order_date=date.fromisoformat(order_date) if order_date else None,
            lines=lines,
        )
        return SalesOrderService(db).create(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/sales/new",
        success=lambda order: (f"/sales/{order.id}", "Order created"),
        err="Could not create order",
    )


@router.get("/sales/{order_id}")
def sale_detail(request: Request, order_id: uuid.UUID, db: Session = Depends(get_db)):
    # A missing order raises NotFoundError → the web error handler renders error.html.
    so = SalesOrderService(db).get(order_id)
    return render(request, "sales/detail.html", so=so)


@router.post("/sales/{order_id}/confirm")
def confirm_sale(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("sales_order.confirm")),
):
    return form_action(
        db, lambda: SalesOrderService(db).confirm(order_id, actor_id=actor.id),
        back=f"/sales/{order_id}", success=(f"/sales/{order_id}", "Order confirmed"),
    )


@router.post("/sales/{order_id}/fulfill")
def fulfill_sale(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("sales_order.fulfill")),
):
    return form_action(
        db, lambda: SalesOrderService(db).fulfill(order_id, actor_id=actor.id),
        back=f"/sales/{order_id}", success=(f"/sales/{order_id}", "Order fulfilled"),
    )


@router.post("/sales/{order_id}/invoice")
def invoice_sale(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("sales_order.invoice")),
):
    return form_action(
        db, lambda: SalesOrderService(db).invoice(order_id, actor_id=actor.id),
        back=f"/sales/{order_id}", success=(f"/sales/{order_id}", "Invoice created"),
    )
