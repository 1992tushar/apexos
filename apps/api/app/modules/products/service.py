"""Product service — CRUD + read projection (names, prices, stock)."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.db.duplicates import ensure_unique
from app.db.listing import ListParams, query_page
from app.db.references import ensure_unreferenced
from app.db.soft_delete import soft_delete
from app.modules.activity.history import CHANGES_KEY, field_changes
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit
from app.modules.inventory.service import InventoryService
from app.modules.pricing.models import PurchasePrice, SellingPrice
from app.modules.pricing.service import PricingService
from app.modules.products.listing import PRODUCT_LIST, PRODUCT_STATUSES_ALLOWED
from app.modules.products.models import Product
from app.modules.products.repository import ProductRepository
from app.modules.products.schemas import ProductCreate, ProductRead


class ProductService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProductRepository(db)
        self.pricing = PricingService(db)
        self.inventory = InventoryService(db)
        self.activity = ActivityService(db)

    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    def _to_read(self, product: Product) -> ProductRead:
        names = self.repo.names(product)
        return ProductRead(
            id=product.id,
            sku_code=product.sku_code,
            name=product.name,
            category_id=product.category_id,
            brand_id=product.brand_id,
            uom_id=product.uom_id,
            procurement_model_id=product.procurement_model_id,
            launch_phase=product.launch_phase,
            specification=product.specification,
            status=product.status,
            selling_price_minor=self.pricing.resolve_selling_minor(product.id),
            purchase_price_minor=self.pricing.latest_purchase_minor(product.id),
            stock_on_hand=self.inventory.on_hand(product.id),
            **names,
        )

    def to_read_many(self, rows: Sequence[Product]) -> list[ProductRead]:
        """The projector the list page passes to `view_from_request(project=...)`."""
        return [self._to_read(p) for p in rows]

    def list(
        self, *, search: str | None, category_id: uuid.UUID | None, page: int, page_size: int
    ):
        """One page of products, through the one query helper (R2.4).

        `page_size` overrides the spec's so a caller that wants everything (a form's
        product dropdown) still gets it; the filters, the sort and the soft-delete
        scope all come from `PRODUCT_LIST`.
        """
        params = ListParams(
            q=search or "",
            filters={"category": str(category_id)} if category_id else {},
            page=page,
        )
        result = query_page(self.db, replace(PRODUCT_LIST, page_size=page_size), params)
        return self.to_read_many(result.rows), result.total

    def get(self, product_id: uuid.UUID) -> ProductRead:
        product = self.repo.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return self._to_read(product)

    def delete(self, product_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        """Soft-delete a product (R1.2).

        Order lines, invoice lines and its stock movements keep rendering — the
        row stays addressable, it just leaves the catalogue (R1.7). Stock history
        is never rewritten; the ledger is append-only (G4).
        """
        product = self.repo.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        # An *open* order still reads this product at receipt or dispatch; a closed one
        # snapshotted what it needed. The refusal names the documents (R3.7).
        ensure_unreferenced(self.db, product, action="delete", label="Product")
        soft_delete(self.db, product, actor_id=actor_id, label="Product")

    def set_status(self, product_id: uuid.UUID, status: str, *, actor_id: uuid.UUID | None):
        """Move a product through Active / Draft / Discontinued (R3.9).

        Retiring one that open work still reads is refused and says which documents are
        in the way — the same guard as deletion, because hiding a product from every
        picker breaks an open order just as thoroughly (R3.7).
        """
        if status not in PRODUCT_STATUSES_ALLOWED:
            raise ValidationError(
                f"Unknown product status '{status}'. "
                f"Use one of: {', '.join(sorted(PRODUCT_STATUSES_ALLOWED))}."
            )
        product = self.repo.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        if product.status == status:
            return self._to_read(product)
        if status != "active":
            ensure_unreferenced(
                self.db, product, action=f"mark {status}", label="Product"
            )
        # Captured before the assignment — `field_changes` reads the row's current value.
        changes = field_changes(product, {"status": status})
        before = product.status
        product.status = status
        product.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="status_changed",
            entity_type="product",
            entity_id=product.id,
            summary=f"Product {product.name} moved from {before} to {status}",
            data={CHANGES_KEY: changes} if changes else None,
        )
        return self._to_read(product)

    def create(self, payload: ProductCreate, *, actor_id: uuid.UUID | None) -> ProductRead:
        sku = payload.sku_code or f"SKU-{self.repo.count_ever() + 1:05d}"
        # The one duplicate check (R2.9) — natural keys are configured in
        # app.db.duplicates, not spelled out here.
        ensure_unique(
            self.db,
            Product,
            {
                "sku_code": sku,
                "name": payload.name,
                "specification": payload.specification,
                "brand_id": payload.brand_id,
            },
        )
        product = Product(
            sku_code=sku,
            name=payload.name,
            category_id=payload.category_id,
            brand_id=payload.brand_id,
            uom_id=payload.uom_id,
            procurement_model_id=payload.procurement_model_id,
            default_tax_rate_id=payload.default_tax_rate_id,
            specification=payload.specification,
            launch_phase=payload.launch_phase,
            reorder_level=payload.reorder_level,
            status="active",
            business_unit_id=payload.business_unit_id or self._default_bu(),
            created_by=actor_id,
        )
        self.repo.add(product)

        now = datetime.now(UTC)
        if payload.selling_price_minor is not None:
            self.db.add(
                SellingPrice(
                    product_id=product.id,
                    price_minor=payload.selling_price_minor,
                    valid_from=now,
                    created_by=actor_id,
                )
            )
        if payload.purchase_price_minor is not None:
            self.db.add(
                PurchasePrice(
                    product_id=product.id,
                    price_minor=payload.purchase_price_minor,
                    valid_from=now,
                    created_by=actor_id,
                )
            )
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="product",
            entity_id=product.id,
            summary=f"Product {product.name} ({product.sku_code}) created",
        )
        return self._to_read(product)
