"""Suppliers pages: list + inline create + detail with evaluations and vendor
intelligence.

The detail page's score, lead time and on-time rate are read from
`VendorIntelService` — measured, never stored (R5.2–R5.4, G7) — and rendered by
the one `explain_panel` macro so each carries its formula, window and source
records (G11, R5.12).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.activity.service import ActivityService
from app.modules.config.service import ConfigService
from app.modules.suppliers.listing import SUPPLIER_LIST
from app.modules.suppliers.schemas import SupplierCreate, SupplierEvaluationCreate
from app.modules.suppliers.service import SupplierService, VendorEvaluationService
from app.modules.suppliers.vendor import VendorIntelService
from app.web.core import form_action, render
from app.web.listing import csv_response_from_request, view_from_request, wants_csv
from app.web.security import require_web_permission

router = APIRouter()


@router.get("/suppliers")
def list_suppliers(request: Request, db: Session = Depends(get_db)):
    project = SupplierService(db).to_read_many
    if wants_csv(request):
        return csv_response_from_request(request, db, SUPPLIER_LIST, project=project)
    return render(
        request,
        "suppliers/list.html",
        view=view_from_request(request, db, SUPPLIER_LIST, project=project),
        types=ConfigService(db).supplier_types(),
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
    actor: Actor = Depends(require_web_permission("supplier.create")),
):
    def work():
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
        return SupplierService(db).create(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/suppliers",
        success=lambda sup: (f"/suppliers/{sup.id}", "Supplier created"),
        err="Could not create supplier",
    )


@router.get("/suppliers/{supplier_id}")
def supplier_detail(request: Request, supplier_id: uuid.UUID, db: Session = Depends(get_db)):
    # A missing supplier raises NotFoundError → the web error handler renders error.html.
    sup = SupplierService(db).get(supplier_id)
    intel = VendorIntelService(db)
    return render(
        request,
        "suppliers/detail.html",
        sup=sup,
        evals=VendorEvaluationService(db).evaluations(supplier_id),
        history=ActivityService(db).history("supplier", supplier_id),
        # R5.12 — the measured intelligence, each one an `Explained` (G11). A pure
        # read: rendering this page writes nothing (G15).
        score=intel.score(supplier_id),
        lead_time=intel.lead_time(supplier_id),
        on_time_rate=intel.on_time_rate(supplier_id),
        receipts=intel.receipts(supplier_id),
    )


@router.post("/suppliers/{supplier_id}/delete")
def delete_supplier(
    request: Request,
    supplier_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("supplier.delete")),
):
    return form_action(
        db, lambda: SupplierService(db).delete(supplier_id, actor_id=actor.id),
        back=f"/suppliers/{supplier_id}",
        success=("/suppliers", "Supplier deleted"),
        err="Could not delete supplier",
    )


@router.post("/supplier-evaluations")
def evaluate_supplier(
    request: Request,
    supplier_id: str = Form(...),
    quality_score: int = Form(...),
    price_score: int = Form(...),
    reliability_score: int = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("supplier_evaluation.create")),
):
    def work():
        payload = SupplierEvaluationCreate(
            supplier_id=uuid.UUID(supplier_id),
            quality_score=quality_score,
            price_score=price_score,
            reliability_score=reliability_score,
            notes=notes or None,
        )
        return VendorEvaluationService(db).score(payload, actor_id=actor.id)

    return form_action(
        db, work, back=f"/suppliers/{supplier_id}",
        success=(f"/suppliers/{supplier_id}", "Evaluation added"),
        err="Could not add evaluation",
    )
