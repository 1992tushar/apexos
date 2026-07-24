"""Products router — thin; delegates to ProductService."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.products.schemas import ProductCreate, ProductPage, ProductRead
from app.modules.products.service import ProductService

router = APIRouter(tags=["products"])


@router.get("/products", response_model=ProductPage)
def list_products(
    search: str | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = ProductService(db).list(
        search=search, category_id=category_id, page=page, page_size=page_size
    )
    return ProductPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/products", response_model=ProductRead, status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("product.create")),
):
    return ProductService(db).create(payload, actor_id=actor.id)


@router.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return ProductService(db).get(product_id)
