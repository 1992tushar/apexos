"""Suppliers pages: list + inline create + detail with evaluations."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import Actor, get_current_actor
from app.modules.config.service import ConfigService
from app.modules.suppliers.schemas import SupplierCreate, SupplierEvaluationCreate
from app.modules.suppliers.service import SupplierService, VendorEvaluationService
from app.web.core import redirect, render

router = APIRouter()


@router.get("/suppliers")
def list_suppliers(request: Request, db: Session = Depends(get_db)):
    rows, total = SupplierService(db).list(search=None, page=1, page_size=200)
    types = ConfigService(db).supplier_types()
    return render(
        request,
        "suppliers/list.html",
        suppliers=rows,
        total=total,
        types=types,
    )


@router.post("/suppliers")
def create_supplier(
    request: Request,
    name: str = Form(...),
    supplier_type_id: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    gstin: str = Form(""),
    address: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        payload = SupplierCreate(
            name=name,
            supplier_type_id=uuid.UUID(supplier_type_id),
            phone=phone or None,
            email=email or None,
            gstin=gstin or None,
            address=address or None,
            city=city or None,
            state=state or None,
        )
        sup = SupplierService(db).create(payload, actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/suppliers", err=getattr(exc, "message", "Could not create supplier"))
    return redirect(f"/suppliers/{sup.id}", ok="Supplier created")


@router.get("/suppliers/{supplier_id}")
def supplier_detail(request: Request, supplier_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        sup = SupplierService(db).get(supplier_id)
    except AppError as exc:
        return render(
            request, "error.html", status_code=exc.status_code, code="Not found", message=exc.message
        )
    evals = VendorEvaluationService(db).evaluations(supplier_id)
    return render(request, "suppliers/detail.html", sup=sup, evals=evals)


@router.post("/supplier-evaluations")
def evaluate_supplier(
    request: Request,
    supplier_id: str = Form(...),
    quality_score: int = Form(...),
    price_score: int = Form(...),
    reliability_score: int = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        payload = SupplierEvaluationCreate(
            supplier_id=uuid.UUID(supplier_id),
            quality_score=quality_score,
            price_score=price_score,
            reliability_score=reliability_score,
            notes=notes or None,
        )
        VendorEvaluationService(db).score(payload, actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect(f"/suppliers/{supplier_id}", err=getattr(exc, "message", "Could not add evaluation"))
    return redirect(f"/suppliers/{supplier_id}", ok="Evaluation added")
