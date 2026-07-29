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

    def purchase_prices_by_product(self) -> dict[uuid.UUID, int]:
        """`{product_id: current buy price}` for every product that has one — ONE query.

        **Absence means the cost is UNKNOWN**, and that distinction is the whole reason this
        map exists: `MarginService.gp` reads a missing purchase price as zero and therefore
        reports a 100% margin. Anything deriving gross profit must consult this before
        trusting `gp` — which is what `MarginService.gp_costed` does, so callers should use
        that rather than this map directly.

        It lives here because `pricing` owns `PurchasePrice`. Part 8 built the same query on
        `FinanceRepository`, where finance was the only consumer; Part 10's R13.1 audit found
        three consumers in three modules, so the query moved to the module that owns the
        table and `FinanceRepository.purchase_prices_by_product` now delegates here.
        """
        rows = self.db.execute(
            select(PurchasePrice.product_id, PurchasePrice.price_minor)
            .where(
                PurchasePrice.valid_to.is_(None),
                PurchasePrice.deleted_at.is_(None),
            )
            .order_by(PurchasePrice.product_id, PurchasePrice.valid_from.desc())
        ).all()
        out: dict[uuid.UUID, int] = {}
        for product_id, price in rows:
            out.setdefault(product_id, int(price))
        return out

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
