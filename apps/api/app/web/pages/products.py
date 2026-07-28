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
from app.modules.procurement.preorder import RfqService
from app.modules.products.listing import PRODUCT_LIST, PRODUCT_STATUS_CHOICES
from app.modules.products.schemas import ProductCreate
from app.modules.products.service import ProductService
from app.modules.suppliers.schemas import ProductSupplierUpsert
from app.modules.suppliers.service import ProductSupplierService, SupplierService
from app.modules.suppliers.vendor import VendorIntelService
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
        # Every price a supplier has quoted for this SKU (R4.6). A pure read.
        quote_history=RfqService(db).quotation_history(product_id),
        # R5.12 — who can supply this, preferred first, each row carrying the
        # supplier's rendered intelligence; and what has actually been paid over
        # time (R5.6). Both pure reads (G15).
        vendors=ProductSupplierService(db).list_for_product(product_id),
        price_history=VendorIntelService(db).price_history(product_id),
        suppliers=SupplierService(db).list(search=None, page=1, page_size=200)[0],
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


# --- the product↔supplier mapping (R5.1, R5.5) ------------------------------
# Three verbs, all on the product's page because that is where the founder asks
# "who can supply this?". Each carries the R1.4 authz guard (G10) and goes through
# `form_action`, so a refusal rolls back and flashes rather than crashing.


@router.post("/products/{product_id}/suppliers")
def link_product_supplier(
    request: Request,
    product_id: uuid.UUID,
    supplier_id: str = Form(...),
    moq: str = Form(""),
    note: str = Form(""),
    is_preferred: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("product_supplier.create")),
):
    """Link a supplier to this product, or amend the link — `upsert` is idempotent."""

    def work():
        payload = ProductSupplierUpsert(
            product_id=product_id,
            supplier_id=uuid.UUID(supplier_id),
            is_preferred=bool(is_preferred),
            moq=Decimal(moq) if moq.strip() else None,
            note=note or None,
        )
        return ProductSupplierService(db).upsert(payload, actor_id=actor.id)

    return form_action(
        db, work, back=f"/products/{product_id}",
        success=lambda row: (f"/products/{product_id}", f"{row.supplier_name} linked"),
        err="Could not link that supplier",
    )


@router.post("/product-suppliers/{link_id}/prefer")
def prefer_product_supplier(
    request: Request,
    link_id: uuid.UUID,
    product_id: uuid.UUID = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("product_supplier.update")),
):
    """Make this the preferred supplier for its product — exclusive per product (R5.1)."""
    return form_action(
        db, lambda: ProductSupplierService(db).set_preferred(link_id, actor_id=actor.id),
        back=f"/products/{product_id}",
        success=lambda row: (f"/products/{product_id}", f"{row.supplier_name} is now preferred"),
        err="Could not set the preferred supplier",
    )


@router.post("/product-suppliers/{link_id}/delete")
def unlink_product_supplier(
    request: Request,
    link_id: uuid.UUID,
    product_id: uuid.UUID = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("product_supplier.delete")),
):
    """Unlink. A preference is not a document, so nothing blocks this (R3.7)."""
    return form_action(
        db, lambda: ProductSupplierService(db).delete(link_id, actor_id=actor.id),
        back=f"/products/{product_id}",
        success=(f"/products/{product_id}", "Supplier unlinked"),
        err="Could not unlink that supplier",
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
