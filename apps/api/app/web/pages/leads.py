"""Leads & pipeline pages: leads list + create + convert, and opportunity
pipeline grouped by stage with an advance action."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Actor
from app.modules.config.service import ConfigService
from app.modules.crm.schemas import LeadConvert, LeadCreate, OpportunityAdvance
from app.modules.crm.service import CrmService
from app.web.core import form_action, render
from app.web.security import require_web_permission

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
    actor: Actor = Depends(require_web_permission("lead.create")),
):
    def work():
        payload = LeadCreate(
            company_name=company_name,
            contact_name=contact_name or None,
            city=city or None,
            source=source or None,
            customer_type_id=uuid.UUID(customer_type_id) if customer_type_id else None,
        )
        return CrmService(db).create_lead(payload, actor_id=actor.id)

    return form_action(
        db, work, back="/leads",
        success=("/leads", "Lead created"),
        err="Could not create lead",
    )


@router.post("/leads/{lead_id}/convert")
def convert_lead(
    request: Request,
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("lead.convert")),
):
    return form_action(
        db, lambda: CrmService(db).convert_lead(lead_id, LeadConvert(), actor_id=actor.id),
        back="/leads", success=("/leads", "Lead converted"),
        err="Could not convert lead",
    )


@router.post("/leads/{lead_id}/delete")
def delete_lead(
    request: Request,
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("lead.delete")),
):
    return form_action(
        db, lambda: CrmService(db).delete_lead(lead_id, actor_id=actor.id),
        back="/leads", success=("/leads", "Lead deleted"),
        err="Could not delete lead",
    )


@router.post("/opportunities/{opp_id}/advance")
def advance_opportunity(
    request: Request,
    opp_id: uuid.UUID,
    pipeline_stage_id: str = Form(...),
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_web_permission("opportunity.advance")),
):
    def work():
        return CrmService(db).advance_opportunity(
            opp_id,
            OpportunityAdvance(pipeline_stage_id=uuid.UUID(pipeline_stage_id)),
            actor_id=actor.id,
        )

    return form_action(
        db, work, back="/leads",
        success=("/leads", "Opportunity advanced"),
        err="Could not advance opportunity",
    )
