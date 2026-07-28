"""Product repository — persistence + display-name lookups."""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.config.models import Brand, Category, ProcurementModel, Uom
from app.modules.products.models import Product


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, product: Product) -> Product:
        self.db.add(product)
        self.db.flush()
        return product

    def get(self, product_id: uuid.UUID) -> Product | None:
        return self.db.scalar(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )

    def count_all(self) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Product).where(Product.deleted_at.is_(None))
        ) or 0

    def count_ever(self) -> int:
        """Rows ever created, soft-deleted ones included.

        The basis for a generated SKU. `count_all()` would be wrong here: it
        excludes deleted rows, so after one deletion the next generated code is one
        a deleted product still holds — `sku_code` is UNIQUE across every row in
        the table, deleted or not.
        """
        return self.db.scalar(select(func.count()).select_from(Product)) or 0

    def search(
        self, *, search: str | None, category_id: uuid.UUID | None, page: int, page_size: int
    ) -> tuple[list[Product], int]:
        base = select(Product).where(Product.deleted_at.is_(None))
        if category_id is not None:
            base = base.where(Product.category_id == category_id)
        if search:
            like = f"%{search.lower()}%"
            base = base.where(
                or_(
                    func.lower(Product.name).like(like),
                    func.lower(Product.sku_code).like(like),
                )
            )
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = list(
            self.db.scalars(
                base.order_by(Product.sku_code)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return rows, total

    def names(self, product: Product) -> dict[str, str | None]:
        return {
            "category_name": self.db.scalar(
                select(Category.name).where(Category.id == product.category_id)
            ),
            "brand_name": self.db.scalar(
                select(Brand.name).where(Brand.id == product.brand_id)
            ),
            "uom_code": self.db.scalar(select(Uom.code).where(Uom.id == product.uom_id)),
            "procurement_model_name": (
                self.db.scalar(
                    select(ProcurementModel.name).where(
                        ProcurementModel.id == product.procurement_model_id
                    )
                )
                if product.procurement_model_id
                else None
            ),
        }
