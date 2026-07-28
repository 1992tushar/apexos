"""Supplier services — CRUD + vendor evaluation, emits activity (mirrors Customers).

`SupplierService` owns supplier create/update; `VendorEvaluationService.score`
appends an immutable scorecard row and records the domain event (D10).
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.duplicates import ensure_unique
from app.db.listing import ListParams, query_page
from app.db.references import ensure_unreferenced
from app.db.soft_delete import soft_delete
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit
from app.modules.products.models import Product
from app.modules.suppliers.listing import SUPPLIER_LIST
from app.modules.suppliers.models import ProductSupplier, Supplier, SupplierEvaluation
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.schemas import (
    ProductSupplierRead,
    ProductSupplierUpsert,
    SupplierCreate,
    SupplierEvaluationCreate,
    SupplierEvaluationRead,
    SupplierRead,
    SupplierUpdate,
)
from app.modules.suppliers.vendor import VendorIntelService


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SupplierRepository(db)
        self.activity = ActivityService(db)

    def _default_bu(self) -> uuid.UUID:
        bu = self.db.scalar(
            select(BusinessUnit.id).where(BusinessUnit.deleted_at.is_(None)).limit(1)
        )
        if bu is None:
            raise NotFoundError("No business unit configured; run the seed first.")
        return bu

    def _to_read(self, supplier: Supplier) -> SupplierRead:
        return SupplierRead(
            id=supplier.id,
            code=supplier.code,
            name=supplier.name,
            supplier_type_id=supplier.supplier_type_id,
            supplier_type_name=self.repo.supplier_type_name(supplier.supplier_type_id),
            phone=supplier.phone,
            email=supplier.email,
            gstin=supplier.gstin,
            address=supplier.address,
            city=supplier.city,
            state=supplier.state,
            outstanding_minor=self.repo.outstanding_minor(supplier.id),
            latest_score=self.repo.latest_score(supplier.id),
            evaluation_count=self.repo.evaluation_count(supplier.id),
            status=supplier.status,
            created_at=supplier.created_at,
        )

    def to_read_many(self, rows: Sequence[Supplier]) -> list[SupplierRead]:
        """The projector the list page passes to `view_from_request(project=...)`."""
        return [self._to_read(s) for s in rows]

    def list(self, *, search: str | None, page: int, page_size: int):
        """One page of suppliers through the one query helper (R2.4)."""
        result = query_page(
            self.db,
            replace(SUPPLIER_LIST, page_size=page_size),
            ListParams(q=search or "", page=page),
        )
        return self.to_read_many(result.rows), result.total

    def get(self, supplier_id: uuid.UUID) -> SupplierRead:
        supplier = self.repo.get(supplier_id)
        if supplier is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        return self._to_read(supplier)

    def delete(self, supplier_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        """Soft-delete a supplier (R1.2).

        Purchase orders, bills and past evaluations keep rendering — the row stays
        addressable, it just leaves the lists and lookups (R1.7).
        """
        supplier = self.repo.get(supplier_id)
        if supplier is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        # An open purchase order still reads this supplier; a closed one snapshotted
        # what it needed (R3.7).
        ensure_unreferenced(self.db, supplier, action="delete", label="Supplier")
        soft_delete(self.db, supplier, actor_id=actor_id, label="Supplier")

    def create(self, payload: SupplierCreate, *, actor_id: uuid.UUID | None) -> SupplierRead:
        code = payload.code or self.repo.next_code()
        # The one duplicate check (R2.9, R3.8) — keys live in `app.db.duplicates`.
        ensure_unique(
            self.db, Supplier, {"code": code, "name": payload.name, "city": payload.city}
        )
        supplier = Supplier(
            code=code,
            name=payload.name,
            supplier_type_id=payload.supplier_type_id,
            phone=payload.phone,
            email=payload.email,
            gstin=payload.gstin,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            status="active",
            business_unit_id=payload.business_unit_id or self._default_bu(),
            created_by=actor_id,
        )
        self.repo.add(supplier)
        self.activity.log(
            actor_id=actor_id,
            verb="created",
            entity_type="supplier",
            entity_id=supplier.id,
            summary=f"Supplier {supplier.name} ({supplier.code}) created",
        )
        return self._to_read(supplier)

    def update(
        self, supplier_id: uuid.UUID, payload: SupplierUpdate, *, actor_id: uuid.UUID | None
    ) -> SupplierRead:
        supplier = self.repo.get(supplier_id)
        if supplier is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        data = payload.model_dump(exclude_unset=True)
        for field in ("name", "supplier_type_id", "phone", "email", "gstin",
                      "address", "city", "state", "status"):
            if field in data:
                setattr(supplier, field, data[field])
        supplier.updated_by = actor_id
        self.db.flush()
        self.activity.log(
            actor_id=actor_id,
            verb="updated",
            entity_type="supplier",
            entity_id=supplier.id,
            summary=f"Supplier {supplier.name} updated",
        )
        return self._to_read(supplier)


class ProductSupplierService:
    """The product↔supplier mapping (R5.1) and its MOQ (R5.5).

    The writer half of Part 4. `VendorIntelService` is the read half and stays
    read-only (G15) — score, lead time and on-time rate are never written here.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.activity = ActivityService(db)

    def _get(self, link_id: uuid.UUID) -> ProductSupplier:
        link = self.db.scalar(
            select(ProductSupplier).where(
                ProductSupplier.id == link_id, ProductSupplier.deleted_at.is_(None)
            )
        )
        if link is None:
            raise NotFoundError(f"Product-supplier link {link_id} not found")
        return link

    def links_for_product(self, product_id: uuid.UUID) -> list[ProductSupplier]:
        """Preferred first, then by supplier name — the order the screen shows."""
        return list(
            self.db.scalars(
                select(ProductSupplier)
                .join(Supplier, Supplier.id == ProductSupplier.supplier_id)
                .where(
                    ProductSupplier.product_id == product_id,
                    ProductSupplier.deleted_at.is_(None),
                )
                .order_by(ProductSupplier.is_preferred.desc(), Supplier.name.asc())
            )
        )

    def list_for_product(self, product_id: uuid.UUID) -> list[ProductSupplierRead]:
        """The vendor comparison for one product (R5.1, R5.12).

        Each row carries the supplier's *rendered* intelligence — "unknown" where
        there is no history, never a stand-in number (G11/R5.11).
        """
        intel = VendorIntelService(self.db)
        out: list[ProductSupplierRead] = []
        for link in self.links_for_product(product_id):
            supplier = self.db.get(Supplier, link.supplier_id)
            out.append(
                ProductSupplierRead(
                    id=link.id,
                    product_id=link.product_id,
                    supplier_id=link.supplier_id,
                    supplier_code=supplier.code if supplier else None,
                    supplier_name=supplier.name if supplier else None,
                    is_preferred=link.is_preferred,
                    moq=link.moq,
                    note=link.note,
                    score=intel.score(link.supplier_id).display,
                    lead_time=intel.lead_time(link.supplier_id).display,
                    on_time_rate=intel.on_time_rate(link.supplier_id).display,
                )
            )
        return out

    def moq(self, product_id: uuid.UUID, supplier_id: uuid.UUID) -> Decimal | None:
        """The agreed minimum for one product+supplier — what R4.5's grid shows (R5.5)."""
        return self.db.scalar(
            select(ProductSupplier.moq).where(
                ProductSupplier.product_id == product_id,
                ProductSupplier.supplier_id == supplier_id,
                ProductSupplier.deleted_at.is_(None),
            )
        )

    def preferred_supplier_id(self, product_id: uuid.UUID) -> uuid.UUID | None:
        """Who to buy this from by default — the recommendation engine reads this."""
        return self.db.scalar(
            select(ProductSupplier.supplier_id).where(
                ProductSupplier.product_id == product_id,
                ProductSupplier.is_preferred.is_(True),
                ProductSupplier.deleted_at.is_(None),
            )
        )

    def upsert(
        self, payload: ProductSupplierUpsert, *, actor_id: uuid.UUID | None
    ) -> ProductSupplierRead:
        """Create or amend one link. Idempotent on (product, supplier)."""
        existing = self.db.scalar(
            select(ProductSupplier).where(
                ProductSupplier.product_id == payload.product_id,
                ProductSupplier.supplier_id == payload.supplier_id,
                ProductSupplier.deleted_at.is_(None),
            )
        )
        product = self.db.get(Product, payload.product_id)
        supplier = self.db.get(Supplier, payload.supplier_id)
        if product is None:
            raise NotFoundError(f"Product {payload.product_id} not found")
        if supplier is None:
            raise NotFoundError(f"Supplier {payload.supplier_id} not found")

        if existing is None:
            # The one duplicate check (R2.9/R3.8) — the key is in app.db.duplicates.
            ensure_unique(
                self.db,
                ProductSupplier,
                {"product_id": payload.product_id, "supplier_id": payload.supplier_id},
            )
            link = ProductSupplier(
                product_id=payload.product_id,
                supplier_id=payload.supplier_id,
                is_preferred=False,
                moq=payload.moq,
                note=payload.note,
                created_by=actor_id,
            )
            self.db.add(link)
            self.db.flush()
            verb, phrase = "linked", "can be bought from"
        else:
            link = existing
            link.moq = payload.moq
            link.note = payload.note
            link.updated_by = actor_id
            self.db.flush()
            verb, phrase = "updated", "supply terms updated for"

        # Exactly one activity row for the whole verb (G5) — `_set_preferred` below
        # is called inline and deliberately does NOT log a second one.
        if payload.is_preferred:
            self._set_preferred(link)
        self.activity.log(
            actor_id=actor_id,
            verb=verb,
            entity_type="product_supplier",
            entity_id=link.id,
            summary=f"{product.name} {phrase} {supplier.name}",
            data={"moq": str(link.moq) if link.moq is not None else None,
                  "is_preferred": link.is_preferred},
        )
        return self.list_one(link.id)

    def list_one(self, link_id: uuid.UUID) -> ProductSupplierRead:
        link = self._get(link_id)
        rows = [r for r in self.list_for_product(link.product_id) if r.id == link_id]
        return rows[0]

    def _set_preferred(self, link: ProductSupplier) -> None:
        """One preferred supplier per product — demote the others.

        Not a logged verb of its own; the caller owns the single activity row (G5).
        """
        others = self.db.scalars(
            select(ProductSupplier).where(
                ProductSupplier.product_id == link.product_id,
                ProductSupplier.id != link.id,
                ProductSupplier.is_preferred.is_(True),
                ProductSupplier.deleted_at.is_(None),
            )
        )
        for other in others:
            other.is_preferred = False
        link.is_preferred = True
        self.db.flush()

    def set_preferred(
        self, link_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ProductSupplierRead:
        """Make this supplier the preferred one for its product (R5.1)."""
        link = self._get(link_id)
        self._set_preferred(link)
        product = self.db.get(Product, link.product_id)
        supplier = self.db.get(Supplier, link.supplier_id)
        self.activity.log(
            actor_id=actor_id,
            verb="preferred",
            entity_type="product_supplier",
            entity_id=link.id,
            summary=(
                f"{supplier.name if supplier else 'Supplier'} set as preferred for "
                f"{product.name if product else 'product'}"
            ),
        )
        return self.list_one(link.id)

    def delete(self, link_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        """Unlink a supplier from a product. The one soft-delete helper (R1.1)."""
        link = self._get(link_id)
        soft_delete(self.db, link, actor_id=actor_id, label="Product-supplier link")


class VendorEvaluationService:
    """Vendor scorecard writer. `overall_score` is the rounded mean of the three
    sub-scores; the row is append-only (history kept)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SupplierRepository(db)
        self.activity = ActivityService(db)

    def evaluations(self, supplier_id: uuid.UUID) -> list[SupplierEvaluationRead]:
        return [SupplierEvaluationRead.model_validate(e) for e in self.repo.evaluations(supplier_id)]

    def score(
        self, payload: SupplierEvaluationCreate, *, actor_id: uuid.UUID | None
    ) -> SupplierEvaluationRead:
        supplier = self.repo.get(payload.supplier_id)
        if supplier is None:
            raise NotFoundError(f"Supplier {payload.supplier_id} not found")
        overall = round(
            (payload.quality_score + payload.price_score + payload.reliability_score) / 3
        )
        evaluation = SupplierEvaluation(
            supplier_id=payload.supplier_id,
            quality_score=payload.quality_score,
            price_score=payload.price_score,
            reliability_score=payload.reliability_score,
            overall_score=overall,
            notes=payload.notes,
            created_by=actor_id,
        )
        self.repo.add_evaluation(evaluation)
        self.activity.log(
            actor_id=actor_id,
            verb="evaluated",
            entity_type="supplier",
            entity_id=supplier.id,
            summary=f"Supplier {supplier.name} evaluated (overall {overall}/5)",
            data={"overall_score": overall},
        )
        return SupplierEvaluationRead.model_validate(evaluation)
