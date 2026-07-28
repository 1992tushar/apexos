"""Products pages: list + inline create + detail.

The list is the shared machinery (R2.11): one `ListSpec` in
`app.modules.products.listing` drives the query, the table, the filters and the
CSV export, so this module holds no query and no table markup.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.activity.service import ActivityService
from app.modules.config.service import ConfigService
from app.modules.products.listing import PRODUCT_LIST, PRODUCT_STATUS_CHOICES
from app.modules.products.schemas import ProductCreate
from app.modules.products.service import ProductService
from app.web.core import form_action, render
from app.web.listing import csv_response_from_request, view_from_request, wants_csv
from app.web.security import require_web_permission

router = APIRouter()


@router.get("/products")
def list_products(request: Request, db: Session = Depends(get_db)):
    project = ProductService(db).to_read_many
    if wants_csv(request):
        return csv_response_from_request(request, db, PRODUCT_LIST, project=project)
    config = ConfigService(db)
    return render(
        request,
        "products/list.html",
        view=view_from_request(request, db, PRODUCT_LIST, project=project),
        categories=config.categories(),
        brands=config.brands(),
        uoms=config.uoms(),
        pmodels=config.procurement_models(),
    )


@router.get("/products/{product_id}")
def product_detail(request: Request, product_id: uuid.UUID, db: Session = Depends(get_db)):
    # A missing product raises NotFoundError → the web error handler renders error.html.
    product = ProductService(db).get(product_id)
    return render(
        request,
        "products/detail.html",
        p=product,
        statuses=PRODUCT_STATUS_CHOICES,
        history=ActivityService(db).history("product", product_id),
    )


@router.post("/products")
def create_product(
    request: Request,
    name: str = Form(...),
    category_id: str = Form(...),
    brand_id: str = Form(...),
    uom_id: str = Form(...),
    procurement_model_id: str = Form(""),
    specification: str = Form(""),
    launch_phase: str = Form(""),
    reorder_level: str = Form("0"),
    selling_price_rupees: str = Form(""),
    purchase_price_rupees: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("product.create")),
):
    def work():
        payload = ProductCreate(
            name=name,
            category_id=uuid.UUID(category_id),
            brand_id=uuid.UUID(brand_id),
            uom_id=uuid.UUID(uom_id),
            procurement_model_id=uuid.UUID(procurement_model_id)
            if procurement_model_id
            else None,
            specification=specification or None,
            launch_phase=launch_phase or None,
            reorder_level=Decimal(str(reorder_level or 0)),
            selling_price_minor=int(round(float(selling_price_rupees) * 100))
            if selling_price_rupees
            else None,
            purchase_price_minor=int(round(float(purchase_price_rupees) * 100))
            if purchase_price_rupees
            else None,
        )
        return ProductService(db).create(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/products",
        success=("/products", "Product created"),
        err="Could not create product",
    )


@router.post("/products/{product_id}/status")
def set_product_status(
    request: Request,
    product_id: uuid.UUID,
    status: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("product.update")),
):
    """Move a product through its lifecycle (R3.9); refused if open work reads it."""
    return form_action(
        db,
        lambda: ProductService(db).set_status(product_id, status, actor_id=actor.id),
        back=f"/products/{product_id}",
        success=(f"/products/{product_id}", f"Product marked {status}"),
        err="Could not change the product's status",
    )


@router.post("/products/{product_id}/delete")
def delete_product(
    request: Request,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("product.delete")),
):
    return form_action(
        db, lambda: ProductService(db).delete(product_id, actor_id=actor.id),
        back="/products",
        success=("/products", "Product deleted"),
        err="Could not delete product",
    )
