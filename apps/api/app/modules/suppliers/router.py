"""Suppliers router — thin; delegates to SupplierService / VendorEvaluationService."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor, require_permission
from app.modules.suppliers.schemas import (
    SupplierCreate,
    SupplierEvaluationCreate,
    SupplierEvaluationRead,
    SupplierPage,
    SupplierRead,
    SupplierUpdate,
)
from app.modules.suppliers.service import SupplierService, VendorEvaluationService

router = APIRouter(tags=["suppliers"])


@router.get("/suppliers", response_model=SupplierPage)
def list_suppliers(
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = SupplierService(db).list(search=search, page=page, page_size=page_size)
    return SupplierPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/suppliers", response_model=SupplierRead, status_code=201)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("supplier.create")),
):
    return SupplierService(db).create(payload, actor_id=actor.id)


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: uuid.UUID, db: Session = Depends(get_db)):
    return SupplierService(db).get(supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("supplier.update")),
):
    return SupplierService(db).update(supplier_id, payload, actor_id=actor.id)


@router.get(
    "/suppliers/{supplier_id}/evaluations", response_model=list[SupplierEvaluationRead]
)
def list_supplier_evaluations(supplier_id: uuid.UUID, db: Session = Depends(get_db)):
    return VendorEvaluationService(db).evaluations(supplier_id)


@router.post("/supplier-evaluations", response_model=SupplierEvaluationRead, status_code=201)
def score_supplier(
    payload: SupplierEvaluationCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_permission("supplier_evaluation.create")),
):
    return VendorEvaluationService(db).score(payload, actor_id=actor.id)
