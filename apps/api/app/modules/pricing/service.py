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
    """Gross-profit (GP) helper: selling − buying. Central KPI (Foundation §4).

    **`gp` cannot tell "cost is zero" from "cost is unknown", and `gp_costed` is the one
    place that can.** A product with no recorded purchase price makes `gp` return the full
    selling value, i.e. a 100% margin — the single most misleading number this codebase can
    produce, and a G11 violation wherever it reaches a screen.

    Part 10's R13.1 audit found three consumers of `gp` and only one applying that check.
    `MarginAnalysisService` excluded and counted uncosted lines. The other two did not:

    * **`CustomerHealthService.profitability` really was wrong** — an uncosted line was scored
      toward a 100% margin, worth up to 30 of the score's 100 points for a number nobody
      measured.
    * **`CashFlowService._cogs` was right by coincidence.** An uncosted line's `gp` equals its
      own subtotal, so `subtotal − gross` contributed zero to cost either way. Measured: COGS
      is unchanged. It is routed through `gp_costed` so the answer no longer depends on that
      coincidence, and so the DIO panel can say how many lines it could not cost.

    The rule had been written down (in a repository docstring) and implemented once. R13.2
    says one engine, so it is now `gp_costed`, and all three callers read it.

    **New code should call `gp_costed`, not `gp`.** `gp` remains because it is the honest
    primitive — selling minus buying, no policy — and because R11.6's "margin is
    MarginService.gp, never an inventory valuation layer" is asserted against it.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.pricing = PricingService(db)

    def gp(self, line) -> int:
        """GP in minor units for one order/PO line, from its stored unit price and
        the product's current buy price × qty. Accepts any object exposing
        `product_id`, `qty`, and `unit_price_minor`.

        **Reads a missing purchase price as zero**, so a product nothing has ever been
        bought for reports its whole selling value as profit. Use `gp_costed` unless you
        genuinely want that. See the class docstring.
        """
        from decimal import Decimal

        buy = self.pricing.latest_purchase_minor(line.product_id) or 0
        unit_gp = int(line.unit_price_minor) - int(buy)
        return int((Decimal(unit_gp) * Decimal(line.qty)).quantize(Decimal("1")))

    def purchase_price_map(self) -> dict[uuid.UUID, int]:
        """`{product_id: current buy price}` in ONE query. Absence means cost UNKNOWN.

        Hoist this out of any loop over lines and pass it to `gp_costed`: without it that
        method costs one query per line, which is the shape of defect Part 9 found in
        `InventoryHealthService.low_stock` (274 queries for one page).
        """
        return self.pricing.repo.purchase_prices_by_product()

    def gp_costed(self, line, *, buy_prices: dict[uuid.UUID, int] | None = None) -> int | None:
        """GP, or **None when this line's product has no recorded purchase price**.

        THE one place that makes the distinction `gp` cannot. `None` means "we do not know
        what this cost", which is not the same fact as "it cost nothing", and every caller
        deriving a margin, a cost of goods or a profitability score owes its screen that
        difference (G11, R13.10, R13.11).

        Pass `buy_prices` from `purchase_price_map()` when looping; omit it for a one-off.
        """
        prices = buy_prices if buy_prices is not None else self.purchase_price_map()
        if line.product_id not in prices:
            return None
        return self.gp(line)
