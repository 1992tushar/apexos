"""Pricing service — resolve the applicable selling / purchase price + margin.

Resolution order for selling price (D2 spirit): customer-specific → segment
(customer_type) → list price. Purchase price resolves supplier-specific → any
supplier for the product. Prices are versioned (append, never overwrite, D3);
only current rows (`valid_to IS NULL`) are considered here. `MarginService.gp`
derives gross profit (selling − buying) per line.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.pricing.models import PurchasePrice
from app.modules.pricing.repository import PricingRepository


class PricingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PricingRepository(db)

    def resolve_selling_minor(
        self,
        product_id: uuid.UUID,
        *,
        customer_id: uuid.UUID | None = None,
        customer_type_id: uuid.UUID | None = None,
    ) -> int | None:
        prices = self.repo.selling_prices(product_id)
        if not prices:
            return None
        if customer_id is not None:
            for p in prices:
                if p.customer_id == customer_id:
                    return p.price_minor
        if customer_type_id is not None:
            for p in prices:
                if p.customer_id is None and p.customer_type_id == customer_type_id:
                    return p.price_minor
        for p in prices:
            if p.customer_id is None and p.customer_type_id is None:
                return p.price_minor
        return prices[0].price_minor

    def resolve_purchase_minor(
        self,
        product_id: uuid.UUID,
        *,
        supplier_id: uuid.UUID | None = None,
    ) -> int | None:
        """Effective buy price for a product: supplier-specific first, else any
        current row (falls back to the latest for the product)."""
        prices = self.repo.purchase_prices(product_id)
        if not prices:
            return None
        if supplier_id is not None:
            for p in prices:
                if p.supplier_id == supplier_id:
                    return p.price_minor
        for p in prices:
            if p.supplier_id is None:
                return p.price_minor
        return prices[0].price_minor

    def latest_purchase_minor(self, product_id: uuid.UUID) -> int | None:
        return self.repo.latest_purchase_price(product_id)

    def set_purchase_price(
        self,
        *,
        product_id: uuid.UUID,
        supplier_id: uuid.UUID | None,
        price_minor: int,
        actor_id: uuid.UUID | None = None,
    ) -> PurchasePrice:
        """Append a new purchase-price version, closing the prior open row(s) for
        this product+supplier scope (D3: history is kept, never overwritten)."""
        now = datetime.now(UTC)
        self.repo.supersede_purchase_prices(product_id, supplier_id, now)
        price = PurchasePrice(
            product_id=product_id,
            supplier_id=supplier_id,
            price_minor=price_minor,
            valid_from=now,
            created_by=actor_id,
        )
        return self.repo.add_purchase_price(price)


class MarginService:
    """Gross-profit (GP) helper: selling − buying. Central KPI (Foundation §4)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.pricing = PricingService(db)

    def gp(self, line) -> int:
        """GP in minor units for one order/PO line, from its stored unit price and
        the product's current buy price × qty. Accepts any object exposing
        `product_id`, `qty`, and `unit_price_minor`."""
        from decimal import Decimal

        buy = self.pricing.latest_purchase_minor(line.product_id) or 0
        unit_gp = int(line.unit_price_minor) - int(buy)
        return int((Decimal(unit_gp) * Decimal(line.qty)).quantize(Decimal("1")))
