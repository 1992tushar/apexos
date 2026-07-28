"""Products pages: list + inline create. No detail route."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.config.service import ConfigService
from app.modules.products.schemas import ProductCreate
from app.modules.products.service import ProductService
from app.web.core import form_action, render
from app.web.security import require_web_permission

router = APIRouter()


@router.get("/products")
def list_products(request: Request, db: Session = Depends(get_db)):
    rows, total = ProductService(db).list(
        search=None, category_id=None, page=1, page_size=300
    )
    return render(
        request,
        "products/list.html",
        products=rows,
        total=total,
        categories=ConfigService(db).categories(),
        brands=ConfigService(db).brands(),
        uoms=ConfigService(db).uoms(),
        pmodels=ConfigService(db).procurement_models(),
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
