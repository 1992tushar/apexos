"""Leads & pipeline pages: leads list + create + convert, and opportunity
pipeline grouped by stage with an advance action."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import Actor, get_current_actor
from app.modules.config.service import ConfigService
from app.modules.crm.schemas import LeadConvert, LeadCreate, OpportunityAdvance
from app.modules.crm.service import CrmService
from app.web.core import redirect, render

router = APIRouter()


@router.get("/leads")
def list_leads(request: Request, db: Session = Depends(get_db)):
    svc = CrmService(db)
    leads, total = svc.leads(status=None, page=1, page_size=200)
    stages = svc.stages()
    opps = svc.opportunities()
    customer_types = ConfigService(db).customer_types()

    groups = []
    for stage in stages:
        opps_in = [o for o in opps if o.pipeline_stage_id == stage.id]
        groups.append(
            {
                "stage": stage,
                "opps": opps_in,
                "count": len(opps_in),
                "total_value_minor": sum(o.estimated_value_minor for o in opps_in),
            }
        )

    return render(
        request,
        "leads/index.html",
        leads=leads,
        total=total,
        stages=stages,
        groups=groups,
        customer_types=customer_types,
    )


@router.post("/leads")
def create_lead(
    request: Request,
    company_name: str = Form(...),
    contact_name: str = Form(""),
    city: str = Form(""),
    source: str = Form(""),
    customer_type_id: str = Form(""),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        payload = LeadCreate(
            company_name=company_name,
            contact_name=contact_name or None,
            city=city or None,
            source=source or None,
            customer_type_id=uuid.UUID(customer_type_id) if customer_type_id else None,
        )
        CrmService(db).create_lead(payload, actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/leads", err=getattr(exc, "message", "Could not create lead"))
    return redirect("/leads", ok="Lead created")


@router.post("/leads/{lead_id}/convert")
def convert_lead(
    request: Request,
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        CrmService(db).convert_lead(lead_id, LeadConvert(), actor_id=actor.id)
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/leads", err=getattr(exc, "message", "Could not convert lead"))
    return redirect("/leads", ok="Lead converted")


@router.post("/opportunities/{opp_id}/advance")
def advance_opportunity(
    request: Request,
    opp_id: uuid.UUID,
    pipeline_stage_id: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_current_actor),
):
    try:
        CrmService(db).advance_opportunity(
            opp_id,
            OpportunityAdvance(pipeline_stage_id=uuid.UUID(pipeline_stage_id)),
            actor_id=actor.id,
        )
    except (AppError, PydanticValidationError, ValueError) as exc:
        db.rollback()
        return redirect("/leads", err=getattr(exc, "message", "Could not advance opportunity"))
    return redirect("/leads", ok="Opportunity advanced")
