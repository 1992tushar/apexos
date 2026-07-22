"""Pricing router — versioned purchase prices (buy side). Selling prices are read
through Product / Sales projections in the spine; buy prices are managed here."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.schemas import PurchasePriceCreate, PurchasePriceRead
from app.modules.pricing.service import PricingService

router = APIRouter(tags=["pricing"])


@router.get("/purchase-prices", response_model=list[PurchasePriceRead])
def list_purchase_prices(
    product_id: uuid.UUID = Query(...),
    supplier_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """List current purchase-price versions for a product (optionally a supplier)."""
    return PricingRepository(db).purchase_prices(product_id, supplier_id)


@router.post("/purchase-prices", response_model=PurchasePriceRead, status_code=201)
def set_purchase_price(
    payload: PurchasePriceCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("purchase_price.set")),
):
    """Set a purchase price (appends a new version; prior version is closed, D3)."""
    return PricingService(db).set_purchase_price(
        product_id=payload.product_id,
        supplier_id=payload.supplier_id,
        price_minor=payload.price_minor,
        actor_id=actor.id,
    )
