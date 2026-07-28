"""Quotation screens (R9.1–R9.3): list + create, detail + the four verbs.

Every POST carries the R1.4 authz guard (G10) and goes through `form_action`, so a refusal
rolls back and flashes rather than crashing. The line grid reuses Part 3's `<datalist>` SKU
picker and its resolver — a `<select>` of 311 products cannot be typed into, and writing a
second SKU resolver is the duplication G16 forbids.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ValidationError
from app.core.security import Actor
from app.modules.customers.service import CustomerService
from app.modules.products.service import ProductService
from app.modules.sales.quotation import QuotationService
from app.modules.sales.schemas import (
    QuotationCreate,
    QuotationLineCreate,
    QuotationRevise,
)
from app.web.core import form_action, render
from app.web.pages.preorder import _lines as resolve_sku_lines
from app.web.security import require_web_permission

router = APIRouter()


def _quote_lines(db: Session, product_code: list[str], qty: list[str], price: list[str]):
    """Resolve the typed SKU grid into priced quotation lines.

    Reuses Part 3's `_lines` resolver for the SKU→id step — it names an unknown SKU back to
    the user rather than silently dropping the row, which is the failure a free-text picker
    must not have. The per-line price is this screen's addition: a quotation usually names
    its own price rather than taking the list price.
    """
    resolved = resolve_sku_lines(db, product_code, qty)
    # `resolve_sku_lines` skips blank rows, so the price list is indexed against the rows it
    # KEPT rather than against the raw form fields — otherwise a blank row in the middle
    # would shift every price down a line.
    kept = [
        i
        for i, (code, quantity) in enumerate(zip(product_code, qty, strict=False))
        if code.strip() and quantity.strip()
    ]
    prices = [p.strip() for p in price] if price else []

    out: list[QuotationLineCreate] = []
    for position, (product_id, quantity) in enumerate(resolved):
        source_row = kept[position] if position < len(kept) else None
        raw = prices[source_row] if source_row is not None and source_row < len(prices) else ""
        out.append(
            QuotationLineCreate(
                product_id=product_id,
                qty=quantity,
                unit_price_minor=int(round(float(raw) * 100)) if raw else None,
            )
        )
    if not out:
        raise ValidationError("A quotation needs at least one line")
    return out


@router.get("/quotations")
def list_quotations(request: Request, db: Session = Depends(get_db)):
    svc = QuotationService(db)
    rows = svc.list()
    products, _ = ProductService(db).list(
        search=None, category_id=None, page=1, page_size=400
    )
    customers, _ = CustomerService(db).list(search=None, page=1, page_size=300)
    return render(
        request,
        "quotations/list.html",
        rows=rows,
        products=products,
        customers=customers,
        open_count=sum(1 for r in rows if r.status in ("draft", "sent")),
        lapsed_count=sum(1 for r in rows if r.past_validity and r.status == "sent"),
    )


@router.get("/quotations/{quotation_id}")
def quotation_detail(request: Request, quotation_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.modules.activity.service import ActivityService

    quote = QuotationService(db).get(quotation_id)
    products, _ = ProductService(db).list(
        search=None, category_id=None, page=1, page_size=400
    )
    return render(
        request,
        "quotations/detail.html",
        q=quote,
        products=products,
        history=ActivityService(db).history("quotation", quotation_id),
    )


@router.post("/quotations")
def create_quotation(
    request: Request,
    customer_id: str = Form(...),
    valid_until: str = Form(""),
    note: str = Form(""),
    product_code: list[str] = Form(default=[]),
    qty: list[str] = Form(default=[]),
    unit_price_rupees: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("quotation.create")),
):
    def work():
        return QuotationService(db).create(
            QuotationCreate(
                customer_id=uuid.UUID(customer_id),
                valid_until=date.fromisoformat(valid_until) if valid_until.strip() else None,
                note=note or None,
                lines=_quote_lines(db, product_code, qty, unit_price_rupees),
            ),
            actor_id=actor.id,
        )

    return form_action(
        db, work, back="/quotations",
        success=lambda q: (f"/quotations/{q.id}", f"{q.quotation_no} raised"),
        err="Could not raise the quotation",
    )


@router.post("/quotations/{quotation_id}/send")
def send_quotation(
    request: Request,
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("quotation.send")),
):
    """R9.1 — and this is where revision 1 is preserved (R9.2)."""
    return form_action(
        db, lambda: QuotationService(db).send(quotation_id, actor_id=actor.id),
        back=f"/quotations/{quotation_id}",
        success=lambda q: (
            f"/quotations/{quotation_id}",
            f"{q.quotation_no} sent — v1 recorded",
        ),
        err="Could not send the quotation",
    )


@router.post("/quotations/{quotation_id}/revise")
def revise_quotation(
    request: Request,
    quotation_id: uuid.UUID,
    reason: str = Form(...),
    valid_until: str = Form(""),
    product_code: list[str] = Form(default=[]),
    qty: list[str] = Form(default=[]),
    unit_price_rupees: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("quotation.revise")),
):
    """R9.2 — appends a version. The prior one stays readable verbatim."""

    def work():
        return QuotationService(db).revise(
            quotation_id,
            QuotationRevise(
                reason=reason,
                valid_until=date.fromisoformat(valid_until) if valid_until.strip() else None,
                lines=_quote_lines(db, product_code, qty, unit_price_rupees),
            ),
            actor_id=actor.id,
        )

    return form_action(
        db, work, back=f"/quotations/{quotation_id}",
        success=lambda q: (
            f"/quotations/{quotation_id}",
            f"{q.quotation_no} revised to v{q.revision_count}",
        ),
        err="Could not revise the quotation",
    )


@router.post("/quotations/{quotation_id}/expire")
def expire_quotation(
    request: Request,
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("quotation.expire")),
):
    return form_action(
        db, lambda: QuotationService(db).expire(quotation_id, actor_id=actor.id),
        back=f"/quotations/{quotation_id}",
        success=(f"/quotations/{quotation_id}", "Quotation expired"),
        err="Could not expire the quotation",
    )


@router.post("/quotations/{quotation_id}/convert")
def convert_quotation(
    request: Request,
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("sales_order.create")),
):
    """R9.3 — ONE action, carrying the quoted prices forward."""
    return form_action(
        db, lambda: QuotationService(db).convert(quotation_id, actor_id=actor.id),
        back=f"/quotations/{quotation_id}",
        success=lambda order: (
            f"/sales/{order.id}",
            f"Converted to {order.order_no} at the quoted prices",
        ),
        err="Could not convert the quotation",
    )
