"""Fast order entry: what the entry screen needs to be quick (R9.12–R9.14).

**Reads only.** Three helpers, each deliberately BULK — the entry form shows ~300 products,
so a per-product query would be 300 round trips to render one page, which is the thing
`CODEBASE-MAP` warns about under "a `select()` per row in a projector".

`picker_hints` is the one that earns its keep: it puts the price and **how much is available**
beside every SKU in the picker, so the founder is not looking stock up in another tab while
taking an order. Available, not on-hand — now that confirming reserves (R9.8), the two differ,
and offering on-hand would promise stock already committed to somebody else.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import minor_to_text, qty_text
from app.modules.inventory.service import InventoryService
from app.modules.pricing.models import SellingPrice
from app.modules.sales.models import SalesOrder, SalesOrderLine


class FastEntryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def available_by_product(self) -> dict[uuid.UUID, Decimal]:
        """Available quantity per product, summed across warehouses — TWO queries.

        `InventoryService.states()` already does the grouped work; this just folds the
        per-warehouse rows together, because an order form asks "can I sell this at all",
        not "from which shelf".
        """
        totals: dict[uuid.UUID, Decimal] = {}
        for row in InventoryService(self.db).states():
            totals[row.product_id] = totals.get(row.product_id, Decimal(0)) + row.available
        return totals

    def list_price_by_product(self) -> dict[uuid.UUID, int]:
        """The current list price per product — ONE query.

        Takes the newest still-valid row that is not customer-specific: the picker shows a
        list price, and a customer-specific override is resolved properly by
        `PricingService.resolve_selling_minor` when the line is actually priced. Showing the
        general price here and pricing at a customer rate is not a contradiction — the hint
        is a guide, the resolver is the authority.
        """
        rows = self.db.execute(
            select(SellingPrice.product_id, SellingPrice.price_minor, SellingPrice.valid_from)
            .where(
                SellingPrice.deleted_at.is_(None),
                SellingPrice.customer_id.is_(None),
                SellingPrice.valid_to.is_(None),
            )
            .order_by(SellingPrice.product_id, SellingPrice.valid_from.desc())
        ).all()
        prices: dict[uuid.UUID, int] = {}
        for product_id, price_minor, _valid_from in rows:
            # Ordered newest-first per product, so the first one wins.
            prices.setdefault(product_id, int(price_minor))
        return prices

    def picker_hints(self, products) -> dict[str, str]:
        """`sku_code -> "₹price · N available"`, for the datalist labels (R9.12).

        A product with no price says so rather than showing a blank, and one with nothing
        available says "none available" — the founder can still quote it, but they find out
        while typing instead of at confirm time when the reservation fails.
        """
        available = self.available_by_product()
        prices = self.list_price_by_product()
        hints: dict[str, str] = {}
        for product in products:
            parts: list[str] = []
            price = prices.get(product.id)
            parts.append(minor_to_text(price) if price is not None else "no price")
            qty = available.get(product.id, Decimal(0))
            parts.append(
                f"{qty_text(qty)} available" if qty > 0 else "none available"
            )
            hints[product.sku_code] = " · ".join(parts)
        return hints

    def last_order_lines(self, customer_id: uuid.UUID) -> list[tuple[str, Decimal, int]]:
        """(sku_code, qty, unit_price_minor) from this customer's most recent order.

        R9.12's reorder-from-last-order. TWO queries, not one per line. Excludes cancelled
        orders: repeating an order that was called off is not what "last order" means.

        Ordered by `order_date` then `id`, and the second key matters — several seeded orders
        share a date, and `uuid7` cannot break a same-millisecond tie, so without it "the
        last order" could differ between page loads.
        """
        from app.modules.products.models import Product

        order = self.db.scalar(
            select(SalesOrder)
            .where(
                SalesOrder.customer_id == customer_id,
                SalesOrder.deleted_at.is_(None),
                SalesOrder.status != "cancelled",
            )
            .order_by(SalesOrder.order_date.desc(), SalesOrder.id.desc())
            .limit(1)
        )
        if order is None:
            return []

        rows = self.db.execute(
            select(Product.sku_code, SalesOrderLine.qty, SalesOrderLine.unit_price_minor)
            .join(Product, Product.id == SalesOrderLine.product_id)
            .where(
                SalesOrderLine.sales_order_id == order.id,
                SalesOrderLine.deleted_at.is_(None),
            )
            .order_by(SalesOrderLine.line_no)
        ).all()
        return [(sku, Decimal(qty), int(price)) for sku, qty, price in rows]

    def customers_with_history(self) -> set[uuid.UUID]:
        """Which customers have an order to repeat — one query, so the form can show the
        repeat action only where it would do something."""
        rows = self.db.execute(
            select(SalesOrder.customer_id)
            .where(SalesOrder.deleted_at.is_(None), SalesOrder.status != "cancelled")
            .distinct()
        ).all()
        return {row[0] for row in rows}
