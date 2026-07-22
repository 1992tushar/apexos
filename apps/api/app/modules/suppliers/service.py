"""Supplier services — CRUD + vendor evaluation, emits activity (mirrors Customers).

`SupplierService` owns supplier create/update; `VendorEvaluationService.score`
appends an immutable scorecard row and records the domain event (D10).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.activity.service import ActivityService
from app.modules.config.models import BusinessUnit
from app.modules.suppliers.models import Supplier, SupplierEvaluation
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.schemas import (
    SupplierCreate,
    SupplierEvaluationCreate,
    SupplierEvaluationRead,
    SupplierRead,
    SupplierUpdate,
)


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

    def list(self, *, search: str | None, page: int, page_size: int):
        rows, total = self.repo.search(search=search, page=page, page_size=page_size)
        return [self._to_read(s) for s in rows], total

    def get(self, supplier_id: uuid.UUID) -> SupplierRead:
        supplier = self.repo.get(supplier_id)
        if supplier is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        return self._to_read(supplier)

    def create(self, payload: SupplierCreate, *, actor_id: uuid.UUID | None) -> SupplierRead:
        code = payload.code or self.repo.next_code()
        if self.db.scalar(select(Supplier.id).where(Supplier.code == code)):
            raise ConflictError(f"Supplier code {code} already exists")
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
