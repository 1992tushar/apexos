"""Pricing repository — current price resolution."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.pricing.models import PurchasePrice, SellingPrice


class PricingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def latest_purchase_price(self, product_id: uuid.UUID) -> int | None:
        return self.db.scalar(
            select(PurchasePrice.price_minor)
            .where(
                PurchasePrice.product_id == product_id,
                PurchasePrice.valid_to.is_(None),
                PurchasePrice.deleted_at.is_(None),
            )
            .order_by(PurchasePrice.valid_from.desc())
            .limit(1)
        )

    def purchase_prices(
        self, product_id: uuid.UUID, supplier_id: uuid.UUID | None = None
    ) -> list[PurchasePrice]:
        """Current purchase-price rows for a product (optionally a given supplier)."""
        stmt = select(PurchasePrice).where(
            PurchasePrice.product_id == product_id,
            PurchasePrice.valid_to.is_(None),
            PurchasePrice.deleted_at.is_(None),
        )
        if supplier_id is not None:
            stmt = stmt.where(PurchasePrice.supplier_id == supplier_id)
        return list(self.db.scalars(stmt.order_by(PurchasePrice.valid_from.desc())))

    def add_purchase_price(self, price: PurchasePrice) -> PurchasePrice:
        self.db.add(price)
        self.db.flush()
        return price

    def supersede_purchase_prices(
        self, product_id: uuid.UUID, supplier_id: uuid.UUID | None, cutoff
    ) -> None:
        """Close open purchase-price versions (append-never-overwrite, D3): set
        `valid_to` on the currently-open rows for this product+supplier scope."""
        for row in self.purchase_prices(product_id, supplier_id):
            row.valid_to = cutoff

    def selling_prices(self, product_id: uuid.UUID) -> list[SellingPrice]:
        return list(
            self.db.scalars(
                select(SellingPrice)
                .where(
                    SellingPrice.product_id == product_id,
                    SellingPrice.valid_to.is_(None),
                    SellingPrice.deleted_at.is_(None),
                )
                .order_by(SellingPrice.valid_from.desc())
            )
        )
